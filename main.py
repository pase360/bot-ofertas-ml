import os
import random
import re
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

REPO = os.getenv(
    "GITHUB_REPOSITORY",
    "pase360/bot-ofertas-ml"
)

RAMA = os.getenv(
    "GITHUB_REF_NAME",
    "main"
)

VERSION = os.getenv(
    "GITHUB_RUN_ID",
    datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
)

RAW_BASE = (
    f"https://raw.githubusercontent.com/"
    f"{REPO}/{RAMA}/ofertas"
)

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

    return re.sub(
        r"\s+",
        " ",
        str(texto)
    ).strip()


def limpiar_url(url):

    if not url:
        return ""

    url = urljoin(
        "https://www.mercadolibre.com.ar",
        url
    )

    return url.split("?")[0]


def es_producto(url):

    return bool(
        url
        and (
            "/p/MLA" in url
            or "/MLA-" in url
        )
    )


def nombre_desde_url(url):

    try:

        path = urlparse(url).path

        partes = [
            parte
            for parte in path.split("/")
            if parte
        ]

        candidato = ""

        for parte in partes:

            if parte == "p":
                continue

            if parte.upper().startswith("MLA"):
                continue

            if len(parte) > len(candidato):
                candidato = parte

        candidato = (
            candidato
            .replace("-", " ")
            .replace("_", " ")
        )

        candidato = limpiar_texto(candidato)

        if candidato:
            return candidato.title()

    except Exception:
        pass

    return "Producto Mercado Libre"


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

        texto = limpiar_texto(
            nodo.get_text(
                " ",
                strip=True
            )
        )

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
                re.IGNORECASE
            )
        )

        if tiene_precio and tiene_imagen:

            candidatos.append(
                (
                    nodo,
                    tiene_datos,
                    len(texto)
                )
            )

            if tiene_datos:
                return nodo

    if candidatos:

        candidatos.sort(
            key=lambda item: item[2]
        )

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

            texto = limpiar_texto(
                elemento.get_text(
                    " ",
                    strip=True
                )
            )

            inferior = texto.lower()

            if not 8 <= len(texto) <= 220:
                continue

            if "$" in texto:
                continue

            if "off" in inferior:
                continue

            if "más vendido" in inferior:
                continue

            if "mas vendido" in inferior:
                continue

            if "envío gratis" in inferior:
                continue

            if "envio gratis" in inferior:
                continue

            return texto

    for atributo in [
        "title",
        "aria-label",
    ]:

        valor = limpiar_texto(
            enlace.get(
                atributo,
                ""
            )
        )

        if 8 <= len(valor) <= 220:
            return valor

    for imagen in contenedor.find_all("img"):

        alt = limpiar_texto(
            imagen.get(
                "alt",
                ""
            )
        )

        if (
            8 <= len(alt) <= 220
            and "$" not in alt
        ):
            return alt

    return nombre_desde_url(url)


# =========================================================
# IMAGEN DEL PRODUCTO
# =========================================================

def obtener_url_imagen(contenedor):

    for imagen in contenedor.find_all("img"):

        for atributo in [
            "data-src",
            "data-lazy",
            "src",
        ]:

            url = imagen.get(atributo)

            if (
                url
                and url.startswith("http")
                and ".svg" not in url.lower()
            ):
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


# =========================================================
# PRECIOS
# =========================================================

def leer_money_amount(elemento):

    if not elemento:
        return ""

    fraction = elemento.select_one(
        ".andes-money-amount__fraction"
    )

    cents = elemento.select_one(
        ".andes-money-amount__cents"
    )

    if fraction:

        entero = limpiar_texto(
            fraction.get_text()
        )

        if cents:

            centavos = limpiar_texto(
                cents.get_text()
            )

            if centavos:
                return (
                    "$ "
                    + entero
                    + ","
                    + centavos
                )

        return "$ " + entero

    texto = limpiar_texto(
        elemento.get_text(
            " ",
            strip=True
        )
    )

    match = re.search(
        r"\$\s*([\d\.]+(?:,\d+)?)",
        texto
    )

    if match:
        return "$ " + match.group(1)

    return ""


def extraer_importes_texto(texto):

    encontrados = re.findall(
        r"\$\s*([\d\.]+(?:,\d+)?)",
        texto
    )

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

        for elemento in contenedor.select(
            ".andes-money-amount"
        ):

            valor = leer_money_amount(
                elemento
            )

            if (
                valor
                and valor not in valores
            ):
                valores.append(valor)

        if valores:

            if (
                descuento
                and len(valores) >= 2
            ):

                if not precio_anterior:
                    precio_anterior = valores[0]

                precio = valores[1]

            else:

                precio = valores[0]

    if not precio:

        importes = extraer_importes_texto(
            texto
        )

        if importes:

            if (
                descuento
                and len(importes) >= 2
            ):

                if not precio_anterior:
                    precio_anterior = importes[0]

                precio = importes[1]

            else:

                precio = importes[0]

    if not precio:
        precio = "Precio no disponible"

    return precio, precio_anterior


# =========================================================
# DATOS DEL PRODUCTO
# =========================================================

def extraer_datos_tarjeta(enlace, contenedor):

    url = limpiar_url(
        enlace.get("href")
    )

    texto = limpiar_texto(
        contenedor.get_text(
            " ",
            strip=True
        )
    )

    nombre = obtener_nombre(
        contenedor,
        enlace,
        url
    )

    descuento = ""

    match = re.search(
        r"(\d{1,2}%\s*OFF)",
        texto,
        re.IGNORECASE
    )

    if match:

        descuento = (
            match.group(1)
            .upper()
        )

    precio, precio_anterior = obtener_precios(
        contenedor,
        texto,
        descuento
    )

    cuotas = ""

    patrones_cuotas = [
        (
            r"((?:Mismo precio(?: en)?\s+)?"
            r"\d{1,2}\s+cuotas"
            r"(?:\s+sin\s+inter[eé]s)?"
            r"(?:\s+de\s+\$\s*[\d\.\,]+)?)"
        ),
        (
            r"(\d{1,2}\s+cuotas"
            r"(?:\s+de\s+\$\s*[\d\.\,]+)?)"
        ),
    ]

    for patron in patrones_cuotas:

        match = re.search(
            patron,
            texto,
            re.IGNORECASE
        )

        if match:

            cuotas = limpiar_texto(
                match.group(1)
            )

            break

    if not cuotas:
        cuotas = "Consultar cuotas"

    ranking = ""

    match = re.search(
        r"(\d{1,2})\s*[º°]\s*(?:MÁS|MAS)\s+VENDIDO",
        texto,
        re.IGNORECASE
    )

    if match:

        ranking = (
            match.group(1)
            + "º MÁS VENDIDO"
        )

    rating = ""

    for selector in [
        ".poly-reviews__rating",
        ".ui-search-reviews__rating-number",
        "[class*='rating']",
    ]:

        elemento = contenedor.select_one(
            selector
        )

        if not elemento:
            continue

        texto_rating = limpiar_texto(
            elemento.get_text(
                " ",
                strip=True
            )
        )

        match = re.search(
            r"\b([1-5](?:[\.,]\d)?)\b",
            texto_rating
        )

        if match:

            rating = (
                match.group(1)
                .replace(
                    ",",
                    "."
                )
            )

            break

    vendidos = ""

    match = re.search(
        (
            r"(\+?\s*[\d\.]+\s*"
            r"(?:mil)?\s+"
            r"(?:productos\s+)?vendidos)"
        ),
        texto,
        re.IGNORECASE
    )

    if match:

        vendidos = limpiar_texto(
            match.group(1)
        )

    imagen_url = obtener_url_imagen(
        contenedor
    )

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
# OBTENER PRODUCTOS
# =========================================================

def obtener_productos():

    print(
        "--- DESCARGANDO MÁS VENDIDOS ---"
    )

    response = requests.get(
        URL_MAS_VENDIDOS,
        headers=HEADERS,
        timeout=30
    )

    print(
        "HTTP Más vendidos:",
        response.status_code
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    encontrados = {}

    for enlace in soup.find_all(
        "a",
        href=True
    ):

        url = limpiar_url(
            enlace.get("href")
        )

        if not es_producto(url):
            continue

        if "mas-vendidos" in url:
            continue

        contenedor = encontrar_contenedor(
            enlace
        )

        if not contenedor:
            continue

        datos = extraer_datos_tarjeta(
            enlace,
            contenedor
        )

        puntos = 0

        if (
            datos["nombre"]
            != "Producto Mercado Libre"
        ):
            puntos += 5

        if (
            datos["precio"]
            != "Precio no disponible"
        ):
            puntos += 6

        if datos["imagen_url"]:
            puntos += 4

        if datos["descuento"]:
            puntos += 1

        if (
            datos["cuotas"]
            != "Consultar cuotas"
        ):
            puntos += 1

        if datos["ranking"]:
            puntos += 1

        anterior = encontrados.get(
            url
        )

        if (
            anterior is None
            or puntos > anterior["_puntos"]
        ):

            datos["_puntos"] = puntos
            encontrados[url] = datos

    productos = list(
        encontrados.values()
    )

    productos.sort(
        key=lambda producto:
        producto["_puntos"],
        reverse=True
    )

    print(
        "Productos encontrados:",
        len(productos)
    )

    validos = [
        producto
        for producto in productos
        if (
            producto["precio"]
            != "Precio no disponible"
            and producto["imagen_url"]
            and producto["nombre"]
            != "Producto Mercado Libre"
        )
    ]

    print(
        "Productos con precio válido:",
        len(validos)
    )

    if len(validos) >= CANTIDAD_PRODUCTOS:

        candidatos = validos[:40]

    else:

        candidatos = productos[:40]

    if len(candidatos) >= CANTIDAD_PRODUCTOS:

        seleccionados = random.sample(
            candidatos,
            CANTIDAD_PRODUCTOS
        )

    else:

        seleccionados = candidatos

    for numero, producto in enumerate(
        seleccionados,
        start=1
    ):

        print(
            f"{numero}. "
            f"{producto['nombre']} | "
            f"{producto['precio']} | "
            f"{producto['precio_anterior']} | "
            f"{producto['descuento']} | "
            f"{producto['cuotas']}"
        )

    return seleccionados


# =========================================================
# DESCARGAR IMAGEN
# =========================================================

def descargar_imagen(url):

    if not url:
        return None

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30
        )

        response.raise_for_status()

        imagen = Image.open(
            BytesIO(
                response.content
            )
        )

        return imagen.convert("RGBA")

    except Exception as e:

        print(
            "ERROR imagen:",
            e
        )

        return None


# =========================================================
# TEXTO
# =========================================================

def ajustar_texto(
    draw,
    texto,
    font,
    ancho_maximo
):

    palabras = limpiar_texto(
        texto
    ).split()

    if not palabras:
        return [""]

    lineas = []
    linea = palabras[0]

    for palabra in palabras[1:]:

        prueba = (
            linea
            + " "
            + palabra
        )

        caja = draw.textbbox(
            (0, 0),
            prueba,
            font=font
        )

        ancho = (
            caja[2]
            - caja[0]
        )

        if ancho <= ancho_maximo:

            linea = prueba

        else:

            lineas.append(
                linea
            )

            linea = palabra

    lineas.append(linea)

    return lineas


def dibujar_lineas(
    draw,
    lineas,
    x,
    y,
    font,
    color,
    espacio=6
):

    posicion_y = y

    for linea in lineas:

        draw.text(
            (x, posicion_y),
            linea,
            font=font,
            fill=color
        )

        caja = draw.textbbox(
            (x, posicion_y),
            linea,
            font=font
        )

        posicion_y = (
            caja[3]
            + espacio
        )

    return posicion_y


# =========================================================
# LOGO
# =========================================================

def colocar_logo(imagen):

    if not LOGO_PATH.exists():

        print(
            "ADVERTENCIA: logo_cazadores.png no encontrado"
        )

        return

    try:

        logo = Image.open(
            LOGO_PATH
        ).convert("RGBA")

        logo.thumbnail(
            (150, 150),
            Image.LANCZOS
        )

        imagen.paste(
            logo,
            (58, 38),
            logo
        )

    except Exception as e:

        print(
            "ERROR logo:",
            e
        )


# =========================================================
# PLANTILLAS APROBADAS
# =========================================================

def cargar_plantilla(path):
    if not path.exists():
        raise FileNotFoundError(
            f"Falta {path.name}. Subila a la raíz del repositorio."
        )

    imagen = Image.open(path).convert("RGBA")

    if imagen.size != (ANCHO, ALTO):
        imagen = imagen.resize(
            (ANCHO, ALTO),
            Image.LANCZOS
        )

    return imagen


def texto_centrado(draw, texto, y, font, color, x0=0, x1=ANCHO):
    caja = draw.textbbox((0, 0), texto, font=font)
    ancho = caja[2] - caja[0]
    x = x0 + ((x1 - x0) - ancho) // 2
    draw.text((x, y), texto, font=font, fill=color)


def lineas_limitadas(draw, texto, font, ancho_maximo, max_lineas):
    lineas = ajustar_texto(
        draw,
        texto,
        font,
        ancho_maximo
    )

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


def datos_laterales(datos):
    """
    Mantiene exactamente la distribución visual de tres ítems laterales,
    pero muestra datos reales del producto cuando están disponibles.
    """
    resultado = []

    if datos.get("ranking"):
        resultado.append(datos["ranking"])
    else:
        resultado.append("Oferta\nseleccionada")

    if (
        datos.get("cuotas")
        and datos["cuotas"] != "Consultar cuotas"
    ):
        resultado.append(datos["cuotas"])
    else:
        resultado.append("Consultar\ncuotas")

    if datos.get("vendidos"):
        resultado.append(datos["vendidos"])
    elif datos.get("rating"):
        resultado.append("★ " + datos["rating"])
    else:
        resultado.append("Producto\ndestacado")

    return resultado[:3]


def dibujar_datos_laterales(draw, datos):
    """
    La plantilla ya contiene los tres círculos e íconos amarillos del diseño
    aprobado. Aquí solo se escribe el texto variable al lado de cada uno.
    """
    textos = datos_laterales(datos)
    centros_y = [390, 510, 630]

    for cy, texto in zip(centros_y, textos):
        partes = []

        for bloque in str(texto).split("\n"):
            partes.extend(
                ajustar_texto(
                    draw,
                    bloque,
                    fuente(20),
                    175
                )
            )

        y = cy - 26

        for linea in partes[:3]:
            draw.text(
                (158, y),
                linea,
                font=fuente(20),
                fill=(20, 20, 20)
            )

            caja = draw.textbbox(
                (158, y),
                linea,
                font=fuente(20)
            )
            y = caja[3] + 1


def pegar_producto(imagen, producto):
    """Ubica el producto en la misma zona central de la maqueta aprobada."""
    if producto is None:
        return

    producto = producto.convert("RGBA")

    area_x0 = 230
    area_y0 = 310
    area_x1 = 1045
    area_y1 = 805

    producto.thumbnail(
        (
            area_x1 - area_x0,
            area_y1 - area_y0
        ),
        Image.LANCZOS
    )

    x = area_x0 + ((area_x1 - area_x0) - producto.width) // 2
    y = area_y0 + ((area_y1 - area_y0) - producto.height) // 2

    imagen.paste(
        producto,
        (x, y),
        producto
    )


def dibujar_precio(draw, precio):
    """Precio azul grande, centrado, igual a la placa aprobada."""
    texto = limpiar_texto(precio)

    for tamano in range(76, 54, -1):
        f = fuente(tamano, True)
        caja = draw.textbbox((0, 0), texto, font=f)
        ancho = caja[2] - caja[0]

        if ancho <= 760:
            x = (ANCHO - ancho) // 2
            draw.text(
                (x, 965),
                texto,
                font=f,
                fill=(27, 112, 245)
            )
            return


def crear_imagen_oferta(datos, numero):
    """
    Parte de la placa aprobada y reemplaza únicamente las zonas variables:
    producto, datos laterales, nombre y precio. Todo lo demás queda tal cual
    está en la plantilla original aprobada.
    """
    nombre_archivo = (
        f"oferta_final_{numero:02d}_{VERSION}.png"
    )

    salida = CARPETA_OFERTAS / nombre_archivo

    imagen = cargar_plantilla(
        PLANTILLA_OFERTA_PATH
    )

    draw = ImageDraw.Draw(imagen)

    # Los espacios variables ya vienen limpios en la plantilla.
    dibujar_datos_laterales(
        draw,
        datos
    )

    producto = descargar_imagen(
        datos["imagen_url"]
    )

    pegar_producto(
        imagen,
        producto
    )

    font_titulo, lineas = fuente_titulo(
        draw,
        datos["nombre"]
    )

    y = 825

    for linea in lineas[:2]:
        draw.text(
            (100, y),
            linea,
            font=font_titulo,
            fill=(5, 5, 5)
        )

        caja = draw.textbbox(
            (100, y),
            linea,
            font=font_titulo
        )

        y = caja[3] + 1

    dibujar_precio(
        draw,
        datos["precio"]
    )

    imagen.convert("RGB").save(
        salida,
        "PNG",
        optimize=True
    )

    print(
        "✅ Imagen creada con plantilla aprobada:",
        salida
    )

    return nombre_archivo


# =========================================================
# PROPAGANDA DEL CANAL
# =========================================================

def crear_imagen_promo_canal():
    """
    La propaganda aprobada es totalmente fija. Se copia tal cual para no
    redibujarla ni cambiar colores, tipografías, tamaños o posiciones.
    """
    nombre_archivo = "promo_canal.png"
    salida = CARPETA_OFERTAS / nombre_archivo

    imagen = cargar_plantilla(
        PLANTILLA_PROMO_PATH
    )

    imagen.convert("RGB").save(
        salida,
        "PNG",
        optimize=True
    )

    print(
        "✅ Propaganda del canal creada:",
        salida
    )

    return nombre_archivo


# =========================================================
# GUARDAR ARCHIVOS
# =========================================================

def limpiar_ofertas():

    for archivo in CARPETA_OFERTAS.glob(
        "oferta_*.png"
    ):

        try:
            archivo.unlink()
        except Exception:
            pass


def guardar_tanda(productos):

    limpiar_ofertas()

    links = []
    datos_txt = []
    imagenes = []

    for numero, datos in enumerate(
        productos,
        start=1
    ):

        archivo = crear_imagen_oferta(
            datos,
            numero
        )

        links.append(
            datos["url_original"]
        )

        nombre = (
            datos["nombre"]
            .replace("|", "-")
        )

        precio = (
            datos["precio"]
            .replace("|", "-")
        )

        cuotas = (
            datos["cuotas"]
            .replace("|", "-")
        )

        datos_txt.append(
            f"{nombre} | "
            f"{precio} | "
            f"{cuotas}"
        )

        imagenes.append(
            f"{RAW_BASE}/{archivo}"
        )

    Path(
        "ultima_tanda.txt"
    ).write_text(
        "\n".join(links),
        encoding="utf-8"
    )

    Path(
        "datos_tanda.txt"
    ).write_text(
        "\n".join(datos_txt),
        encoding="utf-8"
    )

    Path(
        "imagenes_tanda.txt"
    ).write_text(
        "\n".join(imagenes),
        encoding="utf-8"
    )

    print("✅ ultima_tanda.txt generado")
    print("✅ datos_tanda.txt generado")
    print("✅ imagenes_tanda.txt generado")

    # La propaganda se genera aparte.
    # NO se agrega a imagenes_tanda.txt para mantener intacto
    # el circuito actual de Automate: 10 links = 10 imágenes.
    crear_imagen_promo_canal()


# =========================================================
# MAIN
# =========================================================

def main():

    productos = obtener_productos()

    if not productos:

        raise RuntimeError(
            "No se pudieron obtener productos"
        )

    print(
        "Productos seleccionados:",
        len(productos)
    )

    guardar_tanda(
        productos
    )

    print("✅ DISEÑO FINAL SIN ICONO")

    print(
        "✅ PROCESO COMPLETO FINALIZADO"
    )


if __name__ == "__main__":
    main()
