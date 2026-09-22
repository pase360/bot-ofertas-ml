import random
import re
import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
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
            f"Excepción extrayendo productos: {e}"
        )

    if len(links_encontrados) >= 10:
        return random.sample(links_encontrados, 10)

    return links_encontrados[:10]


def obtener_datos_producto(url):
    nombre = "Producto Mercado Libre"
    precio = "Precio no disponible"
    cuotas = "Consultar cuotas"

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=15
        )

        if response.status_code != 200:
            return nombre, precio, cuotas

        soup = BeautifulSoup(
            response.text,
            "html.parser"
        )

        # NOMBRE
        h1 = soup.find("h1")

        if h1:
            nombre = h1.get_text(
                " ",
                strip=True
            )

        # PRECIO
        meta_precio = soup.find(
            "meta",
            attrs={"itemprop": "price"}
        )

        if meta_precio and meta_precio.get("content"):
            valor = meta_precio["content"]

            try:
                numero = float(valor)

                precio = (
                    "$"
                    + f"{numero:,.0f}"
                    .replace(",", ".")
                )
            except Exception:
                precio = "$" + valor

        else:
            precio_elemento = soup.select_one(
                ".andes-money-amount__fraction"
            )

            if precio_elemento:
                precio = (
                    "$"
                    + precio_elemento.get_text(
                        strip=True
                    )
                )

        # CUOTAS
        texto_pagina = soup.get_text(
            " ",
            strip=True
        )

        patrones = [
            r"(\d+)\s+cuotas\s+sin\s+inter[eé]s",
            r"(\d+)\s+cuotas\s+de\s+\$[\d\.\,]+",
        ]

        for patron in patrones:
            coincidencia = re.search(
                patron,
                texto_pagina,
                re.IGNORECASE
            )

            if coincidencia:
                cuotas = coincidencia.group(0)
                break

    except Exception as e:
        print(
            f"Error obteniendo datos de {url}: {e}"
        )

    return nombre, precio, cuotas


def guardar_ultima_tanda(productos):
    contenido = "\n".join(productos)

    with open(
        "ultima_tanda.txt",
        "w",
        encoding="utf-8"
    ) as archivo:
        archivo.write(contenido)

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
            f"Obteniendo datos del producto {numero}/"
            f"{len(productos)}..."
        )

        nombre, precio, cuotas = (
            obtener_datos_producto(url)
        )

        # Evitamos saltos de línea dentro de los datos
        nombre = nombre.replace("\n", " ").strip()
        precio = precio.replace("\n", " ").strip()
        cuotas = cuotas.replace("\n", " ").strip()

        linea = (
            f"{nombre} | "
            f"{precio} | "
            f"{cuotas}"
        )

        lineas.append(linea)

        print(
            f"  {numero}. {linea}"
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

    productos = obtener_productos_mas_vendidos()

    if productos:
        print(
            f"✅ Se obtuvieron {len(productos)} productos"
        )

        guardar_ultima_tanda(productos)
        guardar_datos_tanda(productos)

    else:
        print(
            "❌ No se pudieron extraer productos."
        )
