import os
import random
import re
import json
from collections import deque
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image, ImageDraw, ImageFont


URL_MAS_VENDIDOS = "https://www.mercadolibre.com.ar/mas-vendidos"
CANTIDAD_PRODUCTOS = 10

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}

CARPETA_OFERTAS = Path("ofertas")
CARPETA_OFERTAS.mkdir(exist_ok=True)

LOGO_PATH = Path("logo_cazadores.png")
LOGO_ML_PATH = Path("logo_mercadolibre.png")
PLANTILLA_OFERTA_PATH = Path("plantilla_oferta_aprobada.png")
PLANTILLA_PROMO_PATH = Path("plantilla_promo_aprobada.png")

REPO = os.getenv("GITHUB_REPOSITORY", "pase360/bot-ofertas-ml")
RAMA = os.getenv("GITHUB_REF_NAME", "main")
VERSION = os.getenv(
    "GITHUB_RUN_ID",
    datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S"),
)

RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{RAMA}/ofertas"

# Tamaño exacto de las plantillas aprobadas
ANCHO = 1122
ALTO = 1402


# =========================================================
# FUENTES
# =========================================================

def fuente(tamano, negrita=False, italica=False):
    if negrita and italica:
        candidatos = [
            "/usr/share/fonts/truetype/lato/Lato-HeavyItalic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-BoldOblique.ttf",
        ]
    elif negrita:
        candidatos = [
            "/usr/share/fonts/truetype/lato/Lato-Heavy.ttf",
            "/usr/share/fonts/truetype/lato/Lato-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        ]
    elif italica:
        candidatos = [
            "/usr/share/fonts/truetype/lato/Lato-Italic.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Oblique.ttf",
        ]
    else:
        candidatos = [
            "/usr/share/fonts/truetype/lato/Lato-Regular.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]

    for ruta in candidatos:
        if os.path.exists(ruta):
            return ImageFont.truetype(ruta, tamano)

    return ImageFont.load_default()


# =========================================================
# UTILIDADES
# =========================================================

def limpiar_texto(texto):
    if not texto:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()


def limpiar_url(url):
    if not url:
        return ""
    url = urljoin("https://www.mercadolibre.com.ar", url)
    return url.split("?")[0]


def es_producto(url):
    return bool(url and ("/p/MLA" in url or "/MLA-" in url))


def nombre_desde_url(url):
    try:
        path = urlparse(url).path
        partes = [parte for parte in path.split("/") if parte]
        candidato = ""

        for parte in partes:
            if parte == "p":
                continue
            if parte.upper().startswith("MLA"):
                continue
            if len(parte) > len(candidato):
                candidato = parte

        candidato = candidato.replace("-", " ").replace("_", " ")
        candidato = limpiar_texto(candidato)

        if candidato:
            return candidato.title()
    except Exception:
        pass

    return "Producto Mercado Libre"


def safe_get(url, timeout=30):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


# =========================================================
# CONTENEDOR DE PRODUCTO EN MÁS VENDIDOS
# =========================================================

def encontrar_contenedor(enlace):
    """
    Encuentra la tarjeta MÁS PEQUEÑA que contiene exactamente el producto
    del enlace. Esto evita mezclar precio o imagen de una tarjeta vecina.
    """
    url_objetivo = limpiar_url(enlace.get("href"))
    candidatos = []

    for nodo in enlace.parents:
        if not isinstance(nodo, Tag):
            continue

        texto = limpiar_texto(nodo.get_text(" ", strip=True))
        if not texto or len(texto) > 3500:
            continue

        # Contar productos distintos dentro del ancestro.
        urls_productos = []
        for a in nodo.find_all("a", href=True):
            u = limpiar_url(a.get("href"))
            if es_producto(u) and u not in urls_productos:
                urls_productos.append(u)

        if url_objetivo not in urls_productos:
            continue

        tiene_precio = nodo.select_one(".andes-money-amount") is not None or "$" in texto
        tiene_imagen = nodo.find("img") is not None

        if not (tiene_precio and tiene_imagen):
            continue

        clases = " ".join(nodo.get("class", [])).lower()
        es_tarjeta_tipica = any(
            marca in clases
            for marca in (
                "poly-card",
                "ui-search-result",
                "ui-search-layout__item",
                "andes-card",
            )
        )

        # Preferimos contenedores con un solo producto. Si hay más de uno,
        # guardamos como respaldo pero penalizado.
        cantidad_productos = len(urls_productos)
        puntuacion = 0
        if cantidad_productos == 1:
            puntuacion += 100
        elif cantidad_productos == 2:
            puntuacion += 10
        else:
            puntuacion -= cantidad_productos * 10

        if es_tarjeta_tipica:
            puntuacion += 30

        # Cuanto más chico el HTML, más probable que sea la tarjeta exacta.
        puntuacion -= min(len(texto), 3000) / 1000
        candidatos.append((puntuacion, len(texto), nodo))

        # Un contenedor típico con un solo producto es suficientemente seguro.
        if cantidad_productos == 1 and es_tarjeta_tipica:
            return nodo

    if candidatos:
        candidatos.sort(key=lambda x: (-x[0], x[1]))
        return candidatos[0][2]

    return enlace.parent


# =========================================================
# NOMBRE
# =========================================================

def obtener_nombre(contenedor, enlace, url):
    selectores = [
        ".poly-component__title",
        ".ui-search-item__title",
        "[class*='product-title']",
        "[class*='item-title']",
        "h2",
        "h3",
    ]

    for selector in selectores:
        try:
            elementos = contenedor.select(selector)
        except Exception:
            elementos = []

        for elemento in elementos:
            texto = limpiar_texto(elemento.get_text(" ", strip=True))
            inferior = texto.lower()

            if not 8 <= len(texto) <= 220:
                continue
            if "$" in texto:
                continue
            if "off" in inferior:
                continue
            if "más vendido" in inferior or "mas vendido" in inferior:
                continue
            if "envío gratis" in inferior or "envio gratis" in inferior:
                continue

            return texto

    for atributo in ["title", "aria-label"]:
        valor = limpiar_texto(enlace.get(atributo, ""))
        if 8 <= len(valor) <= 220:
            return valor

    for imagen in contenedor.find_all("img"):
        alt = limpiar_texto(imagen.get("alt", ""))
        if 8 <= len(alt) <= 220 and "$" not in alt:
            return alt

    return nombre_desde_url(url)


# =========================================================
# IMAGEN DEL PRODUCTO DESDE MÁS VENDIDOS
# =========================================================

def obtener_url_imagen(contenedor):
    """
    Toma la foto del producto de la tarjeta de Más vendidos.
    NO usa imágenes de la publicación individual, para evitar volver a
    capturar logos de Mercado Libre / Mercado Pago por error.
    """
    candidatos = []

    for imagen in contenedor.find_all("img"):
        alt = limpiar_texto(imagen.get("alt", "")).lower()

        urls = []
        for atributo in ["data-src", "data-lazy", "src"]:
            url = imagen.get(atributo)
            if url and url.startswith("http"):
                urls.append(url)

        srcset = imagen.get("srcset")
        if srcset:
            for opcion in srcset.split(","):
                url = opcion.strip().split(" ")[0]
                if url.startswith("http"):
                    urls.append(url)

        for url in urls:
            inferior = url.lower()

            if ".svg" in inferior:
                continue
            if any(p in inferior for p in ["logo", "icon", "sprite", "brand", "favicon"]):
                continue

            puntos = 0
            if "mlstatic.com" in inferior:
                puntos += 5
            if "d_nq_np" in inferior or "d_nq_nn" in inferior:
                puntos += 5
            if alt:
                puntos += 1

            candidatos.append((puntos, url))

    if not candidatos:
        return ""

    candidatos.sort(key=lambda x: x[0], reverse=True)
    return candidatos[0][1]


def descargar_imagen(url):
    if not url:
        return None

    try:
        response = safe_get(url, timeout=30)
        imagen = Image.open(BytesIO(response.content))
        return imagen.convert("RGBA")
    except Exception as e:
        print("ERROR imagen:", e)
        return None


def quitar_fondo_blanco_conectado(imagen):
    """
    Quita solo el fondo blanco/casi blanco conectado a los bordes.
    Es más seguro que borrar todos los píxeles blancos, porque conserva
    partes blancas internas del producto.
    """
    if imagen is None:
        return None

    img = imagen.convert("RGBA")
    w, h = img.size

    # Evita procesar imágenes enormes pixel a pixel.
    max_lado = 1100
    if max(w, h) > max_lado:
        escala = max_lado / max(w, h)
        img = img.resize(
            (max(1, int(w * escala)), max(1, int(h * escala))),
            Image.LANCZOS,
        )
        w, h = img.size

    px = img.load()
    visitado = bytearray(w * h)
    cola = deque()

    def es_fondo(x, y):
        r, g, b, a = px[x, y]
        if a == 0:
            return True
        # blanco o casi blanco, sin mucha diferencia entre canales
        return r >= 246 and g >= 246 and b >= 246 and (max(r, g, b) - min(r, g, b)) <= 8

    def agregar(x, y):
        idx = y * w + x
        if not visitado[idx] and es_fondo(x, y):
            visitado[idx] = 1
            cola.append((x, y))

    for x in range(w):
        agregar(x, 0)
        agregar(x, h - 1)
    for y in range(h):
        agregar(0, y)
        agregar(w - 1, y)

    while cola:
        x, y = cola.popleft()
        r, g, b, _ = px[x, y]
        px[x, y] = (r, g, b, 0)

        if x > 0:
            agregar(x - 1, y)
        if x + 1 < w:
            agregar(x + 1, y)
        if y > 0:
            agregar(x, y - 1)
        if y + 1 < h:
            agregar(x, y + 1)

    bbox = img.getbbox()
    if bbox:
        img = img.crop(bbox)

    return img


# =========================================================
# PRECIOS
# =========================================================

def leer_money_amount(elemento):
    if not elemento:
        return ""

    fraction = elemento.select_one(".andes-money-amount__fraction")
    cents = elemento.select_one(".andes-money-amount__cents")

    if fraction:
        entero = limpiar_texto(fraction.get_text())
        if cents:
            centavos = limpiar_texto(cents.get_text())
            if centavos:
                return "$ " + entero + "," + centavos
        return "$ " + entero

    texto = limpiar_texto(elemento.get_text(" ", strip=True))
    match = re.search(r"\$\s*([\d\.]+(?:,\d+)?)", texto)

    if match:
        return "$ " + match.group(1)

    return ""


def extraer_importes_texto(texto):
    encontrados = re.findall(r"\$\s*([\d\.]+(?:,\d+)?)", texto)
    resultado = []

    for valor in encontrados:
        importe = "$ " + valor
        if importe not in resultado:
            resultado.append(importe)

    return resultado


def _es_precio_anterior_tarjeta(elemento):
    """Devuelve True solo si el importe pertenece al precio viejo/tachado."""
    nodo = elemento
    for _ in range(7):
        if nodo is None or not isinstance(nodo, Tag):
            break

        clases = " ".join(nodo.get("class", []))
        attrs = " ".join(
            str(nodo.get(k, ""))
            for k in ("id", "data-testid", "aria-label")
        )
        inferior = (clases + " " + attrs).lower()

        if any(
            marca in inferior
            for marca in (
                "previous",
                "original",
                "strikethrough",
                "old-price",
                "price-before",
                "list-price",
            )
        ):
            return True

        # Mercado Libre suele envolver el precio viejo en <s>.
        if getattr(nodo, "name", "") == "s":
            return True

        nodo = nodo.parent

    return False


def _es_precio_secundario_tarjeta(elemento):
    """Evita cuotas, precio por unidad, cupones u otros importes auxiliares."""
    nodo = elemento
    for _ in range(6):
        if nodo is None or not isinstance(nodo, Tag):
            break

        clases = " ".join(nodo.get("class", []))
        attrs = " ".join(
            str(nodo.get(k, ""))
            for k in ("id", "data-testid", "aria-label")
        )
        inferior = (clases + " " + attrs).lower()

        if any(
            marca in inferior
            for marca in (
                "installment",
                "installments",
                "financing",
                "unit-price",
                "price-per-unit",
                "coupon",
                "rebate",
            )
        ):
            return True

        nodo = nodo.parent

    return False


def _primer_precio_valido_en(nodos, precio_anterior=""):
    """Toma el primer precio de venta real en orden DOM, sin exigir unicidad."""
    for nodo in nodos:
        if _es_precio_anterior_tarjeta(nodo):
            continue
        if _es_precio_secundario_tarjeta(nodo):
            continue

        valor = leer_money_amount(nodo)
        if not valor:
            continue
        if precio_anterior and valor == precio_anterior:
            continue

        return valor

    return ""


def obtener_precios(contenedor, texto, descuento):
    """
    Obtiene el precio ACTUAL de la misma tarjeta de Más vendidos.

    La clave es NO exigir que exista un único money-amount en toda la tarjeta:
    Mercado Libre puede renderizar otros importes auxiliares. Se usa primero
    el bloque semántico .poly-price__current, que es el precio de venta actual.
    """
    precio_anterior = ""

    # Precio anterior/tachado, solo como referencia; nunca se usa como actual.
    selectores_anteriores = (
        "s.andes-money-amount--previous",
        ".andes-money-amount--previous",
        ".poly-price__original .andes-money-amount",
        ".ui-search-price__original-value .andes-money-amount",
        "[class*='original'] .andes-money-amount",
        "[class*='previous'] .andes-money-amount",
    )

    for selector in selectores_anteriores:
        try:
            nodos = contenedor.select(selector)
        except Exception:
            nodos = []

        for nodo in nodos:
            valor = leer_money_amount(nodo)
            if valor:
                precio_anterior = valor
                break
        if precio_anterior:
            break

    # 1) Selector oficial/estable de las tarjetas poly actuales.
    try:
        nodos = contenedor.select(".poly-price__current .andes-money-amount")
    except Exception:
        nodos = []

    precio = _primer_precio_valido_en(nodos, precio_anterior)
    if precio:
        return precio, precio_anterior

    # 2) Variantes de layout vistas en Mercado Libre.
    selectores_actuales = (
        ".ui-search-price__second-line .andes-money-amount",
        "[data-testid='price-part'] .andes-money-amount",
        "[class*='current'] .andes-money-amount",
    )

    for selector in selectores_actuales:
        try:
            nodos = contenedor.select(selector)
        except Exception:
            nodos = []

        precio = _primer_precio_valido_en(nodos, precio_anterior)
        if precio:
            return precio, precio_anterior

    # 3) Respaldo dentro del componente de precio de ESA MISMA tarjeta.
    try:
        nodos = contenedor.select(".poly-component__price .andes-money-amount")
    except Exception:
        nodos = []

    precio = _primer_precio_valido_en(nodos, precio_anterior)
    if precio:
        return precio, precio_anterior

    # 4) Último respaldo: primer money-amount que no sea viejo ni secundario.
    # Sigue limitado a la tarjeta exacta del producto, no al texto libre.
    try:
        nodos = contenedor.select(".andes-money-amount")
    except Exception:
        nodos = []

    precio = _primer_precio_valido_en(nodos, precio_anterior)
    if precio:
        return precio, precio_anterior

    return "Precio no disponible", precio_anterior


# =========================================================
# DATOS DE LA TARJETA DE MÁS VENDIDOS
# =========================================================

def extraer_datos_tarjeta(enlace, contenedor):
    url = limpiar_url(enlace.get("href"))
    texto = limpiar_texto(contenedor.get_text(" ", strip=True))
    nombre = obtener_nombre(contenedor, enlace, url)

    descuento = ""
    match = re.search(r"(\d{1,2}%\s*OFF)", texto, re.IGNORECASE)
    if match:
        descuento = match.group(1).upper()

    precio, precio_anterior = obtener_precios(contenedor, texto, descuento)

    cuotas = ""
    patrones_cuotas = [
        r"((?:Mismo precio(?: en)?\s+)?\d{1,2}\s+cuotas(?:\s+sin\s+inter[eé]s)?(?:\s+de\s+\$\s*[\d\.\,]+)?)",
        r"(\d{1,2}\s+cuotas(?:\s+de\s+\$\s*[\d\.\,]+)?)",
    ]

    for patron in patrones_cuotas:
        match = re.search(patron, texto, re.IGNORECASE)
        if match:
            cuotas = limpiar_texto(match.group(1))
            break

    if not cuotas:
        cuotas = ""

    ranking = ""
    match = re.search(
        r"(\d{1,2})\s*[º°]\s*(?:MÁS|MAS)\s+VENDIDO",
        texto,
        re.IGNORECASE,
    )
    if match:
        ranking = match.group(1) + "º MÁS VENDIDO"

    rating = ""
    for selector in [
        ".poly-reviews__rating",
        ".ui-search-reviews__rating-number",
        "[class*='rating']",
    ]:
        elemento = contenedor.select_one(selector)
        if not elemento:
            continue

        texto_rating = limpiar_texto(elemento.get_text(" ", strip=True))
        match = re.search(r"\b([1-5](?:[\.,]\d)?)\b", texto_rating)
        if match:
            rating = match.group(1).replace(",", ".")
            break

    vendidos = ""
    match = re.search(
        r"(\+?\s*[\d\.]+\s*(?:mil)?\s+(?:productos\s+)?vendidos)",
        texto,
        re.IGNORECASE,
    )
    if match:
        vendidos = limpiar_texto(match.group(1))

    imagen_url = obtener_url_imagen(contenedor)

    return {
        "url_original": url,
        "nombre": nombre,
        "precio": precio,
        "precio_anterior": precio_anterior,
        "precio_verificado": precio != "Precio no disponible",
        "descuento": descuento,
        "cuotas": cuotas,
        "ranking": ranking,
        "rating": rating,
        "vendidos": vendidos,
        "imagen_url": imagen_url,
        "atributos_visuales": [],
    }


# =========================================================
# TEXTO REAL DE LA PUBLICACIÓN INDIVIDUAL
# =========================================================

def extraer_publicacion(url):
    try:
        response = safe_get(url, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        texto = limpiar_texto(soup.get_text(" ", strip=True))
        return soup, texto
    except Exception as e:
        print("ERROR leyendo publicación:", url, e)
        return None, ""


def extraer_json_ld(soup):
    if not soup:
        return []

    encontrados = []

    for script in soup.find_all("script", type="application/ld+json"):
        contenido = script.string or script.get_text(strip=True)
        if not contenido:
            continue

        try:
            data = json.loads(contenido)
        except Exception:
            continue

        if isinstance(data, list):
            encontrados.extend([x for x in data if isinstance(x, dict)])
        elif isinstance(data, dict):
            encontrados.append(data)

    return encontrados


# =========================================================
# PRECIO ACTUAL VERIFICADO DE LA PUBLICACIÓN INDIVIDUAL
# =========================================================

def _iterar_json(obj):
    if isinstance(obj, dict):
        yield obj
        for valor in obj.values():
            yield from _iterar_json(valor)
    elif isinstance(obj, list):
        for item in obj:
            yield from _iterar_json(item)


def _normalizar_numero_precio(valor):
    if valor is None:
        return None

    if isinstance(valor, (int, float)):
        return float(valor)

    texto = limpiar_texto(valor)
    if not texto:
        return None

    texto = texto.replace("$", "").replace(" ", "")

    # AR: 44.155,50 -> 44155.50
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".")
    else:
        # si solo hay puntos y el último grupo tiene 3 dígitos,
        # se consideran separadores de miles
        partes = texto.split(".")
        if len(partes) > 1 and all(p.isdigit() for p in partes):
            if len(partes[-1]) == 3:
                texto = "".join(partes)

    texto = re.sub(r"[^0-9.]", "", texto)

    try:
        numero = float(texto)
    except Exception:
        return None

    if numero <= 0:
        return None

    return numero


def _formatear_precio(numero):
    if numero is None:
        return ""

    if abs(numero - round(numero)) < 0.001:
        entero = int(round(numero))
        return "$ " + f"{entero:,}".replace(",", ".")

    entero = int(numero)
    centavos = int(round((numero - entero) * 100))
    return "$ " + f"{entero:,}".replace(",", ".") + f",{centavos:02d}"


def precio_desde_json_ld(soup):
    """Busca el precio ACTUAL estructurado del Product/Offer."""
    if not soup:
        return ""

    for item in extraer_json_ld(soup):
        for nodo in _iterar_json(item):
            tipo = nodo.get("@type")
            tipos = tipo if isinstance(tipo, list) else [tipo]
            tipos = [str(x).lower() for x in tipos if x]

            # Product -> offers
            if "product" in tipos:
                offers = nodo.get("offers")
                if isinstance(offers, dict):
                    offers = [offers]
                if isinstance(offers, list):
                    for offer in offers:
                        if not isinstance(offer, dict):
                            continue
                        for clave in ("price", "lowPrice"):
                            numero = _normalizar_numero_precio(offer.get(clave))
                            if numero is not None:
                                return _formatear_precio(numero)

            # Offer directo
            if "offer" in tipos or "aggregateoffer" in tipos:
                for clave in ("price", "lowPrice"):
                    numero = _normalizar_numero_precio(nodo.get(clave))
                    if numero is not None:
                        return _formatear_precio(numero)

    return ""


def precio_desde_meta(soup):
    if not soup:
        return ""

    selectores = [
        "meta[itemprop='price'][content]",
        "meta[property='product:price:amount'][content]",
        "meta[property='og:price:amount'][content]",
        "[itemprop='price'][content]",
    ]

    for selector in selectores:
        try:
            nodos = soup.select(selector)
        except Exception:
            nodos = []

        for nodo in nodos:
            numero = _normalizar_numero_precio(nodo.get("content"))
            if numero is not None:
                return _formatear_precio(numero)

    return ""


def _es_precio_anterior(elemento):
    nodo = elemento
    for _ in range(5):
        if nodo is None or not isinstance(nodo, Tag):
            break
        clases = " ".join(nodo.get("class", []))
        inferior = clases.lower()
        if any(x in inferior for x in ("previous", "original", "strikethrough")):
            return True
        nodo = nodo.parent
    return False


def precio_desde_dom_actual(soup):
    """Último respaldo: solo nodos de precio actual, nunca previous/original."""
    if not soup:
        return ""

    selectores = [
        ".ui-pdp-price__second-line .andes-money-amount",
        ".ui-pdp-price__main-container .andes-money-amount",
        "[data-testid='price-part'] .andes-money-amount",
    ]

    for selector in selectores:
        try:
            nodos = soup.select(selector)
        except Exception:
            nodos = []

        for nodo in nodos:
            if _es_precio_anterior(nodo):
                continue
            valor = leer_money_amount(nodo)
            numero = _normalizar_numero_precio(valor)
            if numero is not None:
                return _formatear_precio(numero)

    return ""


def obtener_precio_actual_verificado(soup):
    """
    Devuelve SOLO un precio actual verificable.
    No usa el primer número del texto de la página y no aproxima.
    """
    for extractor in (
        precio_desde_json_ld,
        precio_desde_meta,
        precio_desde_dom_actual,
    ):
        precio = extractor(soup)
        if precio:
            return precio

    return ""


def es_texto_util_atributo(texto, nombre_producto=""):
    texto = limpiar_texto(texto)
    if not texto:
        return False

    inferior = texto.lower()

    if len(texto) < 3 or len(texto) > 55:
        return False

    prohibidos = [
        "mercado libre",
        "mercado pago",
        "comprar",
        "oferta",
        "envío",
        "envio",
        "devolución",
        "devolucion",
        "stock",
        "cuotas",
        "medios de pago",
        "vendidos",
        "opiniones",
        "preguntas",
        "publicación",
        "publicacion",
        "más información",
        "mas información",
        "ver más",
        "ver mas",
        "carrito",
        "iniciar sesión",
        "iniciar sesion",
    ]

    if any(p in inferior for p in prohibidos):
        return False

    if "$" in texto or "%" in texto:
        return False

    # Evita repetir el título completo como característica.
    if nombre_producto and limpiar_texto(nombre_producto).lower() == inferior:
        return False

    return True


def normalizar_atributo(texto):
    texto = limpiar_texto(texto)
    texto = re.sub(r"\s*:\s*", ": ", texto)

    # Acorta frases muy largas sin inventar contenido.
    palabras = texto.split()
    if len(palabras) > 7:
        texto = " ".join(palabras[:7])

    return texto.strip(" -–—:;")


def atributos_desde_json_ld(soup, nombre_producto):
    resultado = []

    for item in extraer_json_ld(soup):
        adicionales = item.get("additionalProperty")
        if not adicionales:
            continue

        if isinstance(adicionales, dict):
            adicionales = [adicionales]

        if not isinstance(adicionales, list):
            continue

        for prop in adicionales:
            if not isinstance(prop, dict):
                continue

            nombre = limpiar_texto(prop.get("name", ""))
            valor = limpiar_texto(prop.get("value", ""))

            if nombre and valor:
                texto = f"{nombre}: {valor}"
            else:
                texto = valor or nombre

            texto = normalizar_atributo(texto)

            if es_texto_util_atributo(texto, nombre_producto) and texto not in resultado:
                resultado.append(texto)

            if len(resultado) >= 3:
                return resultado

    return resultado


def atributos_desde_html(soup, nombre_producto):
    resultado = []

    if not soup:
        return resultado

    selectores = [
        ".ui-vpp-highlighted-specs__features li",
        ".ui-pdp-highlights__content li",
        ".ui-pdp-specs__table tr",
        ".andes-table__row",
        "table tr",
        "[class*='specs'] li",
        "[class*='highlight'] li",
    ]

    for selector in selectores:
        try:
            nodos = soup.select(selector)
        except Exception:
            nodos = []

        for nodo in nodos:
            texto = normalizar_atributo(nodo.get_text(" ", strip=True))

            if es_texto_util_atributo(texto, nombre_producto) and texto not in resultado:
                resultado.append(texto)

            if len(resultado) >= 3:
                return resultado

    return resultado


def atributos_desde_titulo(titulo):
    """
    Último respaldo: extrae expresiones que están literalmente presentes
    en el título real del producto. No inventa características.
    """
    t = limpiar_texto(titulo)
    tl = t.lower()
    resultado = []

    patrones = [
        (r"\bA4\b", "Formato A4"),
        (r"\bA3\b", "Formato A3"),
        (r"\b(\d+(?:[\.,]\d+)?)\s*(?:gr|g)\b", lambda m: f"{m.group(1)} g"),
        (r"\b(\d+(?:[\.,]\d+)?)\s*(?:kg)\b", lambda m: f"{m.group(1)} kg"),
        (r"\b(\d+(?:[\.,]\d+)?)\s*(?:litros?|l)\b", lambda m: f"{m.group(1)} litros"),
        (r"\b(\d+)\s*jarros?\b", lambda m: f"{m.group(1)} jarros"),
        (r"\b(blanco|blanca|negro|negra|verde|azul|rojo|roja|gris|rosa)\b", lambda m: f"Color {m.group(1)}"),
        (r"\bbluetooth\b", "Bluetooth"),
        (r"\binal[aá]mbric[oa]\b", "Uso inalámbrico"),
        (r"\bamortiguaci[oó]n(?:\s+de\s+aire)?\b", lambda m: m.group(0).capitalize()),
        (r"\blivian[oa]s?\b", lambda m: m.group(0).capitalize()),
        (r"\bdeportiv[oa]s?\b", lambda m: m.group(0).capitalize()),
        (r"\b(\d+)\s*ml\b", lambda m: f"{m.group(1)} ml"),
        (r"\b(\d+)\s*cm\b", lambda m: f"{m.group(1)} cm"),
        (r"\b(\d+)\s*unidades?\b", lambda m: f"{m.group(1)} unidades"),
    ]

    for patron, salida in patrones:
        for m in re.finditer(patron, t, re.IGNORECASE):
            if callable(salida):
                texto = salida(m)
            else:
                texto = salida

            texto = limpiar_texto(texto)
            if texto and texto.lower() not in [x.lower() for x in resultado]:
                resultado.append(texto)

            if len(resultado) >= 3:
                return resultado

    # Si todavía falta, toma fragmentos reales del título sin inventarlos.
    palabras = t.split()
    stop = {
        "para", "con", "sin", "de", "del", "la", "el", "los", "las",
        "y", "en", "un", "una", "por", "a", "modelo", "marca",
    }

    for palabra in palabras:
        limpia = palabra.strip(",.;:()[]-/")
        if len(limpia) < 4:
            continue
        if limpia.lower() in stop:
            continue
        if limpia.lower() in tl and limpia.lower() not in [x.lower() for x in resultado]:
            resultado.append(limpia.capitalize())
        if len(resultado) >= 3:
            break

    return resultado[:3]


def obtener_atributos_reales_publicacion(soup, titulo):
    resultado = []

    for fuente_resultados in [
        atributos_desde_json_ld(soup, titulo),
        atributos_desde_html(soup, titulo),
        atributos_desde_titulo(titulo),
    ]:
        for texto in fuente_resultados:
            texto = normalizar_atributo(texto)
            if not texto:
                continue
            if texto.lower() not in [x.lower() for x in resultado]:
                resultado.append(texto)
            if len(resultado) >= 3:
                return resultado

    return resultado[:3]


def enriquecer_solo_textos_reales(datos):
    """
    La publicación individual se consulta SOLO para obtener características
    reales del producto. El precio y la foto permanecen exactamente como
    fueron extraídos de la misma tarjeta de Más vendidos.

    Mercado Libre no expone de forma estable el precio de la PDP a requests
    sin sesión, por eso NO se usa esa página para reemplazar el precio.
    """
    imagen_original = datos.get("imagen_url", "")
    precio_original = datos.get("precio", "")

    soup, _ = extraer_publicacion(datos["url_original"])

    if soup:
        atributos = obtener_atributos_reales_publicacion(
            soup,
            datos["nombre"],
        )
        if atributos:
            datos["atributos_visuales"] = atributos
        else:
            datos["atributos_visuales"] = atributos_desde_titulo(datos["nombre"])
    else:
        datos["atributos_visuales"] = atributos_desde_titulo(datos["nombre"])

    # Garantías: la publicación individual jamás reemplaza precio ni foto.
    datos["imagen_url"] = imagen_original
    datos["precio"] = precio_original
    datos["precio_verificado"] = precio_original not in ("", "Precio no disponible")

    return datos


# =========================================================
# OBTENER PRODUCTOS
# =========================================================

def obtener_productos():
    print("--- DESCARGANDO MÁS VENDIDOS ---")

    response = safe_get(URL_MAS_VENDIDOS, timeout=30)
    print("HTTP Más vendidos:", response.status_code)

    soup = BeautifulSoup(response.text, "html.parser")
    encontrados = {}

    for enlace in soup.find_all("a", href=True):
        url = limpiar_url(enlace.get("href"))

        if not es_producto(url):
            continue
        if "mas-vendidos" in url:
            continue

        contenedor = encontrar_contenedor(enlace)
        if not contenedor:
            continue

        datos = extraer_datos_tarjeta(enlace, contenedor)

        puntos = 0
        if datos["nombre"] != "Producto Mercado Libre":
            puntos += 5
        if datos["imagen_url"]:
            puntos += 6
        if datos.get("precio_verificado"):
            puntos += 8
        if datos["descuento"]:
            puntos += 1
        if datos["cuotas"]:
            puntos += 1
        if datos["ranking"]:
            puntos += 1

        anterior = encontrados.get(url)
        if anterior is None or puntos > anterior["_puntos"]:
            datos["_puntos"] = puntos
            encontrados[url] = datos

    productos = list(encontrados.values())
    productos.sort(key=lambda producto: producto["_puntos"], reverse=True)

    print("Productos encontrados:", len(productos))

    # Solo candidatos donde link, nombre, foto y precio salen de la MISMA
    # tarjeta y el precio actual no es ambiguo.
    candidatos = [
        producto
        for producto in productos
        if (
            producto.get("precio_verificado")
            and producto["imagen_url"]
            and producto["nombre"] != "Producto Mercado Libre"
        )
    ]

    print("Productos con tarjeta completa y precio actual único:", len(candidatos))

    if len(candidatos) < CANTIDAD_PRODUCTOS:
        raise RuntimeError(
            f"Solo se encontraron {len(candidatos)} productos con link, foto y precio actual "
            "inequívocos en la misma tarjeta de Más vendidos."
        )

    # Mantener variedad sin perder seguridad.
    pool = candidatos[:40]
    seleccionados = random.sample(pool, CANTIDAD_PRODUCTOS)

    resultado = []
    for numero, producto in enumerate(seleccionados, start=1):
        print(
            f"ACEPTADO {numero}. {producto['nombre']} | "
            f"precio={producto['precio']} | "
            f"foto={producto['imagen_url'][:70]}"
        )

        # Solo añade características; no modifica precio ni foto.
        producto = enriquecer_solo_textos_reales(producto)
        resultado.append(producto)

    return resultado


# =========================================================
# TEXTO PARA LA IMAGEN
# =========================================================

def ajustar_texto(draw, texto, font, ancho_maximo):
    palabras = limpiar_texto(texto).split()

    if not palabras:
        return [""]

    lineas = []
    linea = palabras[0]

    for palabra in palabras[1:]:
        prueba = linea + " " + palabra
        caja = draw.textbbox((0, 0), prueba, font=font)
        ancho = caja[2] - caja[0]

        if ancho <= ancho_maximo:
            linea = prueba
        else:
            lineas.append(linea)
            linea = palabra

    lineas.append(linea)
    return lineas


def lineas_limitadas(draw, texto, font, ancho_maximo, max_lineas):
    lineas = ajustar_texto(draw, texto, font, ancho_maximo)

    if len(lineas) <= max_lineas:
        return lineas

    lineas = lineas[:max_lineas]
    ultima = lineas[-1]

    while ultima:
        prueba = ultima + "…"
        caja = draw.textbbox((0, 0), prueba, font=font)
        if caja[2] - caja[0] <= ancho_maximo:
            lineas[-1] = prueba
            break
        ultima = ultima[:-1]

    return lineas


def fuente_titulo(draw, texto):
    # Tamaño y peso ajustados al diseño aprobado.
    for tamano in range(43, 30, -1):
        f = fuente(tamano, True)
        lineas = ajustar_texto(draw, texto, f, 920)
        if len(lineas) <= 2:
            return f, lineas

    f = fuente(30, True)
    return f, lineas_limitadas(draw, texto, f, 920, 2)


# =========================================================
# PLANTILLA APROBADA
# =========================================================

def cargar_plantilla(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Falta {path.name}. Subila a la raíz del repositorio."
        )

    imagen = Image.open(path).convert("RGBA")

    if imagen.size != (ANCHO, ALTO):
        imagen = imagen.resize((ANCHO, ALTO), Image.LANCZOS)

    return imagen


def dibujar_textos_laterales(draw, datos):
    """
    Usa únicamente los tres textos obtenidos de la publicación real.
    Los íconos amarillos ya están incorporados en la plantilla.
    """
    textos = list(datos.get("atributos_visuales", []))[:3]

    # Si la web no expuso 3 especificaciones, completa solo con texto literal
    # del título de la publicación, nunca con frases inventadas.
    if len(textos) < 3:
        for texto in atributos_desde_titulo(datos.get("nombre", "")):
            if texto.lower() not in [x.lower() for x in textos]:
                textos.append(texto)
            if len(textos) >= 3:
                break

    while len(textos) < 3:
        textos.append("")

    centros_y = [390, 510, 630]
    font_item = fuente(19, False)

    for cy, texto in zip(centros_y, textos):
        if not texto:
            continue

        lineas = ajustar_texto(draw, texto, font_item, 170)[:3]
        alto_linea = 22
        y = cy - (len(lineas) * alto_linea) // 2

        for linea in lineas:
            draw.text((157, y), linea, font=font_item, fill=(18, 18, 18))
            y += alto_linea


def pegar_producto(imagen, producto):
    """
    Inserta el producto grande, centrado y sin el rectángulo blanco exterior.
    """
    if producto is None:
        return

    producto = quitar_fondo_blanco_conectado(producto)
    if producto is None or producto.width < 2 or producto.height < 2:
        return

    # Zona central del diseño aprobado.
    area_x0 = 245
    area_y0 = 275
    area_x1 = 1010
    area_y1 = 770

    max_w = area_x1 - area_x0
    max_h = area_y1 - area_y0

    escala = min(max_w / producto.width, max_h / producto.height)

    # Le damos presencia similar a la zapatilla aprobada.
    # Nunca achica innecesariamente una foto pequeña.
    nuevo_w = max(1, int(producto.width * escala))
    nuevo_h = max(1, int(producto.height * escala))

    producto = producto.resize((nuevo_w, nuevo_h), Image.LANCZOS)

    x = area_x0 + (max_w - producto.width) // 2
    y = area_y0 + (max_h - producto.height) // 2

    imagen.paste(producto, (x, y), producto)


def dibujar_precio(draw, precio):
    texto = limpiar_texto(precio)

    for tamano in range(75, 52, -1):
        f = fuente(tamano, True)
        caja = draw.textbbox((0, 0), texto, font=f)
        ancho = caja[2] - caja[0]

        if ancho <= 760:
            x = (ANCHO - ancho) // 2
            draw.text(
                (x, 968),
                texto,
                font=f,
                fill=(18, 105, 255),
            )
            return


def dibujar_slogan_mercado_libre(draw):
    """Agrega el slogan visible en el modelo aprobado."""
    azul = (36, 49, 126)
    amarillo = (255, 225, 0)

    f = fuente(20, True, True)
    draw.text((838, 269), "Lo mejor", font=f, fill=azul)
    draw.text((855, 292), "está acá", font=f, fill=azul)
    draw.line((916, 319, 972, 305), fill=amarillo, width=7)


def crear_imagen_oferta(datos, numero):
    nombre_archivo = f"oferta_final_{numero:02d}_{VERSION}.png"
    salida = CARPETA_OFERTAS / nombre_archivo

    # La plantilla fija conserva exactamente colores, cabecera, tarjetas,
    # barra negra, barra inferior, logos y adornos aprobados.
    imagen = cargar_plantilla(PLANTILLA_OFERTA_PATH)
    draw = ImageDraw.Draw(imagen)

    dibujar_slogan_mercado_libre(draw)

    # 1) Textos laterales: de la publicación real.
    dibujar_textos_laterales(draw, datos)

    # 2) Foto: SIEMPRE la que viene de Más vendidos.
    producto = descargar_imagen(datos["imagen_url"])
    pegar_producto(imagen, producto)

    # 3) Nombre real del producto.
    font_titulo, lineas = fuente_titulo(draw, datos["nombre"])

    y = 825
    for linea in lineas[:2]:
        caja = draw.textbbox((0, 0), linea, font=font_titulo)
        ancho = caja[2] - caja[0]
        x = (ANCHO - ancho) // 2
        draw.text((x, y), linea, font=font_titulo, fill=(6, 6, 6))
        y += 45

    # 4) Precio.
    dibujar_precio(draw, datos["precio"])

    imagen.convert("RGB").save(salida, "PNG", optimize=True)

    print("✅ Imagen creada con producto correcto:", salida)
    return nombre_archivo


# =========================================================
# PROPAGANDA DEL CANAL
# =========================================================

def crear_imagen_promo_canal():
    nombre_archivo = "promo_canal.png"
    salida = CARPETA_OFERTAS / nombre_archivo

    imagen = cargar_plantilla(PLANTILLA_PROMO_PATH)
    imagen.convert("RGB").save(salida, "PNG", optimize=True)

    print("✅ Propaganda del canal creada:", salida)
    return nombre_archivo


# =========================================================
# GUARDAR ARCHIVOS PARA AUTOMATE
# =========================================================

def limpiar_ofertas():
    for archivo in CARPETA_OFERTAS.glob("oferta_*.png"):
        try:
            archivo.unlink()
        except Exception:
            pass


def guardar_tanda(productos):
    limpiar_ofertas()

    links = []
    datos_txt = []
    imagenes = []

    for numero, datos in enumerate(productos, start=1):
        archivo = crear_imagen_oferta(datos, numero)

        links.append(datos["url_original"])

        nombre = datos["nombre"].replace("|", "-")
        precio = datos["precio"].replace("|", "-")
        cuotas = datos.get("cuotas", "").replace("|", "-")

        datos_txt.append(f"{nombre} | {precio} | {cuotas}")
        imagenes.append(f"{RAW_BASE}/{archivo}")

    Path("ultima_tanda.txt").write_text("\n".join(links), encoding="utf-8")
    Path("datos_tanda.txt").write_text("\n".join(datos_txt), encoding="utf-8")
    Path("imagenes_tanda.txt").write_text("\n".join(imagenes), encoding="utf-8")

    print("✅ ultima_tanda.txt generado")
    print("✅ datos_tanda.txt generado")
    print("✅ imagenes_tanda.txt generado")

    # Queda aparte para no cambiar el circuito actual de Automate.
    crear_imagen_promo_canal()


# =========================================================
# MAIN
# =========================================================

def main():
    productos = obtener_productos()

    if not productos:
        raise RuntimeError("No se pudieron obtener productos")

    print("Productos seleccionados:", len(productos))
    guardar_tanda(productos)
    print("✅ PROCESO COMPLETO FINALIZADO")


if __name__ == "__main__":
    main()
