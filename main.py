import os
import random
import re
import json
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
    datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
)

RAW_BASE = f"https://raw.githubusercontent.com/{REPO}/{RAMA}/ofertas"

ANCHO = 1122
ALTO = 1402


# =========================================================
# FUENTES
# =========================================================

def fuente(tamano, negrita=False):
    if negrita:
        candidatos = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
        ]
    else:
        candidatos = [
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/liberation2/LiberationSans-Regular.ttf",
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
# CONTENEDOR
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
# IMAGEN
# =========================================================

def obtener_url_imagen(contenedor):
    for imagen in contenedor.find_all("img"):
        for atributo in ["data-src", "data-lazy", "src"]:
            url = imagen.get(atributo)
            if url and url.startswith("http") and ".svg" not in url.lower():
                return url

        srcset = imagen.get("srcset")
        if srcset:
            urls = []
            for opcion in srcset.split(","):
                url = opcion.strip().split(" ")[0]
                if url.startswith("http"):
                    urls.append(url)
            if urls:
                return urls[-1]

    return ""


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


def recortar_borde_blanco(img):
    """
    Quita bordes blancos o casi blancos alrededor del producto para
    que no quede el cuadrado blanco que te molestaba.
    """
    if img is None:
        return None

    img = img.convert("RGBA")
    fondo = Image.new("RGBA", img.size, (255, 255, 255, 0))

    pix = img.load()
    nueva = Image.new("RGBA", img.size)
    nueva_pix = nueva.load()

    for y in range(img.height):
        for x in range(img.width):
            r, g, b, a = pix[x, y]

            if a == 0:
                nueva_pix[x, y] = (255, 255, 255, 0)
                continue

            # Si es casi blanco, lo vuelve transparente
            if r > 245 and g > 245 and b > 245:
                nueva_pix[x, y] = (255, 255, 255, 0)
            else:
                nueva_pix[x, y] = (r, g, b, a)

    bbox = nueva.getbbox()
    if bbox:
        nueva = nueva.crop(bbox)

    return nueva


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


def obtener_precios(contenedor, texto, descuento):
    precio = ""
    precio_anterior = ""

    anteriores = [
        ".andes-money-amount--previous",
        ".poly-price__original .andes-money-amount",
        ".ui-search-price__original-value .andes-money-amount",
        "[class*='original'] .andes-money-amount",
        "[class*='previous'] .andes-money-amount",
    ]

    for selector in anteriores:
        elemento = contenedor.select_one(selector)
        valor = leer_money_amount(elemento)
        if valor:
            precio_anterior = valor
            break

    actuales = [
        ".poly-price__current .andes-money-amount",
        ".ui-search-price__second-line .andes-money-amount",
        "[class*='current'] .andes-money-amount",
    ]

    for selector in actuales:
        elemento = contenedor.select_one(selector)
        valor = leer_money_amount(elemento)
        if valor:
            precio = valor
            break

    if not precio:
        valores = []
        for elemento in contenedor.select(".andes-money-amount"):
            valor = leer_money_amount(elemento)
            if valor and valor not in valores:
                valores.append(valor)

        if valores:
            if descuento and len(valores) >= 2:
                if not precio_anterior:
                    precio_anterior = valores[0]
                precio = valores[1]
            else:
                precio = valores[0]

    if not precio:
        importes = extraer_importes_texto(texto)
        if importes:
            if descuento and len(importes) >= 2:
                if not precio_anterior:
                    precio_anterior = importes[0]
                precio = importes[1]
            else:
                precio = importes[0]

    if not precio:
        precio = "Precio no disponible"

    return precio, precio_anterior


# =========================================================
# EXTRAER DATOS DE MÁS VENDIDOS
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
        cuotas = "Consultar cuotas"

    ranking = ""
    match = re.search(r"(\d{1,2})\s*[º°]\s*(?:MÁS|MAS)\s+VENDIDO", texto, re.IGNORECASE)
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
        re.IGNORECASE
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
    }


# =========================================================
# SCRAPEO DE LA PUBLICACIÓN REAL
# =========================================================

def extraer_json_ld_producto(soup):
    for script in soup.find_all("script", type="application/ld+json"):
        contenido = script.string or script.get_text(strip=True)
        if not contenido:
            continue

        try:
            data = json.loads(contenido)
        except Exception:
            continue

        candidatos = data if isinstance(data, list) else [data]

        for item in candidatos:
            if not isinstance(item, dict):
                continue
            tipo = item.get("@type", "")
            if isinstance(tipo, list):
                tipos = [str(t).lower() for t in tipo]
            else:
                tipos = [str(tipo).lower()]

            if "product" in tipos:
                return item

    return {}


def extraer_texto_publicacion(url):
    try:
        response = safe_get(url, timeout=30)
        soup = BeautifulSoup(response.text, "html.parser")
        return soup, limpiar_texto(soup.get_text(" ", strip=True))
    except Exception as e:
        print("ERROR publicación:", url, e)
        return None, ""


def extraer_titulo_publicacion(soup, fallback=""):
    if not soup:
        return fallback

    for selector in [
        "h1.ui-pdp-title",
        "h1",
        "meta[property='og:title']",
    ]:
        try:
            if selector.startswith("meta"):
                meta = soup.select_one(selector)
                if meta and meta.get("content"):
                    texto = limpiar_texto(meta["content"])
                    if texto:
                        return texto
            else:
                nodo = soup.select_one(selector)
                if nodo:
                    texto = limpiar_texto(nodo.get_text(" ", strip=True))
                    if texto:
                        return texto
        except Exception:
            pass

    return fallback


def extraer_precio_publicacion(soup, texto_completo, fallback="Precio no disponible"):
    if not soup:
        return fallback, ""

    # precio actual
    precio = ""
    precio_anterior = ""

    for selector in [
        ".ui-pdp-price__second-line .andes-money-amount",
        ".ui-pdp-price__main-container .andes-money-amount",
        ".andes-money-amount",
    ]:
        for nodo in soup.select(selector):
            valor = leer_money_amount(nodo)
            if valor:
                if not precio:
                    precio = valor
                elif not precio_anterior and valor != precio:
                    precio_anterior = valor
                if precio:
                    break
        if precio:
            break

    if not precio:
        importes = extraer_importes_texto(texto_completo)
        if importes:
            precio = importes[0]
            if len(importes) > 1:
                precio_anterior = importes[1]

    if not precio:
        precio = fallback

    return precio, precio_anterior


def extraer_imagen_publicacion(soup, fallback=""):
    if not soup:
        return fallback

    for selector in [
        "meta[property='og:image']",
        "figure img",
        ".ui-pdp-gallery__figure img",
        ".ui-pdp-image img",
        "img",
    ]:
        try:
            if selector.startswith("meta"):
                nodo = soup.select_one(selector)
                if nodo and nodo.get("content"):
                    url = limpiar_url(nodo["content"])
                    if url:
                        return url
            else:
                for nodo in soup.select(selector):
                    for attr in ["src", "data-zoom", "data-src"]:
                        url = nodo.get(attr)
                        if url and url.startswith("http") and ".svg" not in url.lower():
                            return url
        except Exception:
            pass

    return fallback


def extraer_ranking_real(texto_completo, fallback=""):
    patrones = [
        r"(\d{1,2}\s*[º°]\s*(?:MÁS|MAS)\s+VENDIDO)",
        r"((?:TOP|Top)\s*\d+)",
    ]

    for patron in patrones:
        m = re.search(patron, texto_completo, re.IGNORECASE)
        if m:
            return limpiar_texto(m.group(1).upper())

    return fallback


def extraer_cuotas_reales(texto_completo, fallback="Consultar cuotas"):
    patrones = [
        r"((?:Mismo precio(?: en)?\s+)?\d{1,2}\s+cuotas(?:\s+sin\s+inter[eé]s)?(?:\s+de\s+\$\s*[\d\.\,]+)?)",
        r"(\d{1,2}\s+cuotas(?:\s+sin\s+inter[eé]s)?)",
        r"(Consultar cuotas)",
    ]

    for patron in patrones:
        m = re.search(patron, texto_completo, re.IGNORECASE)
        if m:
            return limpiar_texto(m.group(1))

    return fallback


def extraer_atributos_reales(soup, texto_completo, nombre_producto=""):
    """
    Devuelve hasta 3 textos reales de la publicación.
    """
    candidatos = []

    # 1) atributos visibles por tabla/listas
    selectores = [
        ".ui-vpp-highlighted-specs__features li",
        ".ui-pdp-specs__table tr",
        ".ui-pdp-color--BLACK li",
        ".ui-pdp-variations__picker li",
        ".ui-pdp-description__content",
        ".ui-pdp-highlights__content li",
        ".ui-pdp-container__row li",
        ".andes-table__row",
    ]

    for selector in selectores:
        try:
            nodos = soup.select(selector)
        except Exception:
            nodos = []

        for nodo in nodos:
            texto = limpiar_texto(nodo.get_text(" ", strip=True))

            if not texto:
                continue
            if len(texto) < 4 or len(texto) > 60:
                continue
            if "$" in texto:
                continue
            if "mercado libre" in texto.lower():
                continue
            if texto not in candidatos:
                candidatos.append(texto)

    # 2) inferir desde el nombre si faltan
    nombre = nombre_producto.lower()

    inferidos = []
    reglas = [
        ("deportiv", "Diseño deportivo"),
        ("livian", "Livianas y cómodas"),
        ("comod", "Livianas y cómodas"),
        ("air", "Amortiguación de aire"),
        ("amortigu", "Amortiguación de aire"),
        ("bluetooth", "Conectividad bluetooth"),
        ("inalámbr", "Uso inalámbrico"),
        ("inalambr", "Uso inalámbrico"),
        ("smart", "Tecnología inteligente"),
        ("full", "Stock Full"),
        ("8 jarros", "8 jarros"),
        ("1,4 litros", "1,4 litros"),
        ("1.4 litros", "1,4 litros"),
        ("verde", "Color verde"),
    ]

    for clave, valor in reglas:
        if clave in nombre and valor not in inferidos:
            inferidos.append(valor)

    # limpiar y elegir
    resultado = []
    for texto in candidatos + inferidos:
        texto = limpiar_texto(texto)
        if not texto:
            continue

        # partir si viene con "clave valor"
        texto = texto.replace("  ", " ")
        if len(texto) > 26:
            # intenta acortarlo
            partes = texto.split()
            texto = " ".join(partes[:4])

        if texto not in resultado:
            resultado.append(texto)

        if len(resultado) >= 3:
            break

    return resultado[:3]


def enriquecer_con_publicacion_real(datos):
    url = datos["url_original"]
    soup, texto_completo = extraer_texto_publicacion(url)

    if not soup:
        datos["atributos_visuales"] = []
        return datos

    json_ld = extraer_json_ld_producto(soup)

    titulo_real = extraer_titulo_publicacion(soup, fallback=datos["nombre"])
    if titulo_real:
        datos["nombre"] = titulo_real

    precio_real, precio_anterior_real = extraer_precio_publicacion(
        soup,
        texto_completo,
        fallback=datos["precio"],
    )
    if precio_real:
        datos["precio"] = precio_real
    if precio_anterior_real:
        datos["precio_anterior"] = precio_anterior_real

    imagen_real = extraer_imagen_publicacion(soup, fallback=datos["imagen_url"])
    if imagen_real:
        datos["imagen_url"] = imagen_real

    ranking_real = extraer_ranking_real(texto_completo, fallback=datos.get("ranking", ""))
    if ranking_real:
        datos["ranking"] = ranking_real

    cuotas_reales = extraer_cuotas_reales(texto_completo, fallback=datos.get("cuotas", "Consultar cuotas"))
    if cuotas_reales:
        datos["cuotas"] = cuotas_reales

    atributos = extraer_atributos_reales(
        soup,
        texto_completo,
        nombre_producto=datos["nombre"],
    )

    # Si JSON-LD trae nombre distinto o imagen, usa lo mejor
    if isinstance(json_ld, dict):
        if not datos["nombre"] and json_ld.get("name"):
            datos["nombre"] = limpiar_texto(json_ld.get("name"))
        if not datos["imagen_url"] and json_ld.get("image"):
            imagen = json_ld.get("image")
            if isinstance(imagen, list) and imagen:
                datos["imagen_url"] = imagen[0]
            elif isinstance(imagen, str):
                datos["imagen_url"] = imagen

    datos["atributos_visuales"] = atributos
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
        if datos["precio"] != "Precio no disponible":
            puntos += 6
        if datos["imagen_url"]:
            puntos += 4
        if datos["descuento"]:
            puntos += 1
        if datos["cuotas"] != "Consultar cuotas":
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

    validos = [
        producto
        for producto in productos
        if (
            producto["precio"] != "Precio no disponible"
            and producto["imagen_url"]
            and producto["nombre"] != "Producto Mercado Libre"
        )
    ]

    print("Productos con precio válido:", len(validos))

    if len(validos) >= CANTIDAD_PRODUCTOS:
        candidatos = validos[:40]
    else:
        candidatos = productos[:40]

    if len(candidatos) >= CANTIDAD_PRODUCTOS:
        seleccionados = random.sample(candidatos, CANTIDAD_PRODUCTOS)
    else:
        seleccionados = candidatos

    enriquecidos = []
    for numero, producto in enumerate(seleccionados, start=1):
        print(f"Enriqueciendo producto {numero}/{len(seleccionados)}...")
        producto = enriquecer_con_publicacion_real(producto)
        enriquecidos.append(producto)

    for numero, producto in enumerate(enriquecidos, start=1):
        print(
            f"{numero}. {producto['nombre']} | "
            f"{producto['precio']} | "
            f"{producto.get('cuotas', '')} | "
            f"{producto.get('ranking', '')}"
        )

    return enriquecidos


# =========================================================
# TEXTO
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
    for tamano in range(49, 31, -1):
        f = fuente(tamano, True)
        lineas = ajustar_texto(draw, texto, f, 920)
        if len(lineas) <= 2:
            return f, lineas

    f = fuente(31, True)
    return f, lineas_limitadas(draw, texto, f, 920, 2)


# =========================================================
# PLANTILLA APROBADA
# =========================================================

def cargar_plantilla(path):
    if not path.exists():
        raise FileNotFoundError(f"Falta {path.name}. Subila a la raíz del repositorio.")

    imagen = Image.open(path).convert("RGBA")

    if imagen.size != (ANCHO, ALTO):
        imagen = imagen.resize((ANCHO, ALTO), Image.LANCZOS)

    return imagen


def bloques_laterales_reales(datos):
    """
    Acá sale de la publicación real.
    Prioridad:
    1) ranking real
    2) cuotas reales
    3) atributos reales de la publicación
    """
    bloques = []

    if datos.get("ranking"):
        bloques.append(datos["ranking"])
    elif datos.get("vendidos"):
        bloques.append(datos["vendidos"])

    if datos.get("cuotas"):
        bloques.append(datos["cuotas"])

    for texto in datos.get("atributos_visuales", []):
        if texto and texto not in bloques:
            bloques.append(texto)

    # fallback si todavía faltan
    fallbacks = [
        "Producto destacado",
        "Consultar cuotas",
        "Oferta seleccionada",
    ]
    for f in fallbacks:
        if len(bloques) >= 3:
            break
        if f not in bloques:
            bloques.append(f)

    return bloques[:3]


def dibujar_datos_laterales(draw, datos):
    """
    La plantilla ya tiene los círculos e íconos del diseño aprobado.
    Sólo escribimos al lado con los datos reales.
    """
    textos = bloques_laterales_reales(datos)
    centros_y = [390, 510, 630]
    font_item = fuente(20, False)

    for cy, texto in zip(centros_y, textos):
        lineas = []

        # si el texto es muy largo, lo partimos
        for bloque in str(texto).split("\n"):
            lineas.extend(ajustar_texto(draw, bloque, font_item, 180))

        lineas = lineas[:3]
        if not lineas:
            lineas = [""]

        alto_total = len(lineas) * 24
        y = cy - alto_total // 2

        for linea in lineas:
            draw.text((156, y), linea, font=font_item, fill=(25, 25, 25))
            y += 24


def pegar_producto(imagen, producto):
    """
    Más grande y sin fondo blanco, para que se parezca más a la aprobada.
    """
    if producto is None:
        return

    producto = recortar_borde_blanco(producto)

    if producto is None:
        return

    area_x0 = 250
    area_y0 = 250
    area_x1 = 1000
    area_y1 = 770

    max_w = area_x1 - area_x0
    max_h = area_y1 - area_y0

    # agrandamos bastante más que antes
    ratio = min(max_w / producto.width, max_h / producto.height)
    ratio *= 1.08

    nuevo_w = int(producto.width * ratio)
    nuevo_h = int(producto.height * ratio)

    producto = producto.resize((nuevo_w, nuevo_h), Image.LANCZOS)

    x = area_x0 + ((area_x1 - area_x0) - producto.width) // 2
    y = area_y0 + ((area_y1 - area_y0) - producto.height) // 2

    imagen.paste(producto, (x, y), producto)


def dibujar_precio(draw, precio):
    texto = limpiar_texto(precio)

    for tamano in range(78, 54, -1):
        f = fuente(tamano, True)
        caja = draw.textbbox((0, 0), texto, font=f)
        ancho = caja[2] - caja[0]

        if ancho <= 760:
            x = (ANCHO - ancho) // 2
            draw.text((x, 968), texto, font=f, fill=(38, 110, 245))
            return


def crear_imagen_oferta(datos, numero):
    nombre_archivo = f"oferta_final_{numero:02d}_{VERSION}.png"
    salida = CARPETA_OFERTAS / nombre_archivo

    imagen = cargar_plantilla(PLANTILLA_OFERTA_PATH)
    draw = ImageDraw.Draw(imagen)

    # textos reales de la publicación
    dibujar_datos_laterales(draw, datos)

    producto = descargar_imagen(datos["imagen_url"])
    pegar_producto(imagen, producto)

    font_titulo, lineas = fuente_titulo(draw, datos["nombre"])
    y = 825

    for linea in lineas[:2]:
        draw.text((100, y), linea, font=font_titulo, fill=(8, 8, 8))
        caja = draw.textbbox((100, y), linea, font=font_titulo)
        y = caja[3] + 1

    dibujar_precio(draw, datos["precio"])

    imagen.convert("RGB").save(salida, "PNG", optimize=True)

    print("✅ Imagen creada con plantilla aprobada:", salida)
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
# GUARDAR ARCHIVOS
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

    # se genera aparte, sin tocar el flujo actual de Automate
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
