import json
import re
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup


SALIDA = Path("productos_demandados.json")
HISTORIAL = Path("historial_publicados.txt")

URL_MAS_VENDIDOS = "https://www.mercadolibre.com.ar/mas-vendidos"
URL_OFERTAS = "https://www.mercadolibre.com.ar/ofertas"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}


def limpiar(texto):
    return re.sub(r"\s+", " ", str(texto or "")).strip()


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
        match = re.search(patron, texto, flags=re.I)
        if match:
            return normalizar_id(match.group(1))

    return ""


def leer_historial():
    if not HISTORIAL.exists():
        return set()

    contenido = HISTORIAL.read_text(
        encoding="utf-8",
        errors="ignore",
    )

    ids = re.findall(
        r"MLA-?\d+",
        contenido,
        flags=re.I,
    )

    return {normalizar_id(x) for x in ids}


def descargar(url):
    respuesta = requests.get(
        url,
        headers=HEADERS,
        timeout=30,
    )

    print("HTTP", respuesta.status_code, "|", url)
    respuesta.raise_for_status()

    return respuesta.text


def extraer_precio(texto):
    texto = limpiar(texto)

    match = re.search(
        r"\$\s*([\d\.\,]+)",
        texto,
    )

    if not match:
        return None

    valor = match.group(1)

    # Mercado Libre Argentina normalmente usa punto
    # como separador de miles.
    valor = valor.replace(".", "")
    valor = valor.replace(",", ".")

    try:
        return float(valor)
    except ValueError:
        return None


def extraer_descuento(texto):
    match = re.search(
        r"(\d{1,2})\s*%\s*(?:OFF|DESCUENTO)",
        texto,
        flags=re.I,
    )

    if match:
        return int(match.group(1))

    return 0


def tiene_envio_gratis(texto):
    return bool(
        re.search(
            r"env[ií]o gratis",
            texto,
            flags=re.I,
        )
    )


def extraer_ranking(texto):
    """
    Detecta textos como:
    1° MÁS VENDIDO
    2º MÁS VENDIDO
    """
    match = re.search(
        r"\b(\d{1,3})\s*[°º]\s*M[AÁ]S VENDIDO",
        texto,
        flags=re.I,
    )

    if match:
        return int(match.group(1))

    return None


def limpiar_titulo(texto):
    titulo = limpiar(texto)

    # Quitar ranking inicial.
    titulo = re.sub(
        r"^\s*\d{1,3}\s*[°º]\s*M[AÁ]S VENDIDO\s*",
        "",
        titulo,
        flags=re.I,
    )

    # Quitar precios iniciales.
    titulo = re.sub(
        r"^(?:\$\s*[\d\.\,]+\s*)+",
        "",
        titulo,
    )

    # Quitar descuento inicial.
    titulo = re.sub(
        r"^\d{1,2}\s*%\s*(?:OFF|DESCUENTO)\s*",
        "",
        titulo,
        flags=re.I,
    )

    # Quitar envío gratis inicial.
    titulo = re.sub(
        r"^env[ií]o gratis\s*",
        "",
        titulo,
        flags=re.I,
    )

    return limpiar(titulo)


def obtener_texto_producto(enlace):
    """
    Intenta tomar el texto del bloque completo del producto,
    no solamente el texto del enlace.
    """

    candidatos = [
        enlace,
        enlace.parent,
        enlace.parent.parent if enlace.parent else None,
    ]

    mejor = ""

    for candidato in candidatos:
        if not candidato:
            continue

        texto = limpiar(
            candidato.get_text(" ", strip=True)
        )

        if len(texto) > len(mejor):
            mejor = texto

    return mejor


def extraer_productos(html, fuente):
    soup = BeautifulSoup(html, "html.parser")

    encontrados = {}
    posicion = 0

    for enlace in soup.find_all("a", href=True):
        href = enlace.get("href", "")

        item_id = extraer_id(href)

        if not item_id:
            continue

        if item_id in encontrados:
            continue

        texto_bloque = obtener_texto_producto(enlace)

        texto_enlace = limpiar(
            enlace.get_text(" ", strip=True)
        )

        titulo = limpiar_titulo(texto_enlace)

        if len(titulo) < 4:
            imagen = enlace.find("img")

            if imagen:
                titulo = limpiar(
                    imagen.get("alt", "")
                )

        if len(titulo) < 4:
            titulo = limpiar_titulo(texto_bloque)

        if len(titulo) < 4:
            continue

        posicion += 1

        precio = extraer_precio(texto_bloque)
        descuento = extraer_descuento(texto_bloque)
        envio_gratis = tiene_envio_gratis(texto_bloque)
        ranking = extraer_ranking(texto_bloque)

        encontrados[item_id] = {
            "item_id": item_id,
            "titulo": titulo,
            "url": href,
            "fuente": fuente,
            "posicion_fuente": posicion,
            "ranking_mas_vendido": ranking,
            "precio": precio,
            "descuento_porcentaje": descuento,
            "envio_gratis": envio_gratis,
        }

    return list(encontrados.values())


def puntuar(producto):
    puntos = 0

    fuente = producto.get("fuente", "")
    posicion = producto.get("posicion_fuente", 999)
    ranking = producto.get("ranking_mas_vendido")
    descuento = producto.get("descuento_porcentaje", 0)
    envio_gratis = producto.get("envio_gratis", False)

    # Señal de demanda.
    if fuente == "Mas vendidos":
        puntos += 100

    elif fuente == "Ofertas":
        puntos += 60

    # Posición dentro de la fuente.
    if posicion <= 5:
        puntos += 40
    elif posicion <= 10:
        puntos += 30
    elif posicion <= 20:
        puntos += 20
    elif posicion <= 40:
        puntos += 10

    # Ranking explícito de Más Vendidos.
    if ranking is not None:
        if ranking <= 5:
            puntos += 50
        elif ranking <= 10:
            puntos += 40
        elif ranking <= 20:
            puntos += 30
        elif ranking <= 50:
            puntos += 20

    # Atractivo comercial.
    if descuento >= 30:
        puntos += 25
    elif descuento >= 20:
        puntos += 20
    elif descuento >= 10:
        puntos += 10

    if envio_gratis:
        puntos += 10

    producto["puntaje_demanda"] = puntos

    return producto


def detectar():
    historial = leer_historial()

    print(
        "Productos ya publicados:",
        len(historial),
    )

    candidatos = {}

    fuentes = [
        ("Mas vendidos", URL_MAS_VENDIDOS),
        ("Ofertas", URL_OFERTAS),
    ]

    for nombre_fuente, url in fuentes:
        try:
            html = descargar(url)

            productos = extraer_productos(
                html,
                nombre_fuente,
            )

            print(
                f"Productos detectados en {nombre_fuente}:",
                len(productos),
            )

            for producto in productos:
                item_id = producto["item_id"]

                if item_id in historial:
                    continue

                # Si aparece en ambas fuentes,
                # Más Vendidos tiene prioridad.
                if item_id not in candidatos:
                    candidatos[item_id] = producto

                elif (
                    nombre_fuente == "Mas vendidos"
                    and candidatos[item_id]["fuente"] != "Mas vendidos"
                ):
                    candidatos[item_id] = producto

        except Exception as error:
            print(
                f"ERROR {nombre_fuente}:",
                error,
            )

    productos = [
        puntuar(producto)
        for producto in candidatos.values()
    ]

    productos.sort(
        key=lambda x: (
            x["puntaje_demanda"],
            -x["posicion_fuente"],
        ),
        reverse=True,
    )

    return productos[:50]


def guardar(productos):
    salida = {
        "generado": datetime.now(
            timezone.utc
        ).isoformat(),

        "tipo": "candidatos_demanda_producto",

        # IMPORTANTE:
        # todavía no decimos que aprende.
        "aprendizaje_activo": False,

        "productos": productos,
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
    print("=== PRODUCTOS CON DEMANDA ===")
    print("Total candidatos:", len(productos))
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
            f"| ranking={producto['ranking_mas_vendido']} "
            f"| precio={producto['precio']} "
            f"| descuento={producto['descuento_porcentaje']}% "
            f"| envio_gratis={producto['envio_gratis']} "
            f"| puntos={producto['puntaje_demanda']}"
        )

    print()
    print("Archivo generado:", SALIDA)


def main():
    print("=== DETECTOR DE PRODUCTOS V2 ===")

    productos = detectar()

    guardar(productos)

    print("=== DETECTOR FINALIZADO ===")


if __name__ == "__main__":
    main()
