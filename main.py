import os
import random
import re
from io import BytesIO
from pathlib import Path

import requests
from bs4 import BeautifulSoup
from PIL import Image, ImageDraw, ImageFont
from playwright.sync_api import (
    sync_playwright,
    TimeoutError as PlaywrightTimeoutError,
)


# =========================================================
# CONFIGURACION
# =========================================================

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}

CANTIDAD_PRODUCTOS = 10

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

    texto = re.sub(
        r"\s+",
        " ",
        str(texto)
    )

    return texto.strip()


def obtener_texto_primero(
    page,
    selectores
):

    for selector in selectores:

        try:
            elemento = page.locator(
                selector
            ).first

            if elemento.count() > 0:

                texto = limpiar_texto(
                    elemento.inner_text(
                        timeout=2500
                    )
                )

                if texto:
                    return texto

        except Exception:
            pass

    return ""


def obtener_atributo_primero(
    page,
    selectores,
    atributo
):

    for selector in selectores:

        try:
            elemento = page.locator(
                selector
            ).first

            if elemento.count() > 0:

                valor = elemento.get_attribute(
                    atributo,
                    timeout=2500
                )

                if valor:
                    return valor

        except Exception:
            pass

    return ""


def extraer_precio(texto):

    texto = limpiar_texto(texto)

    if not texto:
        return ""

    match = re.search(
        r"\$\s*([\d\.]+(?:,\d+)?)",
        texto
    )

    if match:
        return "$ " + match.group(1)

    match = re.search(
        r"([\d\.]+(?:,\d+)?)",
        texto
    )

    if match:
        return "$ " + match.group(1)

    return texto


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

        bbox = draw.textbbox(
            (0, 0),
            prueba,
            font=font
        )

        ancho = (
            bbox[2]
            - bbox[0]
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
    espacio=7
):

    posicion_y = y

    for linea in lineas:

        draw.text(
            (x, posicion_y),
            linea,
            font=font,
            fill=color
        )

        bbox = draw.textbbox(
            (x, posicion_y),
            linea,
            font=font
        )

        posicion_y = (
            bbox[3]
            + espacio
        )

    return posicion_y


def descargar_imagen(url):

    if not url:
        return None

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=25
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
            f"ERROR descargando imagen: {e}"
        )

        return None


# =========================================================
# OBTENER PRODUCTOS MAS VENDIDOS
# =========================================================

def obtener_productos_mas_vendidos():

    url = (
        "https://www.mercadolibre.com.ar/"
        "mas-vendidos"
    )

    links_encontrados = []

    try:

        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20
        )

        print(
            "DEBUG Status Más Vendidos:",
            response.status_code
        )

        if response.status_code == 200:

            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            for a in soup.find_all(
                "a",
                href=True
            ):

                href = a["href"]

                if (
                    (
                        "/p/MLA" in href
                        or "/MLA-" in href
                    )
                    and
                    "mas-vendidos"
                    not in href
                ):

                    link = href.split(
                        "?"
                    )[0]

                    if link.startswith(
                        "/"
                    ):

                        link = (
                            "https://www."
                            "mercadolibre.com.ar"
                            + link
                        )

                    if (
                        link
                        not in links_encontrados
                    ):

                        links_encontrados.append(
                            link
                        )

    except Exception as e:

        print(
            f"ERROR Más Vendidos: {e}"
        )

    if (
        len(links_encontrados)
        >= CANTIDAD_PRODUCTOS
    ):

        return random.sample(
            links_encontrados,
            CANTIDAD_PRODUCTOS
        )

    return links_encontrados[
        :CANTIDAD_PRODUCTOS
    ]


# =========================================================
# LEER PRODUCTO CON NAVEGADOR REAL
# =========================================================

def extraer_datos_producto(
    page,
    url
):

    print(
        f"Abriendo producto: {url}"
    )

    page.goto(
        url,
        wait_until="domcontentloaded",
        timeout=60000
    )

    page.wait_for_timeout(
        5000
    )

    texto_pagina = limpiar_texto(
        page.locator(
            "body"
        ).inner_text()
    )

    # -----------------------------------------------------
    # NOMBRE
    # -----------------------------------------------------

    nombre = obtener_texto_primero(
        page,
        [
            "h1.ui-pdp-title",
            "[data-testid='product-title']",
            "h1",
        ]
    )

    if not nombre:
        nombre = (
            "Producto Mercado Libre"
        )

    # -----------------------------------------------------
    # PRECIO ACTUAL
    # -----------------------------------------------------

    precio_texto = obtener_texto_primero(
        page,
        [
            ".ui-pdp-price__second-line "
            ".andes-money-amount",

            ".ui-pdp-price__second-line",

            "[data-testid='price-part']",
        ]
    )

    precio = extraer_precio(
        precio_texto
    )

    if not precio:

        match = re.search(
            r"\$\s*([\d\.]+)",
            texto_pagina
        )

        if match:
            precio = (
                "$ "
                + match.group(1)
            )

    if not precio:
        precio = (
            "Precio no disponible"
        )

    # -----------------------------------------------------
    # PRECIO ANTERIOR
    # -----------------------------------------------------

    precio_anterior_texto = (
        obtener_texto_primero(
            page,
            [
                ".ui-pdp-price__original-value",

                ".andes-money-amount--previous",

                "s .andes-money-amount",
            ]
        )
    )

    precio_anterior = (
        extraer_precio(
            precio_anterior_texto
        )
    )

    # -----------------------------------------------------
    # DESCUENTO
    # -----------------------------------------------------

    descuento = obtener_texto_primero(
        page,
        [
            ".ui-pdp-price__second-line "
            ".andes-money-amount__discount",

            ".ui-pdp-price__second-line "
            "[class*='discount']",

            "[class*='discount']",
        ]
    )

    if not descuento:

        match = re.search(
            r"(\d{1,2}%\s*OFF)",
            texto_pagina,
            re.IGNORECASE
        )

        if match:
            descuento = (
                match.group(1).upper()
            )

    # -----------------------------------------------------
    # CUOTAS
    # -----------------------------------------------------

    cuotas = obtener_texto_primero(
        page,
        [
            ".ui-pdp-payment__summary",

            "[class*='installment']",

            "[class*='payment'] "
            "[class*='summary']",
        ]
    )

    if not cuotas:

        match = re.search(
            (
                r"((?:Mismo precio en\s+)?"
                r"\d{1,2}\s+cuotas"
                r"(?:\s+de\s+\$\s*"
                r"[\d\.\,]+)?)"
            ),
            texto_pagina,
            re.IGNORECASE
        )

        if match:
            cuotas = limpiar_texto(
                match.group(1)
            )

    if not cuotas:
        cuotas = (
            "Consultar cuotas"
        )

    # -----------------------------------------------------
    # RANKING
    # -----------------------------------------------------

    ranking = ""

    match = re.search(
        (
            r"(\d+\s*[°º]\s+en\s+"
            r"[^|·\n]{3,60})"
        ),
        texto_pagina,
        re.IGNORECASE
    )

    if match:
        ranking = limpiar_texto(
            match.group(1)
        )

    # -----------------------------------------------------
    # RATING
    # -----------------------------------------------------

    rating = ""

    match = re.search(
        r"\b([1-5](?:[\.,]\d)?)\b",
        texto_pagina
    )

    if match:
        posible = (
            match.group(1)
            .replace(",", ".")
        )

        try:

            numero = float(
                posible
            )

            if (
                numero >= 1
                and numero <= 5
            ):
                rating = posible

        except Exception:
            pass

    # -----------------------------------------------------
    # VENDIDOS
    # -----------------------------------------------------

    vendidos = ""

    match = re.search(
        (
            r"(\+?\s*[\d\.\s]+"
            r"\s*mil\s+vendidos)"
        ),
        texto_pagina,
        re.IGNORECASE
    )

    if match:
        vendidos = limpiar_texto(
            match.group(1)
        )

    # -----------------------------------------------------
    # IMAGEN PRINCIPAL
    # -----------------------------------------------------

    imagen_url = obtener_atributo_primero(
        page,
        [
            "img.ui-pdp-image",

            "figure img",

            "[data-testid='gallery'] img",
        ],
        "src"
    )

    if not imagen_url:

        imagen_url = (
            obtener_atributo_primero(
                page,
                [
                    "img.ui-pdp-image",

                    "figure img",
                ],
                "data-zoom"
            )
        )

    return {
        "nombre": nombre,
        "precio": precio,
        "precio_anterior":
            precio_anterior,
        "descuento": descuento,
        "cuotas": cuotas,
        "ranking": ranking,
        "rating": rating,
        "vendidos": vendidos,
        "imagen_url": imagen_url,
        "url_original": url,
    }


# =========================================================
# CREAR IMAGEN PROFESIONAL
# =========================================================

def crear_imagen_oferta(
    datos,
    numero
):

    salida = (
        CARPETA_OFERTAS
        / f"oferta_{numero:02d}.png"
    )

    imagen_final = Image.new(
        "RGB",
        (ANCHO, ALTO),
        (248, 248, 246)
    )

    draw = ImageDraw.Draw(
        imagen_final
    )

    # -----------------------------------------------------
    # TARJETA BLANCA
    # -----------------------------------------------------

    draw.rounded_rectangle(
        (
            28,
            20,
            1052,
            1330
        ),
        radius=34,
        fill=(255, 255, 255),
        outline=(230, 230, 230),
        width=2
    )

    # -----------------------------------------------------
    # LOGO SIMPLE
    # -----------------------------------------------------

    draw.ellipse(
        (
            58,
            45,
            188,
            175
        ),
        fill=(15, 15, 15),
        outline=(245, 190, 0),
        width=8
    )

    draw.text(
        (79, 79),
        "OFERTAS",
        font=fuente(
            24,
            True
        ),
        fill=(245, 190, 0)
    )

    draw.text(
        (87, 111),
        "360",
        font=fuente(
            34,
            True
        ),
        fill="white"
    )

    # -----------------------------------------------------
    # NOMBRE CANAL
    # -----------------------------------------------------

    draw.text(
        (220, 55),
        "Cazadores de Ofertas",
        font=fuente(
            46,
            True
        ),
        fill=(15, 15, 15)
    )

    draw.text(
        (222, 113),
        "Las mejores ofertas, todos los dias",
        font=fuente(
            27,
            False
        ),
        fill=(90, 90, 90)
    )

    # -----------------------------------------------------
    # IMAGEN PRODUCTO
    # -----------------------------------------------------

    producto = descargar_imagen(
        datos["imagen_url"]
    )

    area_x0 = 70
    area_y0 = 195
    area_x1 = 1010
    area_y1 = 555

    area_ancho = (
        area_x1
        - area_x0
    )

    area_alto = (
        area_y1
        - area_y0
    )

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
            )
            // 2
        )

        y = (
            area_y0
            + (
                area_alto
                - producto.height
            )
            // 2
        )

        imagen_final.paste(
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
            (305, 350),
            "Imagen no disponible",
            font=fuente(
                32,
                True
            ),
            fill=(110, 110, 110)
        )

    # -----------------------------------------------------
    # MAS VENDIDO
    # -----------------------------------------------------

    y = 575

    draw.rounded_rectangle(
        (
            60,
            y,
            340,
            y + 60
        ),
        radius=12,
        fill=(255, 92, 20)
    )

    draw.text(
        (
            84,
            y + 10
        ),
        "MAS VENDIDO",
        font=fuente(
            34,
            True
        ),
        fill="white"
    )

    if datos["ranking"]:

        draw.text(
            (
                365,
                y + 13
            ),
            datos["ranking"][:45],
            font=fuente(
                29,
                False
            ),
            fill=(30, 30, 30)
        )

    # -----------------------------------------------------
    # TITULO
    # -----------------------------------------------------

    y += 82

    lineas_titulo = ajustar_texto(
        draw,
        datos["nombre"],
        fuente(
            48,
            True
        ),
        930
    )

    lineas_titulo = (
        lineas_titulo[:3]
    )

    y = dibujar_lineas(
        draw,
        lineas_titulo,
        65,
        y,
        fuente(
            48,
            True
        ),
        (20, 20, 20),
        5
    )

    # -----------------------------------------------------
    # RATING / VENDIDOS
    # -----------------------------------------------------

    datos_meta = []

    if datos["rating"]:

        datos_meta.append(
            "★ "
            + datos["rating"]
        )

    if datos["vendidos"]:

        datos_meta.append(
            datos["vendidos"]
        )

    if datos_meta:

        y += 5

        draw.text(
            (
                65,
                y
            ),
            "   |   ".join(
                datos_meta
            ),
            font=fuente(
                29,
                True
            ),
            fill=(25, 25, 25)
        )

        y += 47

    # -----------------------------------------------------
    # PRECIO ANTERIOR
    # -----------------------------------------------------

    if datos["precio_anterior"]:

        draw.text(
            (
                65,
                y
            ),
            datos["precio_anterior"],
            font=fuente(
                34,
                False
            ),
            fill=(105, 105, 105)
        )

        y += 48

    # -----------------------------------------------------
    # PRECIO ACTUAL
    # -----------------------------------------------------

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
        fill=(0, 145, 75)
    )

    bbox = draw.textbbox(
        (
            65,
            y
        ),
        datos["precio"],
        font=font_precio
    )

    # -----------------------------------------------------
    # DESCUENTO
    # -----------------------------------------------------

    if datos["descuento"]:

        x_descuento = min(
            bbox[2] + 25,
            790
        )

        draw.rounded_rectangle(
            (
                x_descuento,
                y + 9,
                x_descuento + 190,
                y + 67
            ),
            radius=10,
            fill=(0, 153, 82)
        )

        draw.text(
            (
                x_descuento + 14,
                y + 17
            ),
            datos["descuento"][:15],
            font=fuente(
                31,
                True
            ),
            fill="white"
        )

    y += 90

    # -----------------------------------------------------
    # CUOTAS
    # -----------------------------------------------------

    draw.text(
        (
            65,
            y
        ),
        datos["cuotas"][:80],
        font=fuente(
            34,
            True
        ),
        fill=(20, 20, 20)
    )

    y += 60

    # -----------------------------------------------------
    # INFORMACION
    # -----------------------------------------------------

    draw.text(
        (
            65,
            y
        ),
        "• Oferta publicada en Mercado Libre",
        font=fuente(
            28,
            False
        ),
        fill=(60, 60, 60)
    )

    y += 43

    draw.text(
        (
            65,
            y
        ),
        "• Precio y disponibilidad pueden variar",
        font=fuente(
            28,
            False
        ),
        fill=(60, 60, 60)
    )

    # -----------------------------------------------------
    # BOTON VER EN MERCADO LIBRE
    # -----------------------------------------------------

    boton_y = 1160

    draw.rounded_rectangle(
        (
            55,
            boton_y,
            1025,
            boton_y + 120
        ),
        radius=26,
        fill=(225, 248, 232)
    )

    draw.text(
        (
            95,
            boton_y + 22
        ),
        "Ver en Mercado Libre",
        font=fuente(
            35,
            True
        ),
        fill=(15, 60, 35)
    )

    draw.text(
        (
            95,
            boton_y + 69
        ),
        "Link afiliado en el mensaje",
        font=fuente(
            28,
            False
        ),
        fill=(25, 110, 200)
    )

    # -----------------------------------------------------
    # PIE
    # -----------------------------------------------------

    draw.text(
        (
            65,
            1295
        ),
        "Si compras desde el enlace apoyas al canal",
        font=fuente(
            23,
            False
        ),
        fill=(80, 80, 80)
    )

    imagen_final.save(
        salida,
        "PNG",
        optimize=True
    )

    print(
        f"Imagen creada: {salida}"
    )

    return salida


# =========================================================
# GUARDAR ULTIMA TANDA
# =========================================================

def guardar_ultima_tanda(
    productos
):

    Path(
        "ultima_tanda.txt"
    ).write_text(
        "\n".join(
            productos
        ),
        encoding="utf-8"
    )

    print(
        "ultima_tanda.txt "
        "generado correctamente"
    )


# =========================================================
# GUARDAR DATOS E IMAGENES
# =========================================================

def guardar_resultados(
    datos_tanda
):

    lineas_datos = []
    lineas_imagenes = []

    for numero, datos in enumerate(
        datos_tanda,
        start=1
    ):

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

        linea = (
            f"{nombre} | "
            f"{precio} | "
            f"{cuotas}"
        )

        lineas_datos.append(
            linea
        )

        url_imagen = (
            f"{RAW_BASE}/"
            f"oferta_{numero:02d}.png"
        )

        lineas_imagenes.append(
            url_imagen
        )

    Path(
        "datos_tanda.txt"
    ).write_text(
        "\n".join(
            lineas_datos
        ),
        encoding="utf-8"
    )

    Path(
        "imagenes_tanda.txt"
    ).write_text(
        "\n".join(
            lineas_imagenes
        ),
        encoding="utf-8"
    )

    print(
        "datos_tanda.txt "
        "generado correctamente"
    )

    print(
        "imagenes_tanda.txt "
        "generado correctamente"
    )


# =========================================================
# MAIN
# =========================================================

def main():

    print(
        "--- EXTRAYENDO PRODUCTOS "
        "MAS VENDIDOS ---"
    )

    productos = (
        obtener_productos_mas_vendidos()
    )

    if not productos:

        print(
            "No se pudieron "
            "extraer productos."
        )

        return

    print(
        f"Se obtuvieron "
        f"{len(productos)} productos"
    )

    guardar_ultima_tanda(
        productos
    )

    datos_tanda = []

    with sync_playwright() as p:

        browser = (
            p.chromium.launch(
                headless=True,
                args=[
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ]
            )
        )

        context = (
            browser.new_context(
                locale="es-AR",
                viewport={
                    "width": 1280,
                    "height": 1800,
                },
                user_agent=HEADERS[
                    "User-Agent"
                ]
            )
        )

        page = (
            context.new_page()
        )

        for numero, url in enumerate(
            productos,
            start=1
        ):

            print(
                f"Procesando producto "
                f"{numero}/"
                f"{len(productos)}"
            )

            try:

                datos = (
                    extraer_datos_producto(
                        page,
                        url
                    )
                )

                print(
                    f"{numero}. "
                    f"{datos['nombre']} | "
                    f"{datos['precio']} | "
                    f"{datos['cuotas']}"
                )

            except PlaywrightTimeoutError:

                print(
                    "Timeout cargando "
                    "producto"
                )

                datos = {
                    "nombre":
                        "Producto Mercado Libre",

                    "precio":
                        "Precio no disponible",

                    "precio_anterior":
                        "",

                    "descuento":
                        "",

                    "cuotas":
                        "Consultar cuotas",

                    "ranking":
                        "",

                    "rating":
                        "",

                    "vendidos":
                        "",

                    "imagen_url":
                        "",

                    "url_original":
                        url,
                }

            except Exception as e:

                print(
                    f"ERROR producto: {e}"
                )

                datos = {
                    "nombre":
                        "Producto Mercado Libre",

                    "precio":
                        "Precio no disponible",

                    "precio_anterior":
                        "",

                    "descuento":
                        "",

                    "cuotas":
                        "Consultar cuotas",

                    "ranking":
                        "",

                    "rating":
                        "",

                    "vendidos":
                        "",

                    "imagen_url":
                        "",

                    "url_original":
                        url,
                }

            crear_imagen_oferta(
                datos,
                numero
            )

            datos_tanda.append(
                datos
            )

        browser.close()

    guardar_resultados(
        datos_tanda
    )

    print(
        "Proceso terminado correctamente"
    )


if __name__ == "__main__":
    main()
