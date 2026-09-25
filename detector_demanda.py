import json
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote_plus

import requests
from bs4 import BeautifulSoup


SALIDA = Path("demandas_detectadas.json")

URL_TRENDS = "https://trends.google.com/trending/rss?geo=AR"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}


# =========================================================
# PALABRAS QUE NORMALMENTE NO REPRESENTAN PRODUCTOS
# =========================================================

PALABRAS_EXCLUIDAS = {
    "futbol", "fútbol", "partido", "resultado", "gol",
    "seleccion", "selección", "mundial", "copa",
    "gran premio", "formula 1", "fórmula 1",
    "elecciones", "elección", "presidente", "gobierno",
    "diputados", "senadores",
    "clima", "tiempo", "temperatura",
    "dolar", "dólar", "cotizacion", "cotización",
    "horoscopo", "horóscopo",
    "estafa", "accidente", "muerte", "fallecio", "falleció",
    "terremoto", "guerra",
}


# =========================================================
# UTILIDADES
# =========================================================

def limpiar(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def normalizar(texto):
    return limpiar(texto).lower()


def esta_excluido(texto):
    texto = normalizar(texto)

    for palabra in PALABRAS_EXCLUIDAS:
        if palabra in texto:
            return True

    return False


# =========================================================
# GOOGLE TRENDS ARGENTINA
# =========================================================

def obtener_tendencias():
    response = requests.get(
        URL_TRENDS,
        headers=HEADERS,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.content, "xml")

    tendencias = []

    for item in soup.find_all("item"):
        titulo = limpiar(
            item.title.get_text()
            if item.title
            else ""
        )

        if not titulo:
            continue

        trafico = ""

        traffic = item.find("ht:approx_traffic")
        if traffic:
            trafico = limpiar(traffic.get_text())

        tendencias.append({
            "busqueda": titulo,
            "trafico_aproximado": trafico,
            "fuente": "Google Trends Argentina",
        })

    return tendencias


# =========================================================
# COMPROBAR SI MERCADO LIBRE ENCUENTRA PRODUCTOS
# =========================================================

def buscar_en_mercado_libre(termino):
    """
    Una tendencia solamente pasa el filtro si Mercado Libre
    devuelve resultados que parecen publicaciones de productos.
    """

    termino = limpiar(termino)

    if not termino:
        return False, 0

    if esta_excluido(termino):
        return False, 0

    url = (
        "https://listado.mercadolibre.com.ar/"
        + quote_plus(termino).replace("+", "-")
    )

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=30,
        )

        if response.status_code != 200:
            return False, 0

        soup = BeautifulSoup(response.text, "html.parser")

        productos = set()

        for enlace in soup.find_all("a", href=True):
            href = enlace.get("href", "")

            if "/MLA-" in href or "/p/MLA" in href:
                productos.add(href)

        cantidad = len(productos)

        return cantidad > 0, cantidad

    except Exception as error:
        print(
            "AVISO Mercado Libre:",
            termino,
            "|",
            error,
        )
        return False, 0


# =========================================================
# FILTRAR DEMANDA COMPRABLE
# =========================================================

def detectar_demanda_comprable():
    tendencias = obtener_tendencias()

    print(
        "Tendencias generales recibidas:",
        len(tendencias),
    )

    comprables = []

    for tendencia in tendencias:
        termino = tendencia["busqueda"]

        if esta_excluido(termino):
            print(
                "DESCARTADO por tema:",
                termino,
            )
            continue

        existe, cantidad = buscar_en_mercado_libre(
            termino
        )

        if not existe:
            print(
                "DESCARTADO sin producto ML:",
                termino,
            )
            continue

        oportunidad = {
            "busqueda": termino,
            "trafico_aproximado":
                tendencia["trafico_aproximado"],
            "resultados_ml": cantidad,
            "fuente":
                tendencia["fuente"],
            "detectado":
                datetime.now(
                    timezone.utc
                ).isoformat(),
            "estado": "pendiente",
        }

        comprables.append(oportunidad)

        print(
            "POSIBLE DEMANDA:",
            termino,
            "| tráfico=",
            tendencia["trafico_aproximado"],
            "| productos ML=",
            cantidad,
        )

    return comprables


# =========================================================
# GUARDAR
# =========================================================

def guardar(demandas):
    SALIDA.write_text(
        json.dumps(
            demandas,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "Demandas comprables detectadas:",
        len(demandas),
    )

    for numero, demanda in enumerate(
        demandas,
        start=1,
    ):
        print(
            f"{numero}. "
            f"{demanda['busqueda']} "
            f"| tráfico="
            f"{demanda['trafico_aproximado']} "
            f"| resultados ML="
            f"{demanda['resultados_ml']}"
        )

    print(
        "Archivo generado:",
        SALIDA,
    )


# =========================================================
# MAIN
# =========================================================

def main():
    print(
        "=== DETECTOR DE DEMANDA COMPRABLE ==="
    )

    print(
        "Fuente inicial: Google Trends Argentina"
    )

    demandas = detectar_demanda_comprable()

    guardar(demandas)

    print(
        "=== DETECTOR FINALIZADO ==="
    )


if __name__ == "__main__":
    main()
