import os
import random
import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup, Tag
from PIL import Image, ImageDraw, ImageFont


# =========================================================
# CONFIGURACION
# =========================================================

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
    datetime.utcnow().strftime("%Y%m%d%H%M%S")
)

RAW_BASE = (
    f"https://raw.githubusercontent.com/"
    f"{REPO}/{RAMA}/ofertas"
)

ANCHO = 1080
ALTO = 1350


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


def limpiar_url(href):

    if not href:
        return ""

    href = urljoin(
        "https://www.mercadolibre.com.ar",
        href
    )

    return href.split("?")[0]


def es_link_producto(url):

    if not url:
        return False

    return (
        "/p/MLA" in url
        or "/MLA-" in url
    )


def extraer_importes(texto):

    encontrados = re.findall(
        r"\$\s*([\d\.]+(?:,\d+)?)",
        texto
    )

    return [
        "$ " + valor
        for valor in encontrados
    ]


def obtener_url_imagen(contenedor):

    if not contenedor:
        return ""

    imagenes = contenedor.find_all("img")

    for imagen in imagenes:

        for atributo in [
            "data-src",
            "data-lazy",
            "src",
        ]:

            url = imagen.get(atributo)

            if (
                url
                and url.startswith("http")
                and "svg" not in url.lower()
            ):
                return url

        srcset = imagen.get("srcset")

        if srcset:

            opciones = []

            for opcion in srcset.split(","):

                url = opcion.strip().split(" ")[0]

                if url.startswith("http"):
                    opciones.append(url)

            if opciones:
                return opciones[-1]

    sources = contenedor.find_all("source")

    for source in sources:

        srcset = source.get("srcset")

        if srcset:

            opciones = []

            for opcion in srcset.split(","):

                url = opcion.strip().split(" ")[0]

                if url.startswith("http"):
                    opciones.append(url)

            if opciones:
                return opciones[-1]

    return ""


def encontrar_contenedor_producto(enlace):

    nodo = enlace

    candidatos = []

    for nivel in range(9):

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


def obtener_nombre_producto(
    contenedor,
    enlace
):

    posibles = []

    # Primero títulos HTML
    for selector in [
        "h1",
        "h2",
        "h3",
        "[class*='title']",
    ]:

        try:
            elementos = contenedor.select(
                selector
            )
        except Exception:
            elementos = []

        for elemento in elementos:

            texto = limpiar_texto(
                elemento.get_text(
                    " ",
                    strip=True
                )
            )

            if (
                12 <= len(texto) <= 260
                and "$" not in texto
                and "vendidos" not in texto.lower()
            ):
                posibles.append(texto)

    # Luego textos de enlaces
    for a in contenedor.find_all(
        "a",
        href=True
    ):

        texto = limpiar_texto(
            a.get_text(
                " ",
                strip=True
            )
        )

        if (
            12 <= len(texto) <= 260
            and "$" not in texto
            and "vendidos" not in texto.lower()
        ):
            posibles.append(texto)

    # Texto del enlace original
    texto_enlace = limpiar_texto(
        enlace.get_text(
            " ",
            strip=True
        )
    )

    if 12 <= len(texto_enlace) <= 260:
        posibles.append(texto_enlace)

    # ALT de imagen
    for img in contenedor.find_all("img"):

        alt = limpiar_texto(
            img.get("alt", "")
        )

        if 12 <= len(alt) <= 260:
            posibles.append(alt)

    if posibles:

        # El nombre del producto suele ser
        # uno de los textos descriptivos más largos.
        posibles = list(dict.fromkeys(posibles))

        posibles.sort(
            key=len,
            reverse=True
        )

        return posibles[0]

    return "Producto Mercado Libre"


# =========================================================
# EXTRAER DATOS DE UNA TARJETA DE MAS VENDIDOS
# =========================================================

def extraer_datos_tarjeta(
    enlace,
    contenedor
):

    url = limpiar_url(
        enlace.get("href")
    )

    texto = limpiar_texto(
        contenedor.get_text(
            " ",
            strip=True
        )
    )

    nombre = obtener_nombre_producto(
        contenedor,
        enlace
    )

    # -----------------------------------------------------
    # DESCUENTO
    # -----------------------------------------------------

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
            .replace("  ", " ")
        )

    # -----------------------------------------------------
    # PRECIOS
    # -----------------------------------------------------

    importes = extraer_importes(
        texto
    )

    precio_anterior = ""
    precio = "Precio no disponible"

    if descuento and len(importes) >= 2:

        precio_anterior = importes[0]
        precio = importes[1]

    elif importes:

        precio = importes[0]

    # -----------------------------------------------------
    # CUOTAS
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # RANKING
    # -----------------------------------------------------

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

    # -----------------------------------------------------
    # RATING + VENDIDOS
    # -----------------------------------------------------

    rating = ""
    vendidos = ""

    match = re.search(
        (
            r"\b([1-5][\.,]\d)\b"
            r"\s*(?:\||·)?\s*"
            r"(\+?\s*[\d\.]+\s*(?:mil)?\s+vendidos)"
        ),
        texto,
        re.IGNORECASE
    )

    if match:

        rating = (
            match.group(1)
            .replace(",", ".")
        )

        vendidos = limpiar_texto(
            match.group(2)
        )

    else:

        match_rating = re.search(
            r"(?:Calificaci[oó]n\s+)?([1-5][\.,]\d)\s+de\s+5",
            texto,
            re.IGNORECASE
        )

        if match_rating:

            rating = (
                match_rating.group(1)
                .replace(",", ".")
            )

        match_vendidos = re.search(
            r"(\+?\s*[\d\.]+\s*(?:mil)?\s+(?:productos\s+)?vendidos)",
            texto,
            re.IGNORECASE
        )

        if match_vendidos:

            vendidos = limpiar_texto(
                match_vendidos.group(1)
            )

    # -----------------------------------------------------
    # IMAGEN
    # -----------------------------------------------------

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
        "texto_debug": texto[:700],
    }


# =========================================================
# OBTENER PRODUCTOS + DATOS DESDE MAS VENDIDOS
# =========================================================

def obtener_productos_mas_vendidos():

    print(
        "--- DESCARGANDO MAS VENDIDOS ---"
    )

    response = requests.get(
        URL_MAS_VENDIDOS,
        headers=HEADERS,
        timeout=30
    )

    print(
        "HTTP Más Vendidos:",
        response.status_code
    )

    response.raise_for_status()

    soup = BeautifulSoup(
        response.text,
        "html.parser"
    )

    productos_por_url = {}

    for enlace in soup.find_all(
        "a",
        href=True
    ):

        url = limpiar_url(
            enlace.get("href")
        )

        if not es_link_producto(url):
            continue

        if "mas-vendidos" in url:
            continue

        contenedor = encontrar_contenedor_producto(
            enlace
        )

        if not contenedor:
            continue

        datos = extraer_datos_tarjeta(
            enlace,
            contenedor
        )

        puntaje = 0

        if datos["nombre"] != "Producto Mercado Libre":
            puntaje += 4

        if datos["precio"] != "Precio no disponible":
            puntaje += 5

        if datos["imagen_url"]:
            puntaje += 4

        if datos["descuento"]:
            puntaje += 1

        if datos["cuotas"] != "Consultar cuotas":
            puntaje += 1

        if datos["vendidos"]:
            puntaje += 1

        anterior = productos_por_url.get(
            url
        )

        if (
            anterior is None
            or puntaje > anterior["_puntaje"]
        ):

            datos["_puntaje"] = puntaje

            productos_por_url[url] = datos

    productos = list(
        productos_por_url.values()
    )

    productos.sort(
        key=lambda x: x["_puntaje"],
        reverse=True
    )

    print(
        "Productos únicos encontrados:",
        len(productos)
    )

    for numero, datos in enumerate(
        productos[:20],
        start=1
    ):

        print(
            f"{numero}. "
            f"{datos['nombre']} | "
            f"{datos['precio']} | "
            f"{datos['descuento']} | "
            f"{datos['cuotas']}"
        )

    productos_validos = [
        producto
        for producto in productos
        if (
            producto["nombre"]
            != "Producto Mercado Libre"
            and
            producto["precio"]
            != "Precio no disponible"
        )
    ]

    if len(productos_validos) >= CANTIDAD_PRODUCTOS:

        return random.sample(
            productos_validos,
            CANTIDAD_PRODUCTOS
        )

    if len(productos) >= CANTIDAD_PRODUCTOS:

        return random.sample(
            productos,
            CANTIDAD_PRODUCTOS
        )

    return productos


# =========================================================
# DESCARGAR IMAGEN PRODUCTO
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

        return imagen.convert(
            "RGB"
        )

    except Exception as e:

        print(
            "ERROR descargando imagen:",
            e
        )

        return None


# =========================================================
# TEXTO EN IMAGEN
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
    actual = palabras[0]

    for palabra in palabras[1:]:

        prueba = (
            actual
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

            actual = prueba

        else:

            lineas.append(
                actual
            )

            actual = palabra

    lineas.append(
        actual
    )

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
# GENERAR PLACA DE OFERTA
# =========================================================

def crear_imagen_oferta(
    datos,
    numero
):

    nombre_archivo = (
        f"oferta_{numero:02d}_{VERSION}.png"
    )

    salida = (
        CARPETA_OFERTAS
        / nombre_archivo
    )

    imagen = Image.new(
        "RGB",
        (ANCHO, ALTO),
        (247, 246, 242)
    )

    draw = ImageDraw.Draw(
        imagen
    )

    # -----------------------------------------------------
    # TARJETA
    # -----------------------------------------------------

    draw.rounded_rectangle(
        (
            25,
            18,
            1055,
            1330
        ),
        radius=38,
        fill=(255, 255, 255),
        outline=(229, 229, 229),
        width=2
    )

    # -----------------------------------------------------
    # LOGO CAZADORES DE OFERTAS
    # -----------------------------------------------------

    draw.ellipse(
        (
            55,
            40,
            195,
            180
        ),
        fill=(10, 10, 10),
        outline=(245, 190, 0),
        width=8
    )

    draw.text(
        (75, 72),
        "CAZADORES",
        font=fuente(20, True),
        fill=(245, 190, 0)
    )

    draw.text(
        (73, 101),
        "DE OFERTAS",
        font=fuente(19, True),
        fill="white"
    )

    draw.text(
        (226, 52),
        "Cazadores de Ofertas",
        font=fuente(45, True),
        fill=(15, 15, 15)
    )

    draw.text(
        (228, 110),
        "Las mejores ofertas, todos los días",
        font=fuente(27),
        fill=(80, 80, 80)
    )

    # -----------------------------------------------------
    # FOTO PRODUCTO
    # -----------------------------------------------------

    producto = descargar_imagen(
        datos["imagen_url"]
    )

    area_x0 = 65
    area_y0 = 195
    area_x1 = 1015
    area_y1 = 550

    area_ancho = area_x1 - area_x0
    area_alto = area_y1 - area_y0

    if producto:

        producto.thumbnail(
            (
                area_ancho,
                area_alto
            ),
            Image.LANCZOS
        )

        x = (
            area_x0
            + (
                area_ancho
                - producto.width
            ) // 2
        )

        y = (
            area_y0
            + (
                area_alto
                - producto.height
            ) // 2
        )

        imagen.paste(
            producto,
            (x, y)
        )

    else:

        draw.rounded_rectangle(
            (
                area_x0,
                area_y0,
                area_x1,
                area_y1
            ),
            radius=20,
            fill=(245, 245, 245)
        )

        draw.text(
            (330, 350),
            "Imagen no disponible",
            font=fuente(30, True),
            fill=(100, 100, 100)
        )

    # -----------------------------------------------------
    # MAS VENDIDO
    # -----------------------------------------------------

    y = 570

    draw.rounded_rectangle(
        (
            60,
            y,
            355,
            y + 62
        ),
        radius=12,
        fill=(255, 90, 20)
    )

    draw.text(
        (
            82,
            y + 11
        ),
        "🔥 MÁS VENDIDO",
        font=fuente(31, True),
        fill="white"
    )

    if datos["ranking"]:

        draw.text(
            (
                385,
                y + 15
            ),
            datos["ranking"],
            font=fuente(27),
            fill=(25, 25, 25)
        )

    # -----------------------------------------------------
    # TITULO
    # -----------------------------------------------------

    y += 85

    fuente_titulo = fuente(
        46,
        True
    )

    lineas = ajustar_texto(
        draw,
        datos["nombre"],
        fuente_titulo,
        935
    )

    y = dibujar_lineas(
        draw,
        lineas[:3],
        65,
        y,
        fuente_titulo,
        (15, 15, 15)
    )

    # -----------------------------------------------------
    # RATING / VENDIDOS
    # -----------------------------------------------------

    metadata = []

    if datos["rating"]:
        metadata.append(
            "★ " + datos["rating"]
        )

    if datos["vendidos"]:
        metadata.append(
            datos["vendidos"]
        )

    if metadata:

        y += 8

        draw.text(
            (65, y),
            "  |  ".join(metadata),
            font=fuente(29, True),
            fill=(30, 30, 30)
        )

        y += 50

    # -----------------------------------------------------
    # PRECIO ANTERIOR
    # -----------------------------------------------------

    if datos["precio_anterior"]:

        draw.text(
            (65, y),
            datos["precio_anterior"],
            font=fuente(34),
            fill=(100, 100, 100)
        )

        y += 47

    # -----------------------------------------------------
    # PRECIO
    # -----------------------------------------------------

    fuente_precio = fuente(
        68,
        True
    )

    draw.text(
        (65, y),
        datos["precio"],
        font=fuente_precio,
        fill=(0, 145, 75)
    )

    caja = draw.textbbox(
        (65, y),
        datos["precio"],
        font=fuente_precio
    )

    if datos["descuento"]:

        x_descuento = min(
            caja[2] + 25,
            800
        )

        draw.rounded_rectangle(
            (
                x_descuento,
                y + 8,
                x_descuento + 190,
                y + 68
            ),
            radius=10,
            fill=(0, 150, 80)
        )

        draw.text(
            (
                x_descuento + 15,
                y + 17
            ),
            datos["descuento"],
            font=fuente(30, True),
            fill="white"
        )

    y += 90

    # -----------------------------------------------------
    # CUOTAS
    # -----------------------------------------------------

    draw.text(
        (65, y),
        datos["cuotas"][:85],
        font=fuente(32, True),
        fill=(15, 15, 15)
    )

    # -----------------------------------------------------
    # INFORMACION
    # -----------------------------------------------------

    y += 67

    draw.text(
        (65, y),
        "✓ Oferta disponible en Mercado Libre",
        font=fuente(27),
        fill=(55, 55, 55)
    )

    y += 43

    draw.text(
        (65, y),
        "✓ Precio y disponibilidad pueden variar",
        font=fuente(27),
        fill=(55, 55, 55)
    )

    # -----------------------------------------------------
    # BOTON
    # -----------------------------------------------------

    boton_y = 1150

    draw.rounded_rectangle(
        (
            55,
            boton_y,
            1025,
            boton_y + 125
        ),
        radius=27,
        fill=(224, 248, 231)
    )

    draw.text(
        (
            95,
            boton_y + 22
        ),
        "🔗 Ver en Mercado Libre",
        font=fuente(35, True),
        fill=(10, 80, 45)
    )

    draw.text(
        (
            95,
            boton_y + 72
        ),
        "Enlace afiliado en la publicación",
        font=fuente(27),
        fill=(35, 105, 195)
    )

    # -----------------------------------------------------
    # PIE
    # -----------------------------------------------------

    draw.text(
        (65, 1290),
        "🏷 Si comprás desde el enlace apoyás al canal 💛",
        font=fuente(23),
        fill=(65, 75, 95)
    )

    imagen.save(
        salida,
        "PNG",
        optimize=True
    )

    print(
        "✅ Imagen creada:",
        salida
    )

    return nombre_archivo


# =========================================================
# LIMPIAR IMAGENES VIEJAS
# =========================================================

def limpiar_imagenes_viejas():

    for archivo in CARPETA_OFERTAS.glob(
        "oferta_*.png"
    ):

        try:
            archivo.unlink()
        except Exception:
            pass


# =========================================================
# GUARDAR ARCHIVOS
# =========================================================

def guardar_resultados(productos):

    lineas_links = []
    lineas_datos = []
    lineas_imagenes = []

    limpiar_imagenes_viejas()

    for numero, datos in enumerate(
        productos,
        start=1
    ):

        archivo_imagen = crear_imagen_oferta(
            datos,
            numero
        )

        lineas_links.append(
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

        lineas_datos.append(
            f"{nombre} | {precio} | {cuotas}"
        )

        lineas_imagenes.append(
            f"{RAW_BASE}/{archivo_imagen}"
        )

    Path(
        "ultima_tanda.txt"
    ).write_text(
        "\n".join(lineas_links),
        encoding="utf-8"
    )

    Path(
        "datos_tanda.txt"
    ).write_text(
        "\n".join(lineas_datos),
        encoding="utf-8"
    )

    Path(
        "imagenes_tanda.txt"
    ).write_text(
        "\n".join(lineas_imagenes),
        encoding="utf-8"
    )

    print(
        "✅ ultima_tanda.txt generado"
    )

    print(
        "✅ datos_tanda.txt generado"
    )

    print(
        "✅ imagenes_tanda.txt generado"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    try:

        productos = (
            obtener_productos_mas_vendidos()
        )

    except Exception as e:

        print(
            "❌ Error leyendo Más vendidos:",
            e
        )

        raise

    if not productos:

        raise RuntimeError(
            "No se encontraron productos"
        )

    print(
        "Productos seleccionados:",
        len(productos)
    )

    guardar_resultados(
        productos
    )

    print(
        "✅ PROCESO COMPLETO FINALIZADO"
    )


if __name__ == "__main__":
    main()
