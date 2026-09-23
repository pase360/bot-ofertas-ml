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
# ELEMENTOS VISUALES MERCADO LIBRE / CANAL
# =========================================================

def texto_centrado(draw, texto, y, font, color, x0=0, x1=ANCHO):
    caja = draw.textbbox((0, 0), texto, font=font)
    ancho = caja[2] - caja[0]
    x = x0 + ((x1 - x0) - ancho) // 2
    draw.text((x, y), texto, font=font, fill=color)


def colocar_logo_mercadolibre(imagen, x, y, ancho_max=150, alto_max=95):
    """
    Usa logo_mercadolibre.png si existe.
    El archivo puede ser solamente el isotipo del apretón de manos.
    Debajo se dibuja el nombre y el slogan para mantener el aspecto aprobado.
    """

    draw = ImageDraw.Draw(imagen)

    if LOGO_ML_PATH.exists():
        try:
            logo = Image.open(LOGO_ML_PATH).convert("RGBA")
            logo.thumbnail(
                (ancho_max, alto_max),
                Image.LANCZOS
            )

            pos_x = x + (ancho_max - logo.width) // 2

            imagen.paste(
                logo,
                (pos_x, y),
                logo
            )

        except Exception as e:
            print("ERROR logo Mercado Libre:", e)

    else:
        # Fallback visual si todavía no se subió el PNG.
        draw.ellipse(
            (
                x + 12,
                y,
                x + ancho_max - 12,
                y + alto_max
            ),
            fill=(255, 230, 0),
            outline=(45, 50, 119),
            width=5
        )

        draw.text(
            (x + 41, y + 29),
            "ML",
            font=fuente(29, True),
            fill=(45, 50, 119)
        )

    texto_centrado(
        draw,
        "mercado",
        y + alto_max + 2,
        fuente(24, True),
        (45, 50, 119),
        x,
        x + ancho_max
    )

    texto_centrado(
        draw,
        "libre",
        y + alto_max + 28,
        fuente(24, True),
        (45, 50, 119),
        x,
        x + ancho_max
    )

    texto_centrado(
        draw,
        "Lo mejor",
        y + alto_max + 59,
        fuente(15, True),
        (45, 50, 119),
        x,
        x + ancho_max
    )

    texto_centrado(
        draw,
        "está acá",
        y + alto_max + 76,
        fuente(15, True),
        (45, 50, 119),
        x,
        x + ancho_max
    )


def dibujar_icono_lupa(draw, cx, cy):
    draw.ellipse(
        (cx - 18, cy - 18, cx + 11, cy + 11),
        outline=(15, 15, 15),
        width=4
    )
    draw.line(
        (cx + 7, cy + 8, cx + 24, cy + 25),
        fill=(15, 15, 15),
        width=5
    )


def dibujar_icono_simple(draw, cx, cy, tipo):
    fondo = (255, 247, 194)

    draw.ellipse(
        (cx - 32, cy - 32, cx + 32, cy + 32),
        fill=fondo
    )

    color = (20, 20, 20)

    if tipo == "ranking":
        # podio simple
        draw.rectangle(
            (cx - 21, cy + 5, cx - 8, cy + 20),
            outline=color,
            width=3
        )
        draw.rectangle(
            (cx - 4, cy - 7, cx + 9, cy + 20),
            outline=color,
            width=3
        )
        draw.rectangle(
            (cx + 13, cy + 1, cx + 26, cy + 20),
            outline=color,
            width=3
        )

    elif tipo == "cuotas":
        # tres tarjetas superpuestas
        for despl in (0, 7, 14):
            draw.rounded_rectangle(
                (
                    cx - 22 + despl,
                    cy - 16 + despl // 2,
                    cx + 11 + despl,
                    cy + 8 + despl // 2
                ),
                radius=4,
                outline=color,
                width=3
            )

    else:
        # estrella / destacado
        puntos = [
            (cx, cy - 23),
            (cx + 7, cy - 7),
            (cx + 24, cy - 5),
            (cx + 11, cy + 7),
            (cx + 15, cy + 24),
            (cx, cy + 14),
            (cx - 15, cy + 24),
            (cx - 11, cy + 7),
            (cx - 24, cy - 5),
            (cx - 7, cy - 7),
        ]
        draw.polygon(
            puntos,
            outline=color
        )


def datos_laterales(datos):
    """
    Usa solamente información real ya extraída de Mercado Libre.
    No inventa características técnicas del producto.
    """

    resultado = []

    if datos.get("ranking"):
        resultado.append(
            ("ranking", datos["ranking"])
        )
    else:
        resultado.append(
            ("ranking", "Oferta seleccionada")
        )

    if (
        datos.get("cuotas")
        and datos["cuotas"] != "Consultar cuotas"
    ):
        resultado.append(
            ("cuotas", datos["cuotas"])
        )
    else:
        resultado.append(
            ("cuotas", "Consultar cuotas")
        )

    if datos.get("vendidos"):
        resultado.append(
            ("destacado", datos["vendidos"])
        )
    elif datos.get("rating"):
        resultado.append(
            ("destacado", "★ " + datos["rating"])
        )
    else:
        resultado.append(
            ("destacado", "Producto destacado")
        )

    return resultado[:3]


def dibujar_medios_pago(draw, y):
    """
    Bloque visual compacto igual al estilo aprobado.
    No afirma cuotas ni beneficios específicos.
    """

    draw.rounded_rectangle(
        (
            70,
            y,
            1010,
            y + 82
        ),
        radius=18,
        fill=(247, 247, 247),
        outline=(230, 230, 230),
        width=2
    )

    draw.text(
        (92, y + 25),
        "Medios de pago",
        font=fuente(25, True),
        fill=(18, 18, 18)
    )

    x = 345

    # Mastercard
    draw.ellipse(
        (x, y + 22, x + 39, y + 61),
        fill=(235, 0, 27)
    )
    draw.ellipse(
        (x + 27, y + 22, x + 66, y + 61),
        fill=(255, 153, 0)
    )
    x += 84

    # VISA
    draw.rounded_rectangle(
        (x, y + 18, x + 94, y + 64),
        radius=10,
        fill="white",
        outline=(223, 223, 223),
        width=2
    )
    draw.text(
        (x + 15, y + 28),
        "VISA",
        font=fuente(22, True),
        fill=(28, 76, 151)
    )
    x += 106

    # AMEX
    draw.rounded_rectangle(
        (x, y + 18, x + 78, y + 64),
        radius=10,
        fill=(31, 144, 203)
    )
    draw.text(
        (x + 9, y + 31),
        "AMEX",
        font=fuente(16, True),
        fill="white"
    )
    x += 90

    # Mercado Pago
    draw.rounded_rectangle(
        (x, y + 18, x + 148, y + 64),
        radius=10,
        fill="white",
        outline=(223, 223, 223),
        width=2
    )
    draw.text(
        (x + 10, y + 31),
        "mercado pago",
        font=fuente(16, True),
        fill=(40, 112, 190)
    )
    x += 160

    # Naranja X
    draw.rounded_rectangle(
        (x, y + 18, x + 105, y + 64),
        radius=10,
        fill="white",
        outline=(223, 223, 223),
        width=2
    )
    draw.text(
        (x + 8, y + 31),
        "NaranjaX",
        font=fuente(15, True),
        fill=(230, 84, 25)
    )
    x += 117

    draw.rounded_rectangle(
        (x, y + 18, x + 55, y + 64),
        radius=10,
        fill="white",
        outline=(223, 223, 223),
        width=2
    )
    draw.text(
        (x + 11, y + 29),
        "+3",
        font=fuente(19, True),
        fill=(30, 30, 30)
    )


def dibujar_aviso_independiente(draw, y):
    texto_centrado(
        draw,
        "Canal independiente. No oficial.",
        y,
        fuente(17, True),
        (95, 95, 95),
        40,
        1040
    )


# =========================================================
# CREAR PLACA FINAL DE PRODUCTO
# =========================================================

def crear_imagen_oferta(datos, numero):

    nombre_archivo = (
        f"oferta_final_{numero:02d}_{VERSION}.png"
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

    # TARJETA BLANCA PRINCIPAL

    draw.rounded_rectangle(
        (
            28,
            22,
            1052,
            1325
        ),
        radius=38,
        fill=(255, 255, 255),
        outline=(231, 231, 231),
        width=2
    )

    # =====================================================
    # CABECERA: IGUAL AL DISEÑO APROBADO
    # =====================================================

    colocar_logo(imagen)

    draw.text(
        (225, 53),
        "Cazadores de Ofertas",
        font=fuente(43, True),
        fill=(10, 10, 10)
    )

    draw.text(
        (227, 105),
        "Las mejores ofertas, todos los días",
        font=fuente(23),
        fill=(72, 72, 72)
    )

    colocar_logo_mercadolibre(
        imagen,
        840,
        35,
        135,
        72
    )

    # BANDA AMARILLA "OFERTA ENCONTRADA..."

    banda_x0 = 78
    banda_y0 = 170
    banda_x1 = 695
    banda_y1 = 228

    draw.rounded_rectangle(
        (
            banda_x0,
            banda_y0,
            banda_x1,
            banda_y1
        ),
        radius=25,
        fill=(255, 248, 201)
    )

    dibujar_icono_lupa(
        draw,
        110,
        199
    )

    draw.text(
        (145, 184),
        "Oferta encontrada en",
        font=fuente(24),
        fill=(25, 25, 25)
    )

    draw.text(
        (405, 184),
        "Mercado Libre",
        font=fuente(24, True),
        fill=(25, 25, 25)
    )

    # =====================================================
    # COLUMNA IZQUIERDA DE INFORMACIÓN REAL
    # =====================================================

    laterales = datos_laterales(datos)
    ys = [310, 425, 540]

    for indice, (tipo, texto) in enumerate(laterales):

        cy = ys[indice]

        dibujar_icono_simple(
            draw,
            115,
            cy,
            tipo
        )

        lineas_lateral = ajustar_texto(
            draw,
            texto,
            fuente(19, True),
            190
        )

        dibujar_lineas(
            draw,
            lineas_lateral[:3],
            165,
            cy - 24,
            fuente(19, True),
            (30, 30, 30),
            2
        )

    # =====================================================
    # FOTO DEL PRODUCTO GRANDE
    # =====================================================

    producto = descargar_imagen(
        datos["imagen_url"]
    )

    area_x0 = 285
    area_y0 = 235
    area_x1 = 990
    area_y1 = 650

    if producto:

        producto.thumbnail(
            (
                area_x1 - area_x0,
                area_y1 - area_y0
            ),
            Image.LANCZOS
        )

        x_prod = (
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

        y_prod = (
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
            (x_prod, y_prod),
            producto
        )

    # =====================================================
    # NOMBRE
    # =====================================================

    y = 675

    font_titulo = fuente(
        42,
        True
    )

    lineas = ajustar_texto(
        draw,
        datos["nombre"],
        font_titulo,
        920
    )

    y = dibujar_lineas(
        draw,
        lineas[:3],
        72,
        y,
        font_titulo,
        (10, 10, 10),
        3
    )

    # =====================================================
    # PRECIO / DESCUENTO REAL
    # =====================================================

    y += 12

    if datos["precio_anterior"]:

        font_anterior = fuente(25)

        draw.text(
            (72, y),
            datos["precio_anterior"],
            font=font_anterior,
            fill=(110, 110, 110)
        )

        caja = draw.textbbox(
            (72, y),
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
            fill=(110, 110, 110),
            width=3
        )

        y += 34

    font_precio = fuente(
        61,
        True
    )

    draw.text(
        (72, y),
        datos["precio"],
        font=font_precio,
        fill=(30, 118, 239)
    )

    caja_precio = draw.textbbox(
        (72, y),
        datos["precio"],
        font=font_precio
    )

    # Descuento solamente si Mercado Libre realmente lo mostró.
    if datos["descuento"]:

        x_desc = min(
            caja_precio[2] + 22,
            820
        )

        draw.rounded_rectangle(
            (
                x_desc,
                y + 11,
                x_desc + 165,
                y + 62
            ),
            radius=10,
            fill=(0, 156, 82)
        )

        draw.text(
            (x_desc + 16, y + 21),
            datos["descuento"],
            font=fuente(24, True),
            fill="white"
        )

    # =====================================================
    # MEDIOS DE PAGO
    # =====================================================

    medios_y = 980

    dibujar_medios_pago(
        draw,
        medios_y
    )

    # =====================================================
    # BARRA NEGRA APROBADA
    # =====================================================

    envio_y = 1080

    draw.rounded_rectangle(
        (
            90,
            envio_y,
            990,
            envio_y + 68
        ),
        radius=15,
        fill=(14, 14, 14)
    )

    # camión simple
    draw.rectangle(
        (
            125,
            envio_y + 23,
            163,
            envio_y + 46
        ),
        outline="white",
        width=3
    )
    draw.rectangle(
        (
            163,
            envio_y + 30,
            183,
            envio_y + 46
        ),
        outline="white",
        width=3
    )
    draw.ellipse(
        (
            132,
            envio_y + 42,
            145,
            envio_y + 55
        ),
        fill="white"
    )
    draw.ellipse(
        (
            166,
            envio_y + 42,
            179,
            envio_y + 55
        ),
        fill="white"
    )

    draw.text(
        (210, envio_y + 18),
        "ENVÍO PROTEGIDO POR MERCADO LIBRE",
        font=fuente(27, True),
        fill="white"
    )

    # =====================================================
    # LINK DEL POST
    # =====================================================

    link_y = 1165

    draw.rounded_rectangle(
        (
            90,
            link_y,
            990,
            link_y + 72
        ),
        radius=22,
        fill=(255, 250, 230),
        outline=(239, 226, 175),
        width=2
    )

    # icono de eslabón simple
    draw.ellipse(
        (
            118,
            link_y + 23,
            143,
            link_y + 48
        ),
        outline=(45, 50, 119),
        width=4
    )
    draw.ellipse(
        (
            138,
            link_y + 23,
            163,
            link_y + 48
        ),
        outline=(45, 50, 119),
        width=4
    )

    draw.text(
        (185, link_y + 22),
        "Tocá el link del post para ver la publicación",
        font=fuente(25, True),
        fill=(45, 50, 119)
    )

    # ACLARACIÓN NO OFICIAL

    dibujar_aviso_independiente(
        draw,
        1265
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
# PROPAGANDA DEL CANAL
# =========================================================

def crear_imagen_promo_canal():

    nombre_archivo = "promo_canal.png"

    salida = (
        CARPETA_OFERTAS
        / nombre_archivo
    )

    imagen = Image.new(
        "RGB",
        (ANCHO, ALTO),
        (250, 250, 248)
    )

    draw = ImageDraw.Draw(imagen)

    draw.rounded_rectangle(
        (
            25,
            20,
            1055,
            1328
        ),
        radius=40,
        fill=(255, 255, 255),
        outline=(226, 226, 226),
        width=2
    )

    # CABECERA IGUAL AL ESTILO APROBADO

    colocar_logo(imagen)

    draw.text(
        (230, 50),
        "Cazadores de Ofertas",
        font=fuente(45, True),
        fill=(10, 10, 10)
    )

    draw.text(
        (232, 106),
        "Las mejores ofertas de Mercado Libre, todos los días",
        font=fuente(23),
        fill=(70, 70, 70)
    )

    colocar_logo_mercadolibre(
        imagen,
        842,
        35,
        132,
        70
    )

    # MENSAJE AMARILLO

    draw.rounded_rectangle(
        (
            65,
            190,
            740,
            355
        ),
        radius=30,
        fill=(255, 248, 201)
    )

    lineas = ajustar_texto(
        draw,
        (
            "Encontramos, filtramos y compartimos "
            "oportunidades reales para que ahorres tiempo y dinero."
        ),
        fuente(34, True),
        610
    )

    dibujar_lineas(
        draw,
        lineas[:4],
        92,
        218,
        fuente(34, True),
        (15, 15, 15),
        4
    )

    # BENEFICIOS LATERALES

    beneficios = [
        ("Ofertas reales", "y seleccionadas"),
        ("Productos", "destacados"),
        ("Links listos", "para comprar"),
        ("Ahorro", "de tiempo"),
    ]

    iconos = ["ranking", "destacado", "cuotas", "ranking"]
    y = 405

    for i, (titulo, detalle) in enumerate(beneficios):

        dibujar_icono_simple(
            draw,
            120,
            y + 36,
            iconos[i]
        )

        draw.text(
            (175, y + 5),
            titulo,
            font=fuente(29, True),
            fill=(15, 15, 15)
        )

        draw.text(
            (175, y + 43),
            detalle,
            font=fuente(25),
            fill=(40, 40, 40)
        )

        y += 118

    # TELÉFONO SIMULADO

    phone_x0 = 565
    phone_y0 = 390
    phone_x1 = 985
    phone_y1 = 1010

    draw.rounded_rectangle(
        (
            phone_x0,
            phone_y0,
            phone_x1,
            phone_y1
        ),
        radius=48,
        fill=(20, 20, 20)
    )

    draw.rounded_rectangle(
        (
            phone_x0 + 17,
            phone_y0 + 17,
            phone_x1 - 17,
            phone_y1 - 17
        ),
        radius=38,
        fill=(248, 248, 248)
    )

    # cabecera dentro del celular
    draw.ellipse(
        (
            phone_x0 + 38,
            phone_y0 + 50,
            phone_x0 + 105,
            phone_y0 + 117
        ),
        fill=(255, 230, 0),
        outline=(25, 25, 25),
        width=3
    )

    draw.text(
        (phone_x0 + 125, phone_y0 + 52),
        "Cazadores de Ofertas",
        font=fuente(22, True),
        fill=(15, 15, 15)
    )

    draw.text(
        (phone_x0 + 125, phone_y0 + 82),
        "Canal de WhatsApp",
        font=fuente(18),
        fill=(95, 95, 95)
    )

    # tarjetas internas estilo WhatsApp
    mensajes = [
        (
            "Las mejores ofertas,\ntodos los días",
            (224, 248, 225)
        ),
        (
            "Electrónica, hogar,\nmoda y mucho más",
            (255, 255, 255)
        ),
        (
            "Aprovechá antes\nque se agoten",
            (224, 248, 225)
        ),
    ]

    my = phone_y0 + 155

    for mensaje, color in mensajes:

        draw.rounded_rectangle(
            (
                phone_x0 + 45,
                my,
                phone_x1 - 45,
                my + 118
            ),
            radius=24,
            fill=color,
            outline=(230, 230, 230),
            width=1
        )

        lineas_m = mensaje.split("\n")

        pos_y = my + 22

        for linea in lineas_m:

            draw.text(
                (phone_x0 + 70, pos_y),
                linea,
                font=fuente(22, True),
                fill=(35, 35, 35)
            )

            pos_y += 30

        my += 145

    # GLOBO "OFERTAS TODOS LOS DÍAS"

    draw.rounded_rectangle(
        (
            360,
            875,
            660,
            985
        ),
        radius=34,
        fill=(255, 230, 0)
    )

    texto_centrado(
        draw,
        "Ofertas",
        898,
        fuente(31, True),
        (45, 50, 119),
        360,
        660
    )

    texto_centrado(
        draw,
        "todos los días",
        937,
        fuente(25, True),
        (45, 50, 119),
        360,
        660
    )

    # CTA VERDE

    draw.rounded_rectangle(
        (
            85,
            1035,
            995,
            1165
        ),
        radius=60,
        fill=(29, 190, 94)
    )

    texto_centrado(
        draw,
        "Seguí el canal y no te pierdas",
        1064,
        fuente(33, True),
        "white",
        85,
        995
    )

    texto_centrado(
        draw,
        "ninguna oferta",
        1105,
        fuente(33, True),
        "white",
        85,
        995
    )

    # CHIPS INFERIORES

    chips = [
        "100% GRATIS",
        "CANAL INDEPENDIENTE",
        "OFERTAS TODOS LOS DÍAS",
    ]

    xs = [
        (82, 310),
        (326, 695),
        (711, 1000),
    ]

    for texto, (x0, x1) in zip(chips, xs):

        texto_centrado(
            draw,
            texto,
            1207,
            fuente(18, True),
            (40, 40, 40),
            x0,
            x1
        )

    dibujar_aviso_independiente(
        draw,
        1272
    )

    imagen.save(
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
