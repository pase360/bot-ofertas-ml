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


# =========================================================
# CONFIGURACION
# =========================================================

URL_MAS_VENDIDOS = (
    "https://www.mercadolibre.com.ar/mas-vendidos"
)

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
    datetime.now(
        timezone.utc
    ).strftime("%Y%m%d%H%M%S")
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
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans-Bold.ttf",

            "/usr/share/fonts/truetype/liberation2/"
            "LiberationSans-Bold.ttf",
        ]

    else:

        candidatos = [
            "/usr/share/fonts/truetype/dejavu/"
            "DejaVuSans.ttf",

            "/usr/share/fonts/truetype/liberation2/"
            "LiberationSans-Regular.ttf",
        ]

    for ruta in candidatos:

        if os.path.exists(ruta):

            return ImageFont.truetype(
                ruta,
                tamano
            )

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

    if not url:
        return False

    return (
        "/p/MLA" in url
        or "/MLA-" in url
    )


def nombre_desde_url(url):

    try:

        path = urlparse(
            url
        ).path

        partes = [
            p
            for p in path.split("/")
            if p
        ]

        candidato = ""

        for parte in partes:

            if parte.startswith("MLA"):
                continue

            if parte == "p":
                continue

            if len(parte) > len(candidato):
                candidato = parte

        candidato = (
            candidato
            .replace("-", " ")
            .replace("_", " ")
        )

        candidato = limpiar_texto(
            candidato
        )

        if candidato:

            return candidato.title()

    except Exception:
        pass

    return "Producto Mercado Libre"


def buscar_texto(
    contenedor,
    selectores
):

    for selector in selectores:

        try:

            elemento = contenedor.select_one(
                selector
            )

            if elemento:

                texto = limpiar_texto(
                    elemento.get_text(
                        " ",
                        strip=True
                    )
                )

                if texto:
                    return texto

        except Exception:
            pass

    return ""


# =========================================================
# CONTENEDOR DEL PRODUCTO
# =========================================================

def encontrar_contenedor(
    enlace
):

    nodo = enlace

    mejor = None

    for _ in range(10):

        nodo = nodo.parent

        if not isinstance(
            nodo,
            Tag
        ):
            break

        texto = limpiar_texto(
            nodo.get_text(
                " ",
                strip=True
            )
        )

        if not texto:
            continue

        if len(texto) > 2500:
            continue

        tiene_precio = "$" in texto

        tiene_imagen = (
            nodo.find("img")
            is not None
        )

        if (
            tiene_precio
            and tiene_imagen
        ):

            mejor = nodo

            clases = " ".join(
                nodo.get(
                    "class",
                    []
                )
            ).lower()

            if (
                "poly-card" in clases
                or "ui-search" in clases
                or "andes-card" in clases
            ):
                return nodo

    return mejor or enlace.parent


# =========================================================
# NOMBRE PRODUCTO
# =========================================================

def obtener_nombre(
    contenedor,
    enlace,
    url
):

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

            elementos = (
                contenedor.select(
                    selector
                )
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

            texto_lower = (
                texto.lower()
            )

            if not (
                8
                <= len(texto)
                <= 220
            ):
                continue

            if "$" in texto:
                continue

            if "% off" in texto_lower:
                continue

            if "más vendido" in texto_lower:
                continue

            if "mas vendido" in texto_lower:
                continue

            if "envío gratis" in texto_lower:
                continue

            if "envio gratis" in texto_lower:
                continue

            return texto

    # TITLE / ARIA-LABEL

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

        if (
            8
            <= len(valor)
            <= 220
        ):
            return valor

    # ALT DE IMAGEN

    for imagen in contenedor.find_all(
        "img"
    ):

        alt = limpiar_texto(
            imagen.get(
                "alt",
                ""
            )
        )

        if (
            8
            <= len(alt)
            <= 220
        ):

            if "$" not in alt:
                return alt

    # URL COMO ULTIMO RECURSO

    return nombre_desde_url(
        url
    )


# =========================================================
# IMAGEN PRODUCTO
# =========================================================

def obtener_url_imagen(
    contenedor
):

    for imagen in contenedor.find_all(
        "img"
    ):

        for atributo in [
            "data-src",
            "data-lazy",
            "src",
        ]:

            url = imagen.get(
                atributo
            )

            if (
                url
                and url.startswith("http")
                and ".svg" not in url.lower()
            ):

                return url

        srcset = imagen.get(
            "srcset"
        )

        if srcset:

            urls = []

            for opcion in srcset.split(
                ","
            ):

                url = (
                    opcion
                    .strip()
                    .split(" ")[0]
                )

                if url.startswith(
                    "http"
                ):
                    urls.append(
                        url
                    )

            if urls:
                return urls[-1]

    return ""


# =========================================================
# PRECIOS
# =========================================================

def leer_money_amount(
    elemento
):

    if not elemento:
        return ""

    fraction = elemento.select_one(
        ".andes-money-amount__fraction"
    )

    cents = elemento.select_one(
        ".andes-money-amount__cents"
    )

    if fraction:

        valor = limpiar_texto(
            fraction.get_text()
        )

        if cents:

            centavos = limpiar_texto(
                cents.get_text()
            )

            if centavos:
                return (
                    "$ "
                    + valor
                    + ","
                    + centavos
                )

        return "$ " + valor

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

        return (
            "$ "
            + match.group(1)
        )

    return ""


def obtener_precio_actual(
    contenedor
):

    selectores = [
        ".poly-price__current "
        ".andes-money-amount",

        ".ui-search-price__second-line "
        ".andes-money-amount",

        "[class*='current'] "
        ".andes-money-amount",
    ]

    for selector in selectores:

        elemento = contenedor.select_one(
            selector
        )

        valor = leer_money_amount(
            elemento
        )

        if valor:
            return valor

    # FALLBACK

    todos = contenedor.select(
        ".andes-money-amount"
    )

    for elemento in todos:

        clases = " ".join(
            elemento.get(
                "class",
                []
            )
        ).lower()

        padre_clases = ""

        if elemento.parent:

            padre_clases = " ".join(
                elemento.parent.get(
                    "class",
                    []
                )
            ).lower()

        combinado = (
            clases
            + " "
            + padre_clases
        )

        if (
            "previous" in combinado
            or "original" in combinado
        ):
            continue

        valor = leer_money_amount(
            elemento
        )

        if valor:
            return valor

    return "Precio no disponible"


def obtener_precio_anterior(
    contenedor
):

    selectores = [
        ".andes-money-amount--previous",

        ".poly-price__original "
        ".andes-money-amount",

        ".ui-search-price__original-value "
        ".andes-money-amount",

        "[class*='original'] "
        ".andes-money-amount",

        "[class*='previous'] "
        ".andes-money-amount",
    ]

    for selector in selectores:

        elemento = contenedor.select_one(
            selector
        )

        valor = leer_money_amount(
            elemento
        )

        if valor:
            return valor

    return ""


# =========================================================
# EXTRAER DATOS TARJETA
# =========================================================

def extraer_datos_tarjeta(
    enlace,
    contenedor
):

    url = limpiar_url(
        enlace.get(
            "href"
        )
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

    precio = obtener_precio_actual(
        contenedor
    )

    precio_anterior = (
        obtener_precio_anterior(
            contenedor
        )
    )

    # -----------------------------------------------------
    # DESCUENTO
    # -----------------------------------------------------

    descuento = buscar_texto(
        contenedor,
        [
            ".andes-money-amount__discount",

            "[class*='discount']",
        ]
    )

    if descuento:

        match = re.search(
            r"(\d{1,2}%\s*OFF)",
            descuento,
            re.IGNORECASE
        )

        if match:

            descuento = (
                match.group(1)
                .upper()
            )

        else:

            descuento = ""

    if not descuento:

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

    # -----------------------------------------------------
    # CUOTAS
    # -----------------------------------------------------

    cuotas = buscar_texto(
        contenedor,
        [
            "[class*='installment']",

            "[class*='payment']",
        ]
    )

    if cuotas:

        match = re.search(
            (
                r"((?:Mismo precio(?: en)?\s+)?"
                r"\d{1,2}\s+cuotas"
                r"(?:\s+sin\s+inter[eé]s)?"
                r"(?:\s+de\s+\$\s*"
                r"[\d\.\,]+)?)"
            ),
            cuotas,
            re.IGNORECASE
        )

        if match:

            cuotas = limpiar_texto(
                match.group(1)
            )

        else:

            cuotas = ""

    if not cuotas:

        match = re.search(
            (
                r"((?:Mismo precio(?: en)?\s+)?"
                r"\d{1,2}\s+cuotas"
                r"(?:\s+sin\s+inter[eé]s)?"
                r"(?:\s+de\s+\$\s*"
                r"[\d\.\,]+)?)"
            ),
            texto,
            re.IGNORECASE
        )

        if match:

            cuotas = limpiar_texto(
                match.group(1)
            )

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
    # CALIFICACION
    # -----------------------------------------------------

    rating = ""

    selectores_rating = [
        ".poly-reviews__rating",
        ".ui-search-reviews__rating-number",
        "[class*='rating']",
    ]

    texto_rating = buscar_texto(
        contenedor,
        selectores_rating
    )

    if texto_rating:

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

    # -----------------------------------------------------
    # VENDIDOS
    # -----------------------------------------------------

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
# OBTENER MAS VENDIDOS
# =========================================================

def obtener_productos():

    print(
        "--- DESCARGANDO MAS VENDIDOS ---"
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
            enlace.get(
                "href"
            )
        )

        if not es_producto(
            url
        ):
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
            puntos += 5

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

        if datos["vendidos"]:
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
            and
            producto["imagen_url"]
            and
            producto["nombre"]
            != "Producto Mercado Libre"
        )
    ]

    candidatos = (
        validos[:40]
        if len(validos) >= 10
        else productos[:40]
    )

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
            f"{producto['descuento']} | "
            f"{producto['cuotas']}"
        )

    return seleccionados


# =========================================================
# DESCARGAR FOTO
# =========================================================

def descargar_imagen(
    url
):

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
            "RGBA"
        )

    except Exception as e:

        print(
            "ERROR imagen:",
            e
        )

        return None


# =========================================================
# AJUSTAR TEXTO
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

    lineas.append(
        linea
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
# LOGO REAL
# =========================================================

def colocar_logo(
    imagen
):

    if not LOGO_PATH.exists():

        print(
            "ADVERTENCIA: "
            "logo_cazadores.png no encontrado"
        )

        return

    try:

        logo = Image.open(
            LOGO_PATH
        ).convert(
            "RGBA"
        )

        logo.thumbnail(
            (
                150,
                150
            ),
            Image.LANCZOS
        )

        x = 58
        y = 38

        imagen.paste(
            logo,
            (x, y),
            logo
        )

    except Exception as e:

        print(
            "ERROR cargando logo:",
            e
        )


# =========================================================
# CREAR PLACA FINAL
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
        (
            ANCHO,
            ALTO
        ),
        (
            247,
            247,
            245
        )
    )

    draw = ImageDraw.Draw(
        imagen
    )

    # TARJETA

    draw.rounded_rectangle(
        (
            25,
            20,
            1055,
            1328
        ),
        radius=40,
        fill=(
            255,
            255,
            255
        ),
        outline=(
            225,
            225,
            225
        ),
        width=2
    )

    # LOGO

    colocar_logo(
        imagen
    )

    # TITULO CANAL

    draw.text(
        (
            230,
            55
        ),
        "Cazadores de Ofertas",
        font=fuente(
            47,
            True
        ),
        fill=(
            10,
            10,
            10
        )
    )

    draw.text(
        (
            232,
            116
        ),
        "Las mejores ofertas, todos los días",
        font=fuente(
            27
        ),
        fill=(
            75,
            75,
            75
        )
    )

    # FOTO PRODUCTO

    producto = descargar_imagen(
        datos["imagen_url"]
    )

    area_x0 = 65
    area_y0 = 195
    area_x1 = 1015
    area_y1 = 565

    if producto:

        producto.thumbnail(
            (
                area_x1
                - area_x0,

                area_y1
                - area_y0
            ),
            Image.LANCZOS
        )

        x = (
            area_x0
            + (
                (
                    area_x1
                    - area_x0
                )
                - producto.width
            )
            // 2
        )

        y = (
            area_y0
            + (
                (
                    area_y1
                    - area_y0
                )
                - producto.height
            )
            // 2
        )

        imagen.paste(
            producto,
            (
                x,
                y
            ),
            producto
        )

    # MAS VENDIDO

    y = 585

    draw.rounded_rectangle(
        (
            60,
            y,
            360,
            y + 64
        ),
        radius=13,
        fill=(
            255,
            92,
            20
        )
    )

    etiqueta = (
        datos["ranking"]
        if datos["ranking"]
        else "MÁS VENDIDO"
    )

    draw.text(
        (
            83,
            y + 13
        ),
        etiqueta[:24],
        font=fuente(
            29,
            True
        ),
        fill="white"
    )

    # NOMBRE PRODUCTO

    y += 90

    font_titulo = fuente(
        48,
        True
    )

    lineas = ajustar_texto(
        draw,
        datos["nombre"],
        font_titulo,
        930
    )

    y = dibujar_lineas(
        draw,
        lineas[:3],
        65,
        y,
        font_titulo,
        (
            10,
            10,
            10
        ),
        5
    )

    # RATING Y VENDIDOS

    metadata = []

    if datos["rating"]:

        metadata.append(
            "★ "
            + datos["rating"]
        )

    if datos["vendidos"]:

        metadata.append(
            datos["vendidos"]
        )

    if metadata:

        y += 6

        draw.text(
            (
                65,
                y
            ),
            "  |  ".join(
                metadata
            ),
            font=fuente(
                29,
                True
            ),
            fill=(
                35,
                35,
                35
            )
        )

        y += 50

    # PRECIO ANTERIOR

    if datos["precio_anterior"]:

        font_anterior = fuente(
            34
        )

        draw.text(
            (
                65,
                y
            ),
            datos["precio_anterior"],
            font=font_anterior,
            fill=(
                105,
                105,
                105
            )
        )

        caja_anterior = draw.textbbox(
            (
                65,
                y
            ),
            datos["precio_anterior"],
            font=font_anterior
        )

        altura_linea = (
            caja_anterior[1]
            + caja_anterior[3]
        ) // 2

        draw.line(
            (
                caja_anterior[0],
                altura_linea,
                caja_anterior[2],
                altura_linea
            ),
            fill=(
                105,
                105,
                105
            ),
            width=3
        )

        y += 48

    # PRECIO ACTUAL

    font_precio = fuente(
        68,
        True
    )

    draw.text(
        (
            65,
            y
        ),
        datos["precio"],
        font=font_precio,
        fill=(
            0,
            148,
            76
        )
    )

    caja_precio = draw.textbbox(
        (
            65,
            y
        ),
        datos["precio"],
        font=font_precio
    )

    # DESCUENTO

    if datos["descuento"]:

        x_desc = min(
            caja_precio[2]
            + 25,
            800
        )

        draw.rounded_rectangle(
            (
                x_desc,
                y + 10,
                x_desc + 195,
                y + 70
            ),
            radius=10,
            fill=(
                0,
                153,
                82
            )
        )

        draw.text(
            (
                x_desc + 15,
                y + 18
            ),
            datos["descuento"],
            font=fuente(
                30,
                True
            ),
            fill="white"
        )

    y += 92

    # CUOTAS

    draw.text(
        (
            65,
            y
        ),
        datos["cuotas"][:85],
        font=fuente(
            33,
            True
        ),
        fill=(
            25,
            25,
            25
        )
    )

    y += 68

    # INFO

    draw.text(
        (
            65,
            y
        ),
        "✓ Oferta disponible en Mercado Libre",
        font=fuente(
            27
        ),
        fill=(
            60,
            60,
            60
        )
    )

    y += 43

    draw.text(
        (
            65,
            y
        ),
        "✓ Precio y disponibilidad pueden variar",
        font=fuente(
            27
        ),
        fill=(
            60,
            60,
            60
        )
    )

    # CTA VISUAL

    boton_y = 1135

    draw.rounded_rectangle(
        (
            55,
            boton_y,
            1025,
            boton_y + 130
        ),
        radius=30,
        fill=(
            220,
            248,
            228
        ),
        outline=(
            70,
            220,
            120
        ),
        width=3
    )

    draw.text(
        (
            100,
            boton_y + 24
        ),
        "Ver oferta en Mercado Libre",
        font=fuente(
            37,
            True
        ),
        fill=(
            0,
            105,
            55
        )
    )

    draw.text(
        (
            100,
            boton_y + 77
        ),
        "Link afiliado real debajo de esta imagen",
        font=fuente(
            27
        ),
        fill=(
            65,
            75,
            90
        )
    )

    # PIE

    draw.text(
        (
            105,
            1295
        ),
        "Si comprás desde el enlace apoyás al canal",
        font=fuente(
            24
        ),
        fill=(
            70,
            75,
            90
        )
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
# LIMPIAR IMAGENES ANTERIORES
# =========================================================

def limpiar_ofertas():

    for archivo in CARPETA_OFERTAS.glob(
        "oferta_*.png"
    ):

        try:

            archivo.unlink()

        except Exception:

            pass


# =========================================================
# GUARDAR TANDA
# =========================================================

def guardar_tanda(
    productos
):

    limpiar_ofertas()

    links = []
    datos_txt = []
    imagenes = []

    for numero, datos in enumerate(
        productos,
        start=1
    ):

        nombre_archivo = (
            crear_imagen_oferta(
                datos,
                numero
            )
        )

        links.append(
            datos["url_original"]
        )

        nombre = (
            datos["nombre"]
            .replace(
                "|",
                "-"
            )
        )

        precio = (
            datos["precio"]
            .replace(
                "|",
                "-"
            )
        )

        cuotas = (
            datos["cuotas"]
            .replace(
                "|",
                "-"
            )
        )

        datos_txt.append(
            f"{nombre} | "
            f"{precio} | "
            f"{cuotas}"
        )

        imagenes.append(
            f"{RAW_BASE}/"
            f"{nombre_archivo}"
        )

    Path(
        "ultima_tanda.txt"
    ).write_text(
        "\n".join(
            links
        ),
        encoding="utf-8"
    )

    Path(
        "datos_tanda.txt"
    ).write_text(
        "\n".join(
            datos_txt
        ),
        encoding="utf-8"
    )

    Path(
        "imagenes_tanda.txt"
    ).write_text(
        "\n".join(
            imagenes
        ),
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

    print(
        "✅ PROCESO COMPLETO FINALIZADO"
    )


if __name__ == "__main__":
    main()
