import os
import random
import re
import unicodedata
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
API_BASE = "https://api.mercadolibre.com"
CANTIDAD_PRODUCTOS = 10

DEMANDA_PATH = Path("demanda_detectada.txt")
DEMANDA_PROCESADA_PATH = Path("demanda_procesada.txt")
REPORTE_DEMANDA_PATH = Path("reporte_demanda.txt")

MELI_ACCESS_TOKEN = os.getenv("MELI_ACCESS_TOKEN", "").strip()

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
    partes = urlsplit(url)
    return urlunsplit((partes.scheme, partes.netloc, partes.path, partes.query, ""))


def _formatear_precio(numero):
    if numero is None:
        return ""
    try:
        numero = float(numero)
    except Exception:
        return ""
    if numero <= 0:
        return ""

    if abs(numero - round(numero)) < 0.001:
        entero = int(round(numero))
        return "$ " + f"{entero:,}".replace(",", ".")

    entero = int(numero)
    centavos = int(round((numero - entero) * 100))
    return "$ " + f"{entero:,}".replace(",", ".") + f",{centavos:02d}"


# =========================================================
# FILTRO DE PRODUCTOS NO APTOS PARA EL CANAL
# =========================================================

PALABRAS_ALCOHOL = (
    "cerveza", "beer", "vino", "wine", "fernet", "whisky", "whiskey",
    "vodka", "gin", "ginebra", "ron", "rum", "tequila", "champagne",
    "espumante", "licor", "aperitivo alcoholico", "aperitivo alcohólico",
    "sidra", "cognac", "coñac", "brandy", "vermouth", "vermú",
    "campari", "aperol", "heineken", "quilmes", "brahma",
    "stella artois", "corona", "budweiser"
)


def es_producto_permitido(producto):
    texto = " ".join([
        limpiar_texto(producto.get("nombre", "")),
        limpiar_texto(producto.get("url_original", "")),
    ]).lower()

    texto = re.sub(r"[^a-záéíóúüñ0-9]+", " ", texto)
    texto = " " + re.sub(r"\s+", " ", texto).strip() + " "

    for palabra in PALABRAS_ALCOHOL:
        p = re.sub(r"[^a-záéíóúüñ0-9]+", " ", palabra.lower()).strip()
        if p and f" {p} " in texto:
            return False
    return True


def safe_get(url, timeout=30):
    response = requests.get(url, headers=HEADERS, timeout=timeout)
    response.raise_for_status()
    return response


def api_get(endpoint, params=None, timeout=30):
    headers = {
        "Accept": "application/json",
        "User-Agent": HEADERS["User-Agent"],
    }
    token = os.getenv("MELI_ACCESS_TOKEN", "").strip() or MELI_ACCESS_TOKEN
    if token:
        headers["Authorization"] = f"Bearer {token}"

    url = endpoint if endpoint.startswith("http") else f"{API_BASE}{endpoint}"
    response = requests.get(url, headers=headers, params=params, timeout=timeout)
    response.raise_for_status()
    return response.json()


# =========================================================
# IMAGEN DEL PRODUCTO
# =========================================================

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
    if imagen is None:
        return None

    img = imagen.convert("RGBA")
    w, h = img.size

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
# ATRIBUTOS REALES DE LA PUBLICACIÓN
# =========================================================

def normalizar_atributo(texto):
    texto = limpiar_texto(texto)
    texto = re.sub(r"\s*:\s*", ": ", texto)
    palabras = texto.split()
    if len(palabras) > 7:
        texto = " ".join(palabras[:7])
    return texto.strip(" -–—:;")


def es_texto_util_atributo(texto, nombre_producto=""):
    texto = limpiar_texto(texto)
    if not texto:
        return False

    inferior = texto.lower()
    if len(texto) < 3 or len(texto) > 55:
        return False

    prohibidos = [
        "mercado libre", "mercado pago", "comprar", "oferta",
        "envío", "envio", "devolución", "devolucion", "stock",
        "cuotas", "medios de pago", "vendidos", "opiniones",
        "preguntas", "publicación", "publicacion", "marca genérica",
        "no aplica", "sin marca", "universal"
    ]
    if any(p in inferior for p in prohibidos):
        return False
    if "$" in texto or "%" in texto:
        return False
    if nombre_producto and limpiar_texto(nombre_producto).lower() == inferior:
        return False
    return True


def atributos_desde_titulo(titulo):
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
            texto = salida(m) if callable(salida) else salida
            texto = limpiar_texto(texto)
            if texto and texto.lower() not in [x.lower() for x in resultado]:
                resultado.append(texto)
            if len(resultado) >= 3:
                return resultado

    palabras = t.split()
    stop = {
        "para", "con", "sin", "de", "del", "la", "el", "los", "las",
        "y", "en", "un", "una", "por", "a", "modelo", "marca",
    }

    for palabra in palabras:
        limpia = palabra.strip(",.;:()[]-/")
        if len(limpia) < 4 or limpia.lower() in stop:
            continue
        if limpia.lower() in tl and limpia.lower() not in [x.lower() for x in resultado]:
            resultado.append(limpia.capitalize())
        if len(resultado) >= 3:
            break

    return resultado[:3]


def _extraer_atributos_item_api(item_json, titulo):
    resultado = []
    atributos = item_json.get("attributes") or []
    prioritarios = {"BRAND", "MODEL", "COLOR", "CAPACITY", "POWER", "MATERIAL", "VOLUME_CAPACITY", "WEIGHT"}

    for attr in atributos:
        if attr.get("id") in prioritarios:
            nombre = limpiar_texto(attr.get("name", ""))
            valor = limpiar_texto(attr.get("value_name", ""))
            if nombre and valor:
                texto = normalizar_atributo(f"{nombre}: {valor}")
                if es_texto_util_atributo(texto, titulo) and texto not in resultado:
                    resultado.append(texto)
            if len(resultado) >= 3:
                return resultado

    for attr in atributos:
        nombre = limpiar_texto(attr.get("name", ""))
        valor = limpiar_texto(attr.get("value_name", ""))
        if nombre and valor:
            texto = normalizar_atributo(f"{nombre}: {valor}")
            if es_texto_util_atributo(texto, titulo) and texto not in resultado:
                resultado.append(texto)
        if len(resultado) >= 3:
            return resultado

    if len(resultado) < 3:
        for extra in atributos_desde_titulo(titulo):
            if extra.lower() not in [x.lower() for x in resultado]:
                resultado.append(extra)
            if len(resultado) >= 3:
                break

    return resultado[:3]


def _mejor_imagen_api(item_json):
    pictures = item_json.get("pictures") or []
    if pictures and isinstance(pictures, list):
        pic = pictures[0]
        if isinstance(pic, dict):
            url = pic.get("secure_url") or pic.get("url") or ""
            if url:
                return url

    thumb = item_json.get("thumbnail") or ""
    if thumb:
        thumb = re.sub(r"-I(\.[a-zA-Z0-9]+)$", r"-O\1", thumb)
        if thumb.startswith("http://"):
            thumb = "https://" + thumb[7:]
    return thumb


# =========================================================
# HISTORIAL
# =========================================================

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


# =========================================================
# MÉTODO HÍBRIDO: DESCUBRE IDs EN WEB PÚBLICA + LEE DETALLES EN API OFICIAL
# =========================================================

def _consultas_ampliadas():
    consultas = [
        "tecnologia", "celulares", "hogar", "cocina", "herramientas",
        "electrodomesticos", "computacion", "audio", "deportes", "calzado",
        "indumentaria", "belleza", "juguetes", "bebes", "mascotas",
        "accesorios auto", "motos", "jardin", "oficina", "iluminacion",
        "smart tv", "televisores", "notebook", "tablet", "monitores",
        "auriculares", "parlantes", "impresoras", "teclados", "mouse",
        "aires acondicionados", "ventiladores", "calefaccion", "heladeras",
        "freezer", "microondas", "cafeteras", "licuadoras", "batidoras",
        "freidoras", "aspiradoras", "lavarropas", "colchones", "muebles",
        "sillas", "mesas", "placard", "taladros", "amoladoras",
        "hidrolavadoras", "soldadoras", "compresores", "bicicletas",
        "cintas caminadoras", "pesas", "zapatillas", "mochilas", "relojes",
        "perfumes", "cuidado personal", "camaras seguridad", "domotica",
        "luces led", "baterias auto", "neumaticos", "repuestos auto",
        "accesorios celular", "cargadores", "power bank", "discos ssd",
        "memorias ram", "placas de video", "procesadores", "consolas",
        "gaming", "auriculares bluetooth", "parlantes bluetooth", "smartwatch",
        "routers wifi", "hornos electricos", "freidoras de aire", "tostadoras",
        "pavas electricas", "calefactores", "secarropas", "planchas",
        "almohadas", "sabanas", "toallas", "ollas", "sartenes", "vajilla",
        "organizadores", "escritorios", "bibliotecas", "atornilladores",
        "cajas herramientas", "cortadoras de cesped", "cascos bicicleta",
        "camperas", "remeras", "pantalones", "ropa deportiva", "valijas",
        "bolsos", "mochilas escolares", "juegos de mesa", "cochecitos bebe",
        "sillas bebe", "alimento mascotas", "cama mascotas", "perfumes hombre",
        "perfumes mujer", "secadores pelo", "planchitas pelo", "afeitadoras",
        "cepillos electricos", "camaras wifi", "alarmas", "cerraduras digitales",
        "lamparas led", "tiras led", "cubiertas auto", "aceite motor",
        "soportes celular", "cables usb", "cargadores celular", "fundas celular",
        "webcam", "discos externos", "pendrives", "micro sd", "fuentes pc",
        "gabinetes pc", "joystick", "consolas videojuegos", "limpieza hogar",
        "papeleria", "utiles escolares",
    ]
    random.shuffle(consultas)
    return consultas


def _url_busqueda_ml(consulta):
    slug = limpiar_texto(consulta).lower()
    slug = re.sub(r"[^a-z0-9áéíóúüñ]+", "-", slug, flags=re.IGNORECASE)
    slug = slug.strip("-")
    return f"https://listado.mercadolibre.com.ar/{slug}" if slug else URL_OFERTAS


def _descubrir_item_ids_en_url(url):
    """
    Escanea el HTML crudo de la página pública de Mercado Libre buscando
    cualquier referencia a publicaciones (MLA1234567890 o /MLA-1234567890)
    sin depender de clases CSS ni estructura visual.
    """
    try:
        resp = safe_get(url, timeout=25)
        html = resp.text
    except Exception as e:
        print("AVISO web:", url, "|", e)
        return []

    encontrados = []
    vistos = set()
    # Busca MLA seguido de 8 a 12 dígitos (con o sin guión)
    for m in re.finditer(r"\bMLA-?(\d{8,12})\b", html, re.IGNORECASE):
        item_id = "MLA" + m.group(1)
        if item_id not in vistos:
            vistos.add(item_id)
            encontrados.append(item_id)

    return encontrados


def _obtener_items_multiget_api(item_ids):
    """
    Consulta hasta 20 ítems en una sola llamada a /items?ids=... de la API oficial,
    el cual no requiere permisos de búsqueda global.
    """
    if not item_ids:
        return []

    items_validos = []
    # Procesar en lotes de 20 (límite de Mercado Libre multiget)
    for i in range(0, len(item_ids), 20):
        lote = item_ids[i:i + 20]
        ids_str = ",".join(lote)
        try:
            data = api_get("/items", params={"ids": ids_str}, timeout=30)
            if isinstance(data, list):
                for entrada in data:
                    if isinstance(entrada, dict) and entrada.get("code") == 200:
                        body = entrada.get("body")
                        if isinstance(body, dict) and body.get("id"):
                            items_validos.append(body)
        except Exception as e:
            print("AVISO multiget /items:", e)
            # Fallback individual si falla el lote
            for single_id in lote:
                try:
                    body = api_get(f"/items/{single_id}", timeout=20)
                    if isinstance(body, dict) and body.get("id"):
                        items_validos.append(body)
                except Exception:
                    pass

    return items_validos


def _construir_producto_desde_item_api(item_json):
    item_id = limpiar_texto(item_json.get("id", "")).upper()
    if not re.fullmatch(r"MLA\d{7,}", item_id):
        return None

    if item_json.get("status") != "active":
        return None

    if item_json.get("condition") != "new":
        return None

    nombre = limpiar_texto(item_json.get("title") or "")
    precio_num = item_json.get("price")
    precio = _formatear_precio(precio_num)
    if not nombre or not precio:
        return None

    permalink = limpiar_url(item_json.get("permalink") or "")
    if not permalink:
        return None

    imagen_url = _mejor_imagen_api(item_json)
    if not imagen_url:
        return None

    precio_orig = item_json.get("original_price")
    precio_anterior = _formatear_precio(precio_orig) if precio_orig else ""
    descuento = ""
    if precio_orig and precio_num and float(precio_orig) > float(precio_num):
        pct = round((1 - (float(precio_num) / float(precio_orig))) * 100)
        if pct >= 5:
            descuento = f"{pct}% OFF"

    vendidos_num = item_json.get("sold_quantity") or 0
    vendidos = f"+{vendidos_num} vendidos" if vendidos_num else ""

    atributos = _extraer_atributos_item_api(item_json, nombre)

    return {
        "item_id": item_id,
        "nombre": nombre,
        "precio": precio,
        "precio_anterior": precio_anterior,
        "descuento": descuento,
        "cuotas": "",
        "ranking": "",
        "rating": "",
        "vendidos": vendidos,
        "url_original": permalink,
        "imagen_url": imagen_url,
        "atributos_visuales": atributos,
        "precio_verificado": True,
        "precio_fuente": "api_items_oficial",
    }


def _categoria_para_diversidad(producto):
    texto = " ".join([
        limpiar_texto(producto.get("nombre", "")),
        limpiar_texto(producto.get("url_original", "")),
    ]).lower()

    grupos = [
        ("herramientas", (
            "taladro", "amoladora", "atornillador", "hidrolavadora", "soldadora",
            "compresor", "herramienta", "llave", "mecha", "sierra", "martillo"
        )),
        ("hogar_cocina", (
            "heladera", "freezer", "microondas", "cafetera", "licuadora", "batidora",
            "freidora", "aspiradora", "lavarropas", "secarropas", "colchon", "mueble",
            "silla", "mesa", "placard", "olla", "sarten", "vajilla", "tostadora",
            "pava electrica", "almohada", "sabana", "toalla", "organizador"
        )),
        ("tecnologia", (
            "placa de video", "geforce", "radeon", "rtx", "gpu", "notebook", "laptop",
            "celular", "smartphone", "tablet", "monitor", "procesador", "disco ssd",
            "ssd", "memoria ram", "teclado", "mouse", "webcam", "router", "impresora",
            "consola", "joystick", "smart tv", "televisor", "auricular", "parlante",
            "power bank", "cargador", "micro sd", "pendrive"
        )),
        ("deportes", (
            "bicicleta", "cinta caminadora", "pesas", "mancuerna", "fitness", "gym",
            "deportivo", "pelota", "futbol", "running", "entrenamiento"
        )),
        ("moda_calzado", (
            "zapatilla", "calzado", "campera", "remera", "pantalon", "vestido",
            "mochila", "valija", "bolso", "ropa", "indumentaria"
        )),
        ("belleza_cuidado", (
            "perfume", "shampoo", "secador de pelo", "planchita", "afeitadora",
            "cepillo electrico", "belleza", "cuidado personal", "maquillaje"
        )),
        ("juguetes_bebes", (
            "juguete", "juego de mesa", "bebe", "cochecito", "silla bebe", "pañal"
        )),
        ("mascotas", (
            "mascota", "perro", "gato", "alimento mascotas", "cama mascotas"
        )),
        ("auto_moto", (
            "auto", "moto", "neumatico", "cubierta", "bateria", "aceite motor",
            "repuesto", "soporte celular auto"
        )),
        ("seguridad_iluminacion", (
            "camara seguridad", "camara wifi", "alarma", "cerradura digital",
            "lampara led", "tira led", "iluminacion"
        )),
        ("oficina_escolar", (
            "papeleria", "utiles escolares", "escritorio", "biblioteca", "oficina"
        )),
        ("supermercado_limpieza", (
            "supermercado", "limpieza", "detergente", "jabon", "papel higienico"
        )),
    ]

    for categoria, palabras in grupos:
        if any(palabra in texto for palabra in palabras):
            return categoria
    return "otros"


def _puntaje_producto_demanda(producto):
    puntos = 0.0
    vendidos = limpiar_texto(producto.get("vendidos", "")).lower()
    m = re.search(r"([\d\.]+)", vendidos)
    if m:
        try:
            n = float(m.group(1).replace(".", ""))
            puntos += min(n / 100.0, 500.0)
        except Exception:
            pass

    m = re.search(r"(\d{1,2})%", producto.get("descuento", ""))
    if m:
        puntos += int(m.group(1)) * 2

    if producto.get("precio") and producto.get("precio") != "Precio no disponible":
        puntos += 10
    if producto.get("imagen_url"):
        puntos += 10
    return puntos


def _seleccionar_tanda_diversa(candidatos, cantidad):
    ordenados = sorted(candidatos, key=_puntaje_producto_demanda, reverse=True)
    elegidos = []
    ids_elegidos = set()
    conteo = {}

    def agregar(producto):
        item_id = limpiar_texto(producto.get("item_id", "")).upper()
        if item_id in ids_elegidos:
            return False
        categoria = _categoria_para_diversidad(producto)
        elegidos.append(producto)
        ids_elegidos.add(item_id)
        conteo[categoria] = conteo.get(categoria, 0) + 1
        return True

    categorias_usadas = set()
    for producto in ordenados:
        if len(elegidos) >= cantidad:
            break
        categoria = _categoria_para_diversidad(producto)
        if categoria in categorias_usadas:
            continue
        if agregar(producto):
            categorias_usadas.add(categoria)

    for producto in ordenados:
        if len(elegidos) >= cantidad:
            break
        categoria = _categoria_para_diversidad(producto)
        if conteo.get(categoria, 0) >= 2:
            continue
        agregar(producto)

    for producto in ordenados:
        if len(elegidos) >= cantidad:
            break
        agregar(producto)

    print("Categorías elegidas:", [_categoria_para_diversidad(p) for p in elegidos])
    return elegidos[:cantidad]


def obtener_productos_base():
    print("--- BUSCANDO 10 PRODUCTOS NUEVOS (DETECCIÓN DE IDs + VALIDACIÓN API /items) ---")
    token = os.getenv("MELI_ACCESS_TOKEN", "").strip() or MELI_ACCESS_TOKEN
    print("Token Mercado Libre presente:", "SÍ" if token else "NO")

    historial = cargar_historial_publicados()
    print("Publicaciones ya usadas en el historial:", len(historial))

    nuevos = {}
    OBJETIVO_POOL = max(CANTIDAD_PRODUCTOS * 2, 20)

    urls_fuente = [URL_OFERTAS, URL_MAS_VENDIDOS] + [
        _url_busqueda_ml(c) for c in _consultas_ampliadas()
    ]

    ids_evaluados = set()

    for url in urls_fuente:
        if len(nuevos) >= OBJETIVO_POOL:
            break

        ids_pagina = _descubrir_item_ids_en_url(url)
        ids_nuevos = [
            iid for iid in ids_pagina
            if iid not in historial and iid not in nuevos and iid not in ids_evaluados
        ]
        if not ids_nuevos:
            continue

        print(f"IDs detectados en {url}: {len(ids_pagina)} | Nuevos a consultar en API: {len(ids_nuevos)}")
        ids_evaluados.update(ids_nuevos)

        # Consultamos en lotes de 20 vía API /items
        items_api = _obtener_items_multiget_api(ids_nuevos[:40])
        for item_json in items_api:
            if len(nuevos) >= OBJETIVO_POOL:
                break

            producto = _construir_producto_desde_item_api(item_json)
            if not producto:
                continue

            if not es_producto_permitido(producto):
                print("DESCARTADO por filtro (alcohol):", producto.get("nombre", ""))
                continue

            item_id = producto["item_id"]
            nuevos[item_id] = producto
            print(
                f"CANDIDATO VÁLIDO {len(nuevos)}:",
                item_id, "|", _categoria_para_diversidad(producto), "|",
                producto["nombre"], "| precio=", producto["precio"]
            )

    if len(nuevos) < CANTIDAD_PRODUCTOS:
        raise RuntimeError(
            f"Solo se consiguieron {len(nuevos)} productos nuevos completos. "
            f"Se necesitan {CANTIDAD_PRODUCTOS}. El historial NO fue borrado ni se usaron repetidos."
        )

    candidatos = list(nuevos.values())
    elegidos = _seleccionar_tanda_diversa(candidatos, CANTIDAD_PRODUCTOS)

    if len(elegidos) != CANTIDAD_PRODUCTOS:
        raise RuntimeError(
            f"La selección diversa devolvió {len(elegidos)} productos y se necesitan {CANTIDAD_PRODUCTOS}."
        )

    return elegidos


def _leer_demanda_pendiente():
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


def obtener_productos_demanda(maximo=10):
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

        url_busqueda = _url_busqueda_ml(necesidad["consulta"])
        ids_pagina = _descubrir_item_ids_en_url(url_busqueda)
        ids_nuevos = [iid for iid in ids_pagina if iid not in historial and iid not in ids]
        if not ids_nuevos:
            continue

        items_api = _obtener_items_multiget_api(ids_nuevos[:20])
        candidatos = []
        for item_json in items_api:
            prod = _construir_producto_desde_item_api(item_json)
            if prod and es_producto_permitido(prod):
                prod["consulta_demanda"] = necesidad["consulta"]
                prod["origen_demanda"] = necesidad.get("origen", "")
                candidatos.append(prod)

        candidatos.sort(key=_puntaje_producto_demanda, reverse=True)
        candidato = candidatos[0] if candidatos else None
        if not candidato:
            continue

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
    textos = list(datos.get("atributos_visuales", []))[:3]

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
    if producto is None:
        return

    producto = quitar_fondo_blanco_conectado(producto)
    if producto is None or producto.width < 2 or producto.height < 2:
        return

    area_x0 = 245
    area_y0 = 275
    area_x1 = 1010
    area_y1 = 770

    max_w = area_x1 - area_x0
    max_h = area_y1 - area_y0

    escala = min(max_w / producto.width, max_h / producto.height)
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
    azul = (36, 49, 126)
    amarillo = (255, 225, 0)

    f = fuente(20, True, True)
    draw.text((838, 269), "Lo mejor", font=f, fill=azul)
    draw.text((855, 292), "está acá", font=f, fill=azul)
    draw.line((916, 319, 972, 305), fill=amarillo, width=7)


def crear_imagen_oferta(datos, numero):
    nombre_archivo = f"oferta_final_{numero:02d}_{VERSION}.png"
    salida = CARPETA_OFERTAS / nombre_archivo

    imagen = cargar_plantilla(PLANTILLA_OFERTA_PATH)
    draw = ImageDraw.Draw(imagen)

    dibujar_slogan_mercado_libre(draw)
    dibujar_textos_laterales(draw, datos)

    producto = descargar_imagen(datos["imagen_url"])
    if producto is None:
        raise RuntimeError(
            f"No se pudo descargar la imagen del producto "
            f"{datos.get('item_id', '')}: {datos.get('imagen_url', '')}"
        )
    pegar_producto(imagen, producto)

    font_titulo, lineas = fuente_titulo(draw, datos["nombre"])

    y = 825
    for linea in lineas[:2]:
        caja = draw.textbbox((0, 0), linea, font=font_titulo)
        ancho = caja[2] - caja[0]
        x = (ANCHO - ancho) // 2
        draw.text((x, y), linea, font=font_titulo, fill=(6, 6, 6))
        y += 45

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


def validar_tanda_integridad(productos):
    if len(productos) != CANTIDAD_PRODUCTOS:
        raise RuntimeError(
            f"Tanda inválida: se esperaban {CANTIDAD_PRODUCTOS} productos "
            f"y llegaron {len(productos)}."
        )

    ids = set()
    links = set()

    for numero, datos in enumerate(productos, start=1):
        item_id = limpiar_texto(datos.get("item_id", "")).upper()
        link = limpiar_texto(datos.get("url_original", ""))
        precio = limpiar_texto(datos.get("precio", ""))
        imagen = limpiar_texto(datos.get("imagen_url", ""))

        if not re.fullmatch(r"MLA\d{7,}", item_id):
            raise RuntimeError(f"Producto {numero}: item_id inválido o ausente.")
        if not link:
            raise RuntimeError(f"Producto {numero}: link ausente.")
        if not precio or precio == "Precio no disponible":
            raise RuntimeError(f"Producto {numero}: precio ausente.")
        if not datos.get("precio_verificado"):
            raise RuntimeError(f"Producto {numero}: precio no verificado.")
        if not imagen:
            raise RuntimeError(f"Producto {numero}: imagen ausente.")

        if item_id in ids:
            raise RuntimeError(f"Producto {numero}: item repetido {item_id}.")
        if link in links:
            raise RuntimeError(f"Producto {numero}: link repetido.")

        ids.add(item_id)
        links.add(link)

    print("✅ Integridad de tanda verificada: 10 productos, links, precios e imágenes.")


def guardar_tanda(productos):
    validar_tanda_integridad(productos)
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

    crear_imagen_promo_canal()


# =========================================================
# COLA URGENTE PARA AUTOMATE
# =========================================================

def guardar_urgentes(productos):
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
    urgentes, lineas_resueltas = obtener_productos_demanda(maximo=50)
    if urgentes:
        guardar_urgentes(urgentes)
        guardar_historial_publicados(urgentes)
        _marcar_demanda_procesada(lineas_resueltas)

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
