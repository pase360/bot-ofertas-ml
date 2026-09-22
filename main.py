import random
import re
import json
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}


def obtener_productos_mas_vendidos():
    url = "https://www.mercadolibre.com.ar/mas-vendidos"
    links_encontrados = []

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        print(
            f"DEBUG Status Más Vendidos: "
            f"{response.status_code}"
        )

        if response.status_code == 200:
            soup = BeautifulSoup(
                response.text,
                "html.parser"
            )

            for a in soup.find_all("a", href=True):
                href = a["href"]

                if (
                    ("/p/MLA" in href or "/MLA-" in href)
                    and "mas-vendidos" not in href
                ):
                    link_limpio = href.split("?")[0]

                    if link_limpio.startswith("/"):
                        link_limpio = (
                            "https://www.mercadolibre.com.ar"
                            + link_limpio
                        )

                    if link_limpio not in links_encontrados:
                        links_encontrados.append(link_limpio)

    except Exception as e:
        print(
            f"ERROR Más Vendidos: {e}"
        )

    if len(links_encontrados) >= 10:
        return random.sample(
            links_encontrados,
            10
        )

    return links_encontrados[:10]


def obtener_datos_producto(url):
    nombre = "Producto Mercado Libre"
    precio = "Precio no disponible"
    cuotas = "Consultar cuotas"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
            allow_redirects=True
        )

        print(
            f"   HTTP producto: "
            f"{response.status_code}"
        )

        html = response.text

        soup = BeautifulSoup(
            html,
            "html.parser"
        )

        # -------------------------
        # NOMBRE
        # -------------------------

        og_title = soup.find(
            "meta",
            property="og:title"
        )

        if (
            og_title
            and og_title.get("content")
        ):
            nombre = og_title[
                "content"
            ].strip()

        else:
            titulo = soup.find("h1")

            if titulo:
                nombre = titulo.get_text(
                    " ",
                    strip=True
                )

        # -------------------------
        # PRECIO - JSON-LD
        # -------------------------

        scripts = soup.find_all(
            "script",
            type="application/ld+json"
        )

        for script in scripts:
            try:
                datos = json.loads(
                    script.string or ""
                )

                objetos = (
                    datos
                    if isinstance(datos, list)
                    else [datos]
                )

                for objeto in objetos:
                    if not isinstance(
                        objeto,
                        dict
                    ):
                        continue

                    oferta = objeto.get(
                        "offers"
                    )

                    if isinstance(
                        oferta,
                        dict
                    ):
                        valor = oferta.get(
                            "price"
                        )

                        if valor:
                            precio = (
                                "$"
                                + formatear_precio(
                                    valor
                                )
                            )
                            break

                if precio != "Precio no disponible":
                    break

            except Exception:
                pass

        # -------------------------
        # PRECIO - META
        # -------------------------

        if precio == "Precio no disponible":

            posibles_meta = [
                soup.find(
                    "meta",
                    property="product:price:amount"
                ),
                soup.find(
                    "meta",
                    attrs={
                        "itemprop": "price"
                    }
                ),
            ]

            for meta in posibles_meta:
                if (
                    meta
                    and meta.get("content")
                ):
                    precio = (
                        "$"
                        + formatear_precio(
                            meta["content"]
                        )
                    )
                    break

        # -------------------------
        # PRECIO - HTML
        # -------------------------

        if precio == "Precio no disponible":

            elemento = soup.select_one(
                ".andes-money-amount__fraction"
            )

            if elemento:
                precio = (
                    "$"
                    + elemento.get_text(
                        strip=True
                    )
                )

        # -------------------------
        # CUOTAS
        # -------------------------

        texto = soup.get_text(
            " ",
            strip=True
        )

        patrones = [
            r"\d+\s+cuotas\s+sin\s+inter[eé]s(?:\s+de\s+\$[\d\.\,]+)?",
            r"\d+\s+cuotas\s+de\s+\$[\d\.\,]+",
        ]

        for patron in patrones:
            resultado = re.search(
                patron,
                texto,
                re.IGNORECASE
            )

            if resultado:
                cuotas = (
                    resultado
                    .group(0)
                    .strip()
                )
                break

    except Exception as e:
        print(
            f"   ERROR producto: {e}"
        )

    nombre = (
        nombre
        .replace("\n", " ")
        .replace("|", "-")
        .strip()
    )

    return nombre, precio, cuotas


def formatear_precio(valor):
    try:
        numero = float(
            str(valor)
            .replace(",", ".")
        )

        return (
            f"{numero:,.0f}"
            .replace(",", ".")
        )

    except Exception:
        return str(valor)


def guardar_ultima_tanda(productos):
    with open(
        "ultima_tanda.txt",
        "w",
        encoding="utf-8"
    ) as archivo:

        archivo.write(
            "\n".join(productos)
        )

    print(
        "✅ ultima_tanda.txt generado correctamente"
    )


def guardar_datos_tanda(productos):
    lineas = []

    for numero, url in enumerate(
        productos,
        start=1
    ):

        print(
            f"Obteniendo datos del producto "
            f"{numero}/{len(productos)}..."
        )

        nombre, precio, cuotas = (
            obtener_datos_producto(url)
        )

        linea = (
            f"{nombre} | "
            f"{precio} | "
            f"{cuotas}"
        )

        lineas.append(linea)

        print(
            f"   {numero}. {linea}"
        )

    with open(
        "datos_tanda.txt",
        "w",
        encoding="utf-8"
    ) as archivo:

        archivo.write(
            "\n".join(lineas)
        )

    print(
        "✅ datos_tanda.txt generado correctamente"
    )


if __name__ == "__main__":

    print(
        "--- EXTRAYENDO PRODUCTOS MÁS VENDIDOS ---"
    )

    productos = (
        obtener_productos_mas_vendidos()
    )

    if productos:

        print(
            f"✅ Se obtuvieron "
            f"{len(productos)} productos"
        )

        guardar_ultima_tanda(
            productos
        )

        guardar_datos_tanda(
            productos
        )

    else:

        print(
            "❌ No se pudieron extraer productos."
        )
