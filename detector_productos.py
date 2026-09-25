import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


SALIDA = Path("productos_demandados.json")
HISTORIAL = Path("historial_publicados.txt")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}


# =========================================================
# FUENTES PÚBLICAS
# =========================================================

URL_MAS_VENDIDOS = "https://www.mercadolibre.com.ar/mas-vendidos"
URL_OFERTAS = "https://www.mercadolibre.com.ar/ofertas"


# =========================================================
# UTILIDADES
# =========================================================

def limpiar(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def leer_historial():
    if not HISTORIAL.exists():
        return set()

    contenido = HISTORIAL.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    ids = set(
        re.findall(
            r"MLA-?\d+",
            contenido,
            flags=re.I,
        )
    )

    return {
        x.upper().replace("-", "")
        for x in ids
    }


def normalizar_id(item_id):
    return str(item_id or "").upper().replace("-", "")


def extraer_id(texto):
    texto = str(texto or "")

    patrones = [
        r"\b(MLA\d{6,})\b",
        r"\b(MLA-\d{6,})\b",
        r"/p/(MLA\d+)",
        r"/(MLA-\d+)",
    ]

    for patron in patrones:
        match = re.search(
            patron,
            texto,
            flags=re.I,
        )

        if match:
            return normalizar_id(match.group(1))

    return ""


# =========================================================
# LEER UNA PÁGINA DE MERCADO LIBRE
# =========================================================

def descargar(url):
    respuesta = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    print(
        "HTTP",
        respuesta.status_code,
        "|",
        url,
    )

    respuesta.raise_for_status()

    return respuesta.text


# =========================================================
# EXTRAER PRODUCTOS DE HTML
# =========================================================

def extraer_productos(html, fuente):
    soup = BeautifulSoup(html, "html.parser")

    encontrados = {}
    orden = 0

    for enlace in soup.find_all("a", href=True):
        href = enlace.get("href", "")

        item_id = extraer_id(href)

        if not item_id:
            continue

        titulo = limpiar(
            enlace.get_text(" ", strip=True)
        )

        if len(titulo) < 4:
            imagen = enlace.find("img")

            if imagen:
                titulo = limpiar(
                    imagen.get("alt", "")
                )

        if len(titulo) < 4:
            continue

        if item_id not in encontrados:
            orden += 1

            encontrados[item_id] = {
                "item_id": item_id,
                "titulo": titulo,
                "url": href,
                "fuente": fuente,
                "posicion_fuente": orden,
            }

    return list(encontrados.values())


# =========================================================
# BÚSQUEDA ADICIONAL
# =========================================================

def buscar_mercado_libre(termino):
    slug = quote_plus(termino).replace("+", "-")

    url = (
        "https://listado.mercadolibre.com.ar/"
        + slug
    )

    try:
        html = descargar(url)

        return extraer_productos(
            html,
            "Busqueda Mercado Libre",
        )

    except Exception as error:
        print(
            "AVISO búsqueda:",
            termino,
            "|",
            error,
        )

        return []


# =========================================================
# PUNTUACIÓN INICIAL
# =========================================================

def puntuar(producto):
    """
    Primera puntuación.

    Todavía NO utiliza clics ni ventas del canal.
    Esa información se incorporará cuando conectemos
    las métricas reales del programa de afiliados.
    """

    puntos = 0

    fuente = producto.get("fuente", "")
    posicion = producto.get(
        "posicion_fuente",
        999,
    )

    if fuente == "Mas vendidos":
        puntos += 100

    elif fuente == "Ofertas":
        puntos += 60

    elif fuente == "Busqueda Mercado Libre":
        puntos += 40

    # Premiar posiciones altas dentro de la fuente.
    if posicion <= 5:
        puntos += 40

    elif posicion <= 10:
        puntos += 30

    elif posicion <= 20:
        puntos += 20

    elif posicion <= 40:
        puntos += 10

    producto["puntaje_demanda"] = puntos

    return producto


# =========================================================
# DETECTOR PRINCIPAL
# =========================================================

def detectar():
    historial = leer_historial()

    print(
        "Productos ya publicados:",
        len(historial),
    )

    candidatos = {}

    # -----------------------------------------------------
    # MÁS VENDIDOS
    # -----------------------------------------------------

    try:
        html = descargar(URL_MAS_VENDIDOS)

        productos = extraer_productos(
            html,
            "Mas vendidos",
        )

        print(
            "Productos detectados en Más Vendidos:",
            len(productos),
        )

        for producto in productos:
            item_id = producto["item_id"]

            if item_id in historial:
                continue

            candidatos[item_id] = producto

    except Exception as error:
        print(
            "ERROR Más Vendidos:",
            error,
        )

    # -----------------------------------------------------
    # OFERTAS
    # -----------------------------------------------------

    try:
        html = descargar(URL_OFERTAS)

        productos = extraer_productos(
            html,
            "Ofertas",
        )

        print(
            "Productos detectados en Ofertas:",
            len(productos),
        )

        for producto in productos:
            item_id = producto["item_id"]

            if item_id in historial:
                continue

            if item_id not in candidatos:
                candidatos[item_id] = producto

    except Exception as error:
        print(
            "ERROR Ofertas:",
            error,
        )

    # -----------------------------------------------------
    # PUNTUAR
    # -----------------------------------------------------

    resultado = []

    for producto in candidatos.values():
        resultado.append(
            puntuar(producto)
        )

    resultado.sort(
        key=lambda x: (
            x["puntaje_demanda"],
            -x["posicion_fuente"],
        ),
        reverse=True,
    )

    # Guardamos hasta 50 candidatos.
    return resultado[:50]


# =========================================================
# GUARDAR
# =========================================================

def guardar(productos):
    salida = {
        "generado":
            datetime.now(
                timezone.utc
            ).isoformat(),

        "tipo":
            "candidatos_demanda_producto",

        "aprendizaje_activo":
            False,

        "nota":
            (
                "La puntuacion actual usa señales "
                "de Mercado Libre. Los clics, ventas "
                "y comisiones se incorporaran en la "
                "etapa de aprendizaje."
            ),

        "productos":
            productos,
    }

    SALIDA.write_text(
        json.dumps(
            salida,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "=== PRODUCTOS CON DEMANDA ==="
    )

    print(
        "Total candidatos:",
        len(productos),
    )

    print()

    for numero, producto in enumerate(
        productos[:20],
        start=1,
    ):
        print(
            f"{numero}. "
            f"{producto['titulo']} "
            f"| {producto['item_id']} "
            f"| fuente={producto['fuente']} "
            f"| puntos="
            f"{producto['puntaje_demanda']}"
        )

    print()

    print(
        "Archivo generado:",
        SALIDA,
    )


# =========================================================
# MAIN
# =========================================================

def main():
    print(
        "=== DETECTOR DE PRODUCTOS ==="
    )

    productos = detectar()

    guardar(productos)

    print(
        "=== DETECTOR FINALIZADO ==="
    )


if __name__ == "__main__":
    main()
