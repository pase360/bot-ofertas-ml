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
# MANO APUNTANDO HACIA ABAJO
# =========================================================

def dibujar_mano_abajo(draw, x, y):

    verde = (0, 105, 65)

    # Palma
    draw.rounded_rectangle(
        (
            x,
            y,
            x + 62,
            y + 48
        ),
        radius=17,
        outline=verde,
        width=8
    )

    # Dedo
    draw.rounded_rectangle(
        (
            x + 22,
            y + 35,
            x + 42,
            y + 92
        ),
        radius=10,
        fill=verde
    )

    # Pulgar
    draw.line(
        (
            x + 4,
            y + 28,
            x - 18,
            y + 48
        ),
        fill=verde,
        width=8
    )

    # Rayitas debajo
    draw.line(
        (
            x + 32,
            y + 102,
            x + 32,
            y + 119
        ),
        fill=verde,
        width=5
    )

    draw.line(
        (
            x + 10,
            y + 98,
            x,
            y + 111
        ),
        fill=verde,
        width=5
    )

    draw.line(
        (
            x + 54,
            y + 98,
            x + 65,
            y + 111
        ),
        fill=verde,
        width=5
    )


# =========================================================
# CREAR PLACA FINAL
# =========================================================

def crear_imagen_oferta(datos, numero):

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
        (247, 247, 245)
    )

    draw = ImageDraw.Draw(imagen)

    # TARJETA

    draw.rounded_rectangle(
        (
            25,
            20,
            1055,
            1328
        ),
        radius=40,
        fill=(255, 255, 255),
        outline=(225, 225, 225),
        width=2
    )

    # LOGO REAL

    colocar_logo(imagen)

    # CABECERA

    draw.text(
        (230, 55),
        "Cazadores de Ofertas",
        font=fuente(47, True),
        fill=(10, 10, 10)
    )

    draw.text(
        (232, 116),
        "Las mejores ofertas, todos los días",
        font=fuente(27),
        fill=(75, 75, 75)
    )

    # FOTO DEL PRODUCTO

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
                area_x1 - area_x0,
                area_y1 - area_y0
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
            (x, y),
            producto
        )

    # RANKING

    y = 585

    draw.rounded_rectangle(
        (
            60,
            y,
            360,
            y + 64
        ),
        radius=13,
        fill=(255, 92, 20)
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
        font=fuente(29, True),
        fill="white"
    )

    # NOMBRE

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
        (10, 10, 10),
        5
    )

    # RATING / VENDIDOS

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

        y += 6

        draw.text(
            (65, y),
            "  |  ".join(
                metadata
            ),
            font=fuente(29, True),
            fill=(35, 35, 35)
        )

        y += 50

    # PRECIO ANTERIOR

    if datos["precio_anterior"]:

        font_anterior = fuente(34)

        draw.text(
            (65, y),
            datos["precio_anterior"],
            font=font_anterior,
            fill=(105, 105, 105)
        )

        caja = draw.textbbox(
            (65, y),
            datos["precio_anterior"],
            font=font_anterior
        )

        medio = (
            caja[1]
            + caja[3]
        ) // 2

        draw.line(
            (
                caja[0],
                medio,
                caja[2],
                medio
            ),
            fill=(105, 105, 105),
            width=3
        )

        y += 48

    # PRECIO ACTUAL

    font_precio = fuente(
        68,
        True
    )

    draw.text(
        (65, y),
        datos["precio"],
        font=font_precio,
        fill=(0, 148, 76)
    )

    caja_precio = draw.textbbox(
        (65, y),
        datos["precio"],
        font=font_precio
    )

    # DESCUENTO

    if datos["descuento"]:

        x_desc = min(
            caja_precio[2] + 25,
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
            fill=(0, 153, 82)
        )

        draw.text(
            (
                x_desc + 15,
                y + 18
            ),
            datos["descuento"],
            font=fuente(30, True),
            fill="white"
        )

    y += 92

    # CUOTAS

    draw.text(
        (65, y),
        datos["cuotas"][:85],
        font=fuente(33, True),
        fill=(25, 25, 25)
    )

    y += 68

    # INFORMACION

    draw.text(
        (65, y),
        "Oferta disponible en Mercado Libre",
        font=fuente(27),
        fill=(60, 60, 60)
    )

    y += 43

    draw.text(
        (65, y),
        "Precio y disponibilidad pueden variar",
        font=fuente(27),
        fill=(60, 60, 60)
    )

    # =====================================================
    # BOTON VISUAL FINAL
    # =====================================================

    boton_y = 1125

    draw.rounded_rectangle(
        (
            55,
            boton_y,
            1025,
            boton_y + 155
        ),
        radius=30,
        fill=(220, 248, 228),
        outline=(50, 215, 105),
        width=4
    )

    draw.text(
        (
            100,
            boton_y + 24
        ),
        "Compralo acá",
        font=fuente(43, True),
        fill=(0, 100, 55)
    )

    draw.text(
        (
            100,
            boton_y + 82
        ),
        "Tocá el link de abajo",
        font=fuente(30),
        fill=(60, 70, 80)
    )

    dibujar_mano_abajo(
        draw,
        845,
        boton_y + 27
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
