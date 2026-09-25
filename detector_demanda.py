import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


SALIDA = Path("demandas_detectadas.json")

# Google Trends Argentina - tendencias actuales.
URL_TRENDS = "https://trends.google.com/trending/rss?geo=AR"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}


# Palabras que normalmente indican temas que NO son productos comprables.
PALABRAS_EXCLUIDAS = {
    "futbol", "fútbol", "partido", "resultado", "gol",
    "seleccion", "selección", "elecciones", "elección",
    "presidente", "diputados", "senadores", "gobierno",
    "clima", "tiempo", "temperatura",
    "dolar", "dólar", "cotizacion", "cotización",
    "horoscopo", "horóscopo",
}


def limpiar(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


def parece_producto(texto):
    """
    Filtro inicial conservador.
    No decide definitivamente que algo sea un producto:
    solamente elimina tendencias claramente ajenas a compras.
    """
    texto_bajo = limpiar(texto).lower()

    if len(texto_bajo) < 3:
        return False

    for palabra in PALABRAS_EXCLUIDAS:
        if palabra in texto_bajo:
            return False

    return True


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
        titulo = limpiar(item.title.get_text() if item.title else "")

        if not titulo:
            continue

        trafico = ""

        traffic = item.find("ht:approx_traffic")
        if traffic:
            trafico = limpiar(traffic.get_text())

        if parece_producto(titulo):
            tendencias.append(
                {
                    "busqueda": titulo,
                    "trafico_aproximado": trafico,
                    "fuente": "Google Trends Argentina",
                    "detectado": datetime.now(timezone.utc).isoformat(),
                    "estado": "pendiente",
                }
            )

    return tendencias


def guardar(tendencias):
    SALIDA.write_text(
        json.dumps(
            tendencias,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    print("Demandas detectadas:", len(tendencias))

    for numero, tendencia in enumerate(tendencias, start=1):
        print(
            f"{numero}. {tendencia['busqueda']} "
            f"| tráfico={tendencia['trafico_aproximado']}"
        )

    print("Archivo generado:", SALIDA)


def main():
    print("=== DETECTOR DE DEMANDA ===")
    print("Fuente: Google Trends Argentina")

    try:
        tendencias = obtener_tendencias()
    except Exception as error:
        print("ERROR obteniendo tendencias:", error)
        raise

    guardar(tendencias)

    print("=== DETECTOR FINALIZADO ===")


if __name__ == "__main__":
    main()
