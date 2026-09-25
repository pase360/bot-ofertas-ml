import os
import random
import re
import json
from collections import deque
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit, parse_qsl, urlencode, quote_plus

import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image, ImageDraw, ImageFont


URL_MAS_VENDIDOS = "https://www.mercadolibre.com.ar/mas-vendidos"
URL_OFERTAS = "https://www.mercadolibre.com.ar/ofertas"
CANTIDAD_PRODUCTOS = 10

# NUEVO: demanda detectada por el agente externo. Cada línea puede ser:
#   texto buscado
# o:
#   texto buscado | URL pública donde apareció la intención de compra
DEMANDA_PATH = Path("demanda_detectada.txt")
DEMANDA_PROCESADA_PATH = Path("demanda_procesada.txt")
REPORTE_DEMANDA_PATH = Path("reporte_demanda.txt")

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
HISTORIAL_PATH = Path("historial_publicados.txt")

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
    """
    Conserva la query string del enlace. Esto es CLAVE en Mercado Libre:
    los links de catálogo /p/MLA... pueden traer pdp_filters=item_id:MLA...
    y ese parámetro identifica la publicación/oferta exacta cuyo precio se
    muestra en la tarjeta. Antes se borraba todo lo que seguía a '?', lo que
    podía transformar un link exacto en un catálogo genérico con otro precio.
    Solo se elimina el fragmento #... del navegador.
    """
    if not url:
        return ""

    url = urljoin("https://www.mercadolibre.com.ar", url)
    partes = urlsplit(url)
    return urlunsplit((partes.scheme, partes.netloc, partes.path, partes.query, ""))


def es_producto(url):
    return bool(url and ("/p/MLA" in url or "/MLA-" in url))


def tiene_publicacion_exacta(url):
    """
    True cuando el enlace apunta a una publicación concreta y no solo a un
    catálogo genérico. Acepta:
      - URLs /MLA-123...
      - URLs /p/MLA... con item_id:MLA... en la query (pdp_filters, item_id, etc.)
    """
    if not url:
        return False

    inferior = url.lower()
    if re.search(r"/mla-?\d+", inferior):
        return True

    query = urlsplit(url).query
    if not query:
        return False

    # parseo tolerante: Mercado Libre puede codificar ':' como %3A
    query_decodificada = requests.utils.unquote(query).lower()
    return bool(re.search(r"item[_-]?id(?:=|%3d|:)[^&]*mla-?\d+", query_decodificada)
                or re.search(r"pdp_filters=[^&]*item[_-]?id[^&]*mla-?\d+", query_decodificada))


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
    nodo = enlace
    candidatos = []

    for _ in range(10):
        nodo = nodo.parent

        if not isinstance(nodo, Tag):
            break

        texto = limpiar_texto(nodo.get_text(" ", strip=True))

        if not texto:
            continue
        if len(texto) > 3000:
            continue

        tiene_precio = "$" in texto
        tiene_imagen = nodo.find("img") is not None
        tiene_datos = bool(
            re.search(
                r"vendidos|cuotas|%\s*OFF|MÁS VENDIDO|MAS VENDIDO",
                texto,
                re.IGNORECASE,
            )
        )

        if tiene_precio and tiene_imagen:
            candidatos.append((nodo, tiene_datos, len(texto)))
            if tiene_datos:
                return nodo

    if candidatos:
        candidatos.sort(key=lambda item: item[2])
        return candidatos[0][0]

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


def _es_precio_anterior(elemento):
    nodo = elemento
    for _ in range(6):
        if nodo is None or not isinstance(nodo, Tag):
            break

        clases = " ".join(nodo.get("class", []))
        attrs = " ".join(str(nodo.get(k, "")) for k in ("id", "data-testid", "aria-label"))
        marca = (clases + " " + attrs).lower()

        if getattr(nodo, "name", "") == "s":
            return True

        if any(x in marca for x in (
            "previous", "original", "strikethrough", "old-price",
            "price-before", "list-price"
        )):
            return True

        nodo = nodo.parent

    return False


def _primer_precio_actual(nodos, precio_anterior=""):
    for nodo in nodos:
        if _es_precio_anterior(nodo):
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
    Lee el precio ACTUAL mostrado en la misma tarjeta del producto.
    Nunca toma el precio tachado/original y nunca aproxima por texto libre.
    """
    precio_anterior = ""

    for selector in (
        ".andes-money-amount--previous",
        ".poly-price__original .andes-money-amount",
        ".ui-search-price__original-value .andes-money-amount",
        "[class*='original'] .andes-money-amount",
        "[class*='previous'] .andes-money-amount",
    ):
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

    # Prioridad: bloques semánticos de precio actual.
    for selector in (
        ".poly-price__current .andes-money-amount",
        ".ui-search-price__second-line .andes-money-amount",
        "[data-testid='price-part'] .andes-money-amount",
        "[class*='current'] .andes-money-amount",
        ".poly-component__price .andes-money-amount",
    ):
        try:
            nodos = contenedor.select(selector)
        except Exception:
            nodos = []

        precio = _primer_precio_actual(nodos, precio_anterior)
        if precio:
            return precio, precio_anterior

    # Último respaldo: primer money amount de ESA tarjeta que no sea anterior.
    # No se usa el texto completo ni la regla de "segundo precio si hay OFF".
    try:
        nodos = contenedor.select(".andes-money-amount")
    except Exception:
        nodos = []

    precio = _primer_precio_actual(nodos, precio_anterior)
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
    reales. No modifica link, precio ni foto: esos tres datos ya vienen unidos
    desde la misma tarjeta de Más vendidos.
    """
    imagen_original = datos.get("imagen_url", "")
    precio_original = datos.get("precio", "")
    url_original = datos.get("url_original", "")

    soup, _ = extraer_publicacion(url_original)

    if soup:
        atributos = obtener_atributos_reales_publicacion(soup, datos["nombre"])
        datos["atributos_visuales"] = atributos or atributos_desde_titulo(datos["nombre"])
    else:
        datos["atributos_visuales"] = atributos_desde_titulo(datos["nombre"])

    datos["imagen_url"] = imagen_original
    datos["precio"] = precio_original
    datos["url_original"] = url_original
    datos["precio_verificado"] = precio_original not in ("", "Precio no disponible")
    return datos


# =========================================================
# OBTENER PRODUCTOS
# =========================================================


# =========================================================
# RESULTADOS EMBEBIDOS DE MERCADO LIBRE
# =========================================================

def _iterar_diccionarios(obj):
    """Recorre cualquier JSON y devuelve todos sus diccionarios."""
    if isinstance(obj, dict):
        yield obj
        for valor in obj.values():
            yield from _iterar_diccionarios(valor)
    elif isinstance(obj, list):
        for valor in obj:
            yield from _iterar_diccionarios(valor)


def _cargar_json_de_script(texto):
    """
    Mercado Libre puede incrustar JSON puro o una asignación JS que contiene
    un objeto JSON. Devuelve todos los objetos que pueda decodificar sin
    ejecutar JavaScript.
    """
    if not texto:
        return []

    texto = texto.strip()
    resultados = []

    # JSON puro.
    try:
        resultados.append(json.loads(texto))
        return resultados
    except Exception:
        pass

    # Asignaciones tipo window.__STATE__ = {...};
    decoder = json.JSONDecoder()
    posiciones = [i for i, ch in enumerate(texto) if ch in "{["]
    # Probar solo los primeros comienzos razonables para no hacer un O(n²)
    # sobre scripts gigantes.
    for pos in posiciones[:30]:
        try:
            obj, _ = decoder.raw_decode(texto[pos:])
            resultados.append(obj)
            break
        except Exception:
            continue

    return resultados


def _extraer_item_id_dict(d):
    for clave in ("item_id", "itemId", "itemID"):
        valor = d.get(clave)
        if isinstance(valor, str) and re.fullmatch(r"MLA\d{7,}", valor):
            return valor

    # Algunos resultados usan simplemente id para el item. Solo se acepta si
    # el mismo objeto también parece un resultado comercial (precio/título).
    valor = d.get("id")
    if (
        isinstance(valor, str)
        and re.fullmatch(r"MLA\d{9,}", valor)
        and any(k in d for k in ("price", "title", "permalink", "thumbnail"))
    ):
        return valor

    return ""


def _extraer_catalog_id_dict(d):
    for clave in (
        "catalog_product_id", "catalogProductId", "catalog_product",
        "product_id", "productId"
    ):
        valor = d.get(clave)
        if isinstance(valor, str) and re.fullmatch(r"MLA\d{6,}", valor):
            return valor
        if isinstance(valor, dict):
            for sub in ("id", "product_id"):
                v = valor.get(sub)
                if isinstance(v, str) and re.fullmatch(r"MLA\d{6,}", v):
                    return v
    return ""


def _extraer_user_product_id_dict(d):
    for clave in ("user_product_id", "userProductId"):
        valor = d.get(clave)
        if isinstance(valor, str) and re.fullmatch(r"MLAU\d+", valor):
            return valor
    return ""


def _precio_numerico_desde_valor(valor):
    if isinstance(valor, (int, float)) and valor > 0:
        return float(valor)

    if isinstance(valor, str):
        return _normalizar_numero_precio(valor)

    if isinstance(valor, dict):
        # Solo precio ACTUAL. Nunca original/list/previous.
        for clave in ("amount", "value", "current_price", "currentPrice"):
            if clave in valor:
                n = _precio_numerico_desde_valor(valor.get(clave))
                if n:
                    return n
    return None


def _extraer_precio_actual_dict(d):
    # Prioridad a nombres explícitos de precio actual.
    for clave in ("price", "current_price", "currentPrice", "sale_price", "salePrice"):
        if clave in d:
            n = _precio_numerico_desde_valor(d.get(clave))
            if n:
                return n

    # Estructuras anidadas comunes de polycards.
    for clave in ("prices", "price_data", "priceData"):
        bloque = d.get(clave)
        if isinstance(bloque, dict):
            for sub in ("price", "current_price", "currentPrice", "sale_price", "amount"):
                if sub in bloque:
                    n = _precio_numerico_desde_valor(bloque.get(sub))
                    if n:
                        return n

    return None


def _extraer_titulo_dict(d):
    for clave in ("title", "name"):
        valor = d.get(clave)
        if isinstance(valor, str):
            valor = limpiar_texto(valor)
            if 5 <= len(valor) <= 250:
                return valor
    return ""


def _extraer_imagen_dict(d):
    candidatos = []

    for clave in ("thumbnail", "thumbnail_url", "thumbnailUrl", "image", "picture"):
        valor = d.get(clave)
        if isinstance(valor, str):
            candidatos.append(valor)
        elif isinstance(valor, dict):
            for sub in ("url", "secure_url", "src"):
                v = valor.get(sub)
                if isinstance(v, str):
                    candidatos.append(v)

    pictures = d.get("pictures")
    if isinstance(pictures, list):
        for pic in pictures[:3]:
            if isinstance(pic, str):
                candidatos.append(pic)
            elif isinstance(pic, dict):
                for sub in ("url", "secure_url", "src"):
                    v = pic.get(sub)
                    if isinstance(v, str):
                        candidatos.append(v)

    for url in candidatos:
        if not isinstance(url, str):
            continue
        url = url.replace("\\/", "/")
        if url.startswith("//"):
            url = "https:" + url
        if not url.startswith("http"):
            continue
        inferior = url.lower()
        if any(x in inferior for x in ("logo", "icon", "sprite", "favicon")):
            continue
        if "mlstatic" in inferior or "http" in inferior:
            return url

    return ""


def extraer_resultados_embebidos(soup):
    """
    Extrae el item_id, precio y demás datos del array de resultados que
    Mercado Libre incrusta en la propia página. Esto evita depender de que el
    href visible de la tarjeta sea /p/MLA... (catálogo) o una publicación.
    """
    resultados = []
    vistos = set()

    for script in soup.find_all("script"):
        texto = script.string or script.get_text("", strip=False)
        if not texto or "MLA" not in texto:
            continue

        for raiz in _cargar_json_de_script(texto):
            for d in _iterar_diccionarios(raiz):
                item_id = _extraer_item_id_dict(d)
                if not item_id or item_id in vistos:
                    continue

                precio_num = _extraer_precio_actual_dict(d)
                titulo = _extraer_titulo_dict(d)
                catalog_id = _extraer_catalog_id_dict(d)
                user_product_id = _extraer_user_product_id_dict(d)
                imagen = _extraer_imagen_dict(d)

                # Necesitamos al menos precio y algún dato que permita asociar
                # el item con una tarjeta concreta.
                if precio_num is None:
                    continue
                if not (catalog_id or user_product_id or titulo):
                    continue

                vistos.add(item_id)
                resultados.append({
                    "item_id": item_id,
                    "catalog_product_id": catalog_id,
                    "user_product_id": user_product_id,
                    "precio": _formatear_precio(precio_num),
                    "precio_num": precio_num,
                    "titulo": titulo,
                    "imagen_url": imagen,
                })

    print("Resultados embebidos con item_id + precio:", len(resultados))
    return resultados


def _catalog_id_desde_url(url):
    m = re.search(r"/p/(MLA\d+)", url or "", re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _user_product_id_desde_url(url):
    m = re.search(r"/up/(MLAU\d+)", url or "", re.IGNORECASE)
    return m.group(1).upper() if m else ""


def _titulo_normalizado_para_match(texto):
    texto = limpiar_texto(texto).lower()
    texto = re.sub(r"[^a-z0-9áéíóúüñ ]+", " ", texto)
    return re.sub(r"\s+", " ", texto).strip()


def _buscar_resultado_para_tarjeta(datos_tarjeta, resultados_embebidos):
    url = datos_tarjeta.get("url_original", "")
    catalog_id = _catalog_id_desde_url(url)
    user_product_id = _user_product_id_desde_url(url)

    if catalog_id:
        candidatos = [
            r for r in resultados_embebidos
            if r.get("catalog_product_id") == catalog_id
        ]
        if candidatos:
            return candidatos[0]

    if user_product_id:
        candidatos = [
            r for r in resultados_embebidos
            if r.get("user_product_id") == user_product_id
        ]
        if candidatos:
            return candidatos[0]

    # Último respaldo: título casi idéntico.
    titulo = _titulo_normalizado_para_match(datos_tarjeta.get("nombre", ""))
    if titulo:
        for r in resultados_embebidos:
            rt = _titulo_normalizado_para_match(r.get("titulo", ""))
            if rt and (rt == titulo or rt in titulo or titulo in rt):
                return r

    return None




def _extraer_item_id_del_contenedor(contenedor, url=""):
    """
    Respaldo muy conservador: busca un item_id explícito dentro del HTML de
    LA MISMA tarjeta. No confunde el MLA del catálogo /p/MLA... con el item,
    porque solo acepta IDs asociados a item_id, wid o data-item-id.
    """
    partes = [url or ""]
    try:
        partes.append(str(contenedor))
    except Exception:
        pass

    texto = requests.utils.unquote(" ".join(partes)).replace("&quot;", '"')

    patrones = [
        r"pdp_filters[^\s\"'<>]*item[_-]?id[:=](MLA\d{7,})",
        r"(?:^|[?&#])wid=(MLA\d{7,})",
        r"[\"']item[_-]?id[\"']\s*[:=]\s*[\"'](MLA\d{7,})[\"']",
        r"data-item-id=[\"'](MLA\d{7,})[\"']",
        r"data-id=[\"'](MLA\d{9,})[\"']",
    ]

    for patron in patrones:
        m = re.search(patron, texto, re.IGNORECASE)
        if m:
            return m.group(1).upper()

    return ""

def _url_exacta_con_item(url_base, item_id):
    """
    Conserva la página de producto (/p o /up), pero fija la publicación
    exacta mediante pdp_filters=item_id y wid. Mercado Libre usa esta forma
    en los links compartidos para identificar una oferta concreta.
    """
    partes = urlsplit(url_base)
    query = dict(parse_qsl(partes.query, keep_blank_values=True))
    query["pdp_filters"] = f"item_id:{item_id}"
    query["wid"] = item_id
    nueva_query = urlencode(query, doseq=True)
    return urlunsplit((partes.scheme, partes.netloc, partes.path, nueva_query, ""))


def cargar_historial_publicados():
    if not HISTORIAL_PATH.exists():
        return set()

    ids = set()
    for linea in HISTORIAL_PATH.read_text(encoding="utf-8").splitlines():
        linea = linea.strip().upper()
        if re.fullmatch(r"MLA\d{7,}", linea):
            ids.add(linea)
    return ids


def guardar_historial_publicados(productos):
    ids = cargar_historial_publicados()
    for producto in productos:
        item_id = limpiar_texto(producto.get("item_id", "")).upper()
        if re.fullmatch(r"MLA\d{7,}", item_id):
            ids.add(item_id)

    HISTORIAL_PATH.write_text(
        "\n".join(sorted(ids)) + ("\n" if ids else ""),
        encoding="utf-8",
    )
    print("✅ historial_publicados.txt actualizado:", len(ids), "IDs")


def _es_url_mas_vendidos_general(url):
    """Acepta solo la sección general de Más vendidos, sin categorías."""
    try:
        partes = urlsplit(url)
        path = partes.path.rstrip("/").lower()
        return (
            "mercadolibre.com.ar" in partes.netloc.lower()
            and path == "/mas-vendidos"
        )
    except Exception:
        return False


def _urls_mas_vendidos_misma_seccion(soup, base_url):
    """
    Busca enlaces de continuación/paginación de la MISMA sección general
    de Más vendidos. Nunca entra en /mas-vendidos/MLA... (categorías).
    """
    urls = []
    vistos = set()

    for enlace in soup.find_all("a", href=True):
        href = limpiar_url(enlace.get("href"))
        if not href:
            continue
        absoluta = urljoin(base_url, href)
        if not _es_url_mas_vendidos_general(absoluta):
            continue

        partes = urlsplit(absoluta)
        limpia = urlunsplit((partes.scheme or "https", partes.netloc, partes.path, partes.query, ""))
        if limpia != base_url and limpia not in vistos:
            vistos.add(limpia)
            urls.append(limpia)

    return urls


def _extraer_productos_de_mas_vendidos(url_pagina):
    """Extrae publicaciones exactas de la sección general de Más vendidos."""
    response = safe_get(url_pagina, timeout=30)
    print("HTTP Más vendidos:", response.status_code, "|", url_pagina)
    soup = BeautifulSoup(response.text, "html.parser")
    resultados_embebidos = extraer_resultados_embebidos(soup)
    print("Resultados embebidos con item_id + precio:", len(resultados_embebidos))

    encontrados = {}
    for enlace in soup.find_all("a", href=True):
        url = limpiar_url(enlace.get("href"))
        if not es_producto(url) or "mas-vendidos" in url:
            continue

        contenedor = encontrar_contenedor(enlace)
        if not contenedor:
            continue

        tarjeta = extraer_datos_tarjeta(enlace, contenedor)
        exacto = _buscar_resultado_para_tarjeta(tarjeta, resultados_embebidos)

        if exacto:
            item_id = exacto.get("item_id", "")
            precio = exacto.get("precio", "")
            if exacto.get("imagen_url"):
                tarjeta["imagen_url"] = exacto["imagen_url"]
            if exacto.get("titulo"):
                tarjeta["nombre"] = exacto["titulo"]
        else:
            item_id = _extraer_item_id_del_contenedor(contenedor, url)
            precio = tarjeta.get("precio", "")

        item_id = limpiar_texto(item_id).upper()
        if not re.fullmatch(r"MLA\d{7,}", item_id):
            continue
        if not precio or precio == "Precio no disponible":
            continue
        if not tarjeta.get("imagen_url"):
            continue

        tarjeta["item_id"] = item_id
        tarjeta["precio"] = precio
        tarjeta["url_original"] = _url_exacta_con_item(url, item_id)
        encontrados.setdefault(item_id, tarjeta)

    return encontrados, _urls_mas_vendidos_misma_seccion(soup, url_pagina)


def _urls_fuentes_ampliadas():
    """
    Fuentes públicas para conseguir variedad SIN repetir publicaciones.
    Primero conserva Más Vendidos y Ofertas. Además usa búsquedas amplias por
    categorías de alta rotación. El historial manda: un item ya publicado no
    vuelve a entrar en la tanda normal.
    """
    consultas = [
        "tecnologia", "celulares", "hogar", "cocina", "herramientas",
        "electrodomesticos", "computacion", "audio", "deportes", "calzado",
        "indumentaria", "belleza", "juguetes", "bebes", "mascotas",
        "accesorios auto", "motos", "jardin", "oficina", "iluminacion",
    ]
    urls = [URL_MAS_VENDIDOS, URL_OFERTAS]
    urls.extend(_url_busqueda_ml(q) for q in consultas)
    return urls


def _extraer_productos_pagina_generica(url_pagina, limite=80):
    """Extrae publicaciones válidas de una página pública de ML."""
    response = safe_get(url_pagina, timeout=30)
    print("HTTP fuente:", response.status_code, "|", url_pagina)
    soup = BeautifulSoup(response.text, "html.parser")
    resultados_embebidos = extraer_resultados_embebidos(soup)
    encontrados = {}

    for enlace in soup.find_all("a", href=True):
        url = limpiar_url(enlace.get("href"))
        if not es_producto(url):
            continue

        contenedor = encontrar_contenedor(enlace)
        if not contenedor:
            continue

        tarjeta = extraer_datos_tarjeta(enlace, contenedor)
        exacto = _buscar_resultado_para_tarjeta(tarjeta, resultados_embebidos)

        if exacto:
            item_id = limpiar_texto(exacto.get("item_id", "")).upper()
            precio = exacto.get("precio", "")
            if exacto.get("imagen_url"):
                tarjeta["imagen_url"] = exacto["imagen_url"]
            if exacto.get("titulo"):
                tarjeta["nombre"] = exacto["titulo"]
        else:
            item_id = _extraer_item_id_del_contenedor(contenedor, url)
            precio = tarjeta.get("precio", "")

        if not re.fullmatch(r"MLA\d{7,}", item_id):
            continue
        if not precio or precio == "Precio no disponible":
            continue
        if not tarjeta.get("imagen_url"):
            continue

        tarjeta["item_id"] = item_id
        tarjeta["precio"] = precio
        tarjeta["url_original"] = _url_exacta_con_item(url, item_id)
        encontrados.setdefault(item_id, tarjeta)
        if len(encontrados) >= limite:
            break

    return encontrados


def obtener_productos_base():
    """
    TANDA NORMAL: obtiene exactamente 10 publicaciones NUEVAS.
    Nunca rellena con productos del historial. Si una fuente no alcanza,
    continúa con otras fuentes públicas de Mercado Libre.
    """
    print("--- BUSCANDO 10 PRODUCTOS NUEVOS SIN REPETIR ---")
    historial = cargar_historial_publicados()
    print("Publicaciones ya usadas en el historial:", len(historial))

    nuevos = {}
    fuentes = _urls_fuentes_ampliadas()

    for url_pagina in fuentes:
        if len(nuevos) >= CANTIDAD_PRODUCTOS:
            break
        try:
            if _es_url_mas_vendidos_general(url_pagina):
                encontrados, _ = _extraer_productos_de_mas_vendidos(url_pagina)
            else:
                encontrados = _extraer_productos_pagina_generica(url_pagina)
        except Exception as e:
            print("AVISO: no se pudo leer fuente", url_pagina, "|", e)
            continue

        for item_id, tarjeta in encontrados.items():
            if item_id in historial or item_id in nuevos:
                continue
            nuevos[item_id] = tarjeta

        print("Nuevos únicos acumulados:", len(nuevos))

    if len(nuevos) < CANTIDAD_PRODUCTOS:
        raise RuntimeError(
            f"Se encontraron {len(nuevos)} productos nuevos y se necesitan "
            f"{CANTIDAD_PRODUCTOS}. NO se usarán repetidos."
        )

    candidatos = list(nuevos.values())
    candidatos.sort(key=_puntaje_producto_demanda, reverse=True)
    seleccionados = candidatos[:CANTIDAD_PRODUCTOS]

    resultado = []
    for numero, producto in enumerate(seleccionados, start=1):
        print(
            f"NUEVO {numero}. item={producto['item_id']} | "
            f"{producto['nombre']} | precio={producto['precio']}"
        )
        resultado.append(enriquecer_solo_textos_reales(producto))

    return resultado


# =========================================================
# NUEVO: DEMANDA REAL + BÚSQUEDA DIRECTA EN MERCADO LIBRE
# =========================================================

def _leer_demanda_pendiente():
    """Lee necesidades detectadas sin volver a procesar la misma línea."""
    if not DEMANDA_PATH.exists():
        return []

    procesadas = set()
    if DEMANDA_PROCESADA_PATH.exists():
        procesadas = {
            limpiar_texto(x)
            for x in DEMANDA_PROCESADA_PATH.read_text(encoding="utf-8").splitlines()
            if limpiar_texto(x)
        }

    pendientes = []
    for linea in DEMANDA_PATH.read_text(encoding="utf-8").splitlines():
        linea = limpiar_texto(linea)
        if not linea or linea.startswith("#") or linea in procesadas:
            continue

        partes = [limpiar_texto(x) for x in linea.split("|", 1)]
        consulta = partes[0]
        origen = partes[1] if len(partes) > 1 else ""
        if len(consulta) >= 3:
            pendientes.append({"linea": linea, "consulta": consulta, "origen": origen})

    return pendientes


def _url_busqueda_ml(consulta):
    # Mercado Libre acepta búsquedas públicas por /listado?q=...
    return "https://listado.mercadolibre.com.ar/_NoIndex_True?" + urlencode({"q": consulta})


def _puntaje_producto_demanda(producto):
    """Ordena sin inventar datos: ventas, rating, descuento y cuotas visibles."""
    puntos = 0.0
    vendidos = limpiar_texto(producto.get("vendidos", "")).lower()
    m = re.search(r"([\d\.]+)\s*(mil)?", vendidos)
    if m:
        try:
            n = float(m.group(1).replace(".", ""))
            if m.group(2):
                n *= 1000
            puntos += min(n / 100.0, 500.0)
        except Exception:
            pass

    try:
        puntos += float(producto.get("rating") or 0) * 15
    except Exception:
        pass

    m = re.search(r"(\d{1,2})%", producto.get("descuento", ""))
    if m:
        puntos += int(m.group(1)) * 2

    if producto.get("cuotas"):
        puntos += 20
    if producto.get("precio") and producto.get("precio") != "Precio no disponible":
        puntos += 10
    if producto.get("imagen_url"):
        puntos += 10
    return puntos


def _extraer_busqueda_publica(consulta, limite=12):
    """Busca exactamente lo pedido en la web pública de Mercado Libre."""
    url_busqueda = _url_busqueda_ml(consulta)
    print("🔎 DEMANDA: buscando en Mercado Libre:", consulta)
    response = safe_get(url_busqueda, timeout=30)
    soup = BeautifulSoup(response.text, "html.parser")
    resultados_embebidos = extraer_resultados_embebidos(soup)

    encontrados = {}
    for enlace in soup.find_all("a", href=True):
        url = limpiar_url(enlace.get("href"))
        if not es_producto(url):
            continue

        contenedor = encontrar_contenedor(enlace)
        if not contenedor:
            continue

        tarjeta = extraer_datos_tarjeta(enlace, contenedor)
        exacto = _buscar_resultado_para_tarjeta(tarjeta, resultados_embebidos)
        if exacto:
            item_id = limpiar_texto(exacto.get("item_id", "")).upper()
            precio = exacto.get("precio", "")
            if exacto.get("imagen_url"):
                tarjeta["imagen_url"] = exacto["imagen_url"]
            if exacto.get("titulo"):
                tarjeta["nombre"] = exacto["titulo"]
        else:
            item_id = _extraer_item_id_del_contenedor(contenedor, url)
            precio = tarjeta.get("precio", "")

        if not re.fullmatch(r"MLA\d{7,}", item_id):
            continue
        if not precio or precio == "Precio no disponible" or not tarjeta.get("imagen_url"):
            continue

        tarjeta["item_id"] = item_id
        tarjeta["precio"] = precio
        tarjeta["url_original"] = _url_exacta_con_item(url, item_id)
        tarjeta["consulta_demanda"] = consulta
        encontrados.setdefault(item_id, tarjeta)
        if len(encontrados) >= limite:
            break

    productos = list(encontrados.values())
    productos.sort(key=_puntaje_producto_demanda, reverse=True)
    return productos


def obtener_productos_demanda(maximo=10):
    """Convierte necesidades ya detectadas en productos concretos para publicar."""
    pendientes = _leer_demanda_pendiente()
    if not pendientes:
        return [], []

    historial = cargar_historial_publicados()
    elegidos = []
    ids = set()
    lineas_resueltas = []
    reporte = []

    for necesidad in pendientes:
        if len(elegidos) >= maximo:
            break
        try:
            candidatos = _extraer_busqueda_publica(necesidad["consulta"])
        except Exception as e:
            print("AVISO demanda:", necesidad["consulta"], "|", e)
            continue

        # DEMANDA URGENTE: jamás reutiliza una publicación del historial.
        candidatos = [
            p for p in candidatos
            if p.get("item_id") not in historial and p.get("item_id") not in ids
        ]
        candidatos.sort(key=_puntaje_producto_demanda, reverse=True)
        candidato = candidatos[0] if candidatos else None
        if not candidato:
            continue

        candidato["origen_demanda"] = necesidad.get("origen", "")
        candidato = enriquecer_solo_textos_reales(candidato)
        elegidos.append(candidato)
        ids.add(candidato["item_id"])
        lineas_resueltas.append(necesidad["linea"])
        reporte.append(
            f"{necesidad['consulta']} | {candidato['nombre']} | "
            f"{candidato['precio']} | {candidato['url_original']} | {necesidad.get('origen','')}"
        )

    if reporte:
        REPORTE_DEMANDA_PATH.write_text("\n".join(reporte) + "\n", encoding="utf-8")

    return elegidos, lineas_resueltas


def _marcar_demanda_procesada(lineas):
    if not lineas:
        return
    anteriores = []
    if DEMANDA_PROCESADA_PATH.exists():
        anteriores = DEMANDA_PROCESADA_PATH.read_text(encoding="utf-8").splitlines()
    conjunto = {limpiar_texto(x) for x in anteriores if limpiar_texto(x)}
    conjunto.update(limpiar_texto(x) for x in lineas if limpiar_texto(x))
    DEMANDA_PROCESADA_PATH.write_text("\n".join(sorted(conjunto)) + "\n", encoding="utf-8")


def obtener_productos():
    """Compatibilidad: la tanda normal siempre contiene 10 productos nuevos."""
    return obtener_productos_base()


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
# COLA URGENTE PARA AUTOMATE
# =========================================================

def guardar_urgentes(productos):
    """
    Genera archivos separados para demanda detectada. No pisa la tanda normal.
    El detector puede disparar este workflow en cuanto agregue demanda_detectada.txt;
    Automate podrá vigilar estos archivos y publicar cada urgente inmediatamente.
    """
    if not productos:
        return

    links, datos_txt, imagenes = [], [], []
    for numero, datos in enumerate(productos, start=1):
        archivo = crear_imagen_oferta(datos, 1000 + numero)
        links.append(datos["url_original"])
        nombre = datos["nombre"].replace("|", "-")
        precio = datos["precio"].replace("|", "-")
        cuotas = datos.get("cuotas", "").replace("|", "-")
        datos_txt.append(f"{nombre} | {precio} | {cuotas}")
        imagenes.append(f"{RAW_BASE}/{archivo}")

    Path("urgente_links.txt").write_text("\n".join(links), encoding="utf-8")
    Path("urgente_datos.txt").write_text("\n".join(datos_txt), encoding="utf-8")
    Path("urgente_imagenes.txt").write_text("\n".join(imagenes), encoding="utf-8")
    print("🚨 Cola urgente generada:", len(productos), "producto(s) nuevos")


# =========================================================
# MAIN
# =========================================================

def main():
    # 1) DEMANDA URGENTE: si existe, se prepara aparte y sin repetidos.
    urgentes, lineas_resueltas = obtener_productos_demanda(maximo=50)
    if urgentes:
        guardar_urgentes(urgentes)
        guardar_historial_publicados(urgentes)
        _marcar_demanda_procesada(lineas_resueltas)

    # 2) TANDA NORMAL: siempre 10 NUEVOS; nunca completa con repetidos.
    productos = obtener_productos_base()
    if len(productos) != CANTIDAD_PRODUCTOS:
        raise RuntimeError(
            f"La tanda normal debe tener {CANTIDAD_PRODUCTOS} productos nuevos; "
            f"se obtuvieron {len(productos)}."
        )

    print("Productos nuevos seleccionados:", len(productos))
    guardar_tanda(productos)
    guardar_historial_publicados(productos)
    print("✅ PROCESO COMPLETO FINALIZADO SIN REPETIDOS")


if __name__ == "__main__":
    main()
