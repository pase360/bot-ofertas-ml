import random
import re
import requests

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
        response = requests.get(url, headers=HEADERS, timeout=15)

        print(f"DEBUG Status Más Vendidos: {response.status_code}")

        if response.status_code == 200:
            from bs4 import BeautifulSoup

            soup = BeautifulSoup(response.text, "html.parser")

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
        print(f"ERROR Más Vendidos: {e}")

    if len(links_encontrados) >= 10:
        return random.sample(links_encontrados, 10)

    return links_encontrados[:10]


def extraer_id(url):
    # Caso catálogo:
    # https://www.mercadolibre.com.ar/.../p/MLA123456
    match_catalogo = re.search(
        r"/p/(MLA\d+)",
        url,
        re.IGNORECASE
    )

    if match_catalogo:
        return "catalogo", match_catalogo.group(1).upper()

    # Caso publicación:
    # https://articulo.mercadolibre.com.ar/MLA-123456...
    match_item = re.search(
        r"/MLA-(\d+)",
        url,
        re.IGNORECASE
    )

    if match_item:
        return "item", "MLA" + match_item.group(1)

    return None, None


def formatear_precio(valor):
    try:
        numero = float(valor)

        return "$" + f"{numero:,.0f}".replace(",", ".")

    except Exception:
        return str(valor)


def consultar_item(item_id):
    url_api = f"https://api.mercadolibre.com/items/{item_id}"

    try:
        r = requests.get(url_api, timeout=15)

        print(f"   API item {item_id}: HTTP {r.status_code}")

        if r.status_code == 200:
            datos = r.json()

            nombre = datos.get("title") or "Nombre no disponible"
            precio = datos.get("price")

            if precio is not None:
                precio = formatear_precio(precio)
            else:
                precio = "Precio no disponible"

            return nombre, precio

    except Exception as e:
        print(f"   ERROR API item: {e}")

    return "Nombre no disponible", "Precio no disponible"


def consultar_catalogo(product_id):
    url_api = (
        "https://api.mercadolibre.com/products/"
        + product_id
    )

    try:
        r = requests.get(url_api, timeout=15)

        print(
            f"   API catálogo {product_id}: "
            f"HTTP {r.status_code}"
        )

        if r.status_code == 200:
            datos = r.json()

            nombre = (
                datos.get("name")
                or datos.get("title")
                or "Nombre no disponible"
            )

            precio = "Precio no disponible"

            buy_box = datos.get("buy_box_winner")

            if isinstance(buy_box, dict):
                precio_valor = buy_box.get("price")

                if precio_valor is not None:
                    precio = formatear_precio(precio_valor)

                item_id = buy_box.get("item_id")

                if item_id:
                    nombre_item, precio_item = consultar_item(item_id)

                    if nombre == "Nombre no disponible":
                        nombre = nombre_item

                    if precio == "Precio no disponible":
                        precio = precio_item

            return nombre, precio

    except Exception as e:
        print(f"   ERROR API catálogo: {e}")

    return "Nombre no disponible", "Precio no disponible"


def obtener_datos_producto(url):
    tipo, identificador = extraer_id(url)

    print(f"   Tipo: {tipo} | ID: {identificador}")

    if tipo == "item":
        return consultar_item(identificador)

    if tipo == "catalogo":
        return consultar_catalogo(identificador)

    return "Nombre no disponible", "Precio no disponible"


def guardar_ultima_tanda(productos):
    with open(
        "ultima_tanda.txt",
        "w",
        encoding="utf-8"
    ) as archivo:
        archivo.write("\n".join(productos))

    print("✅ ultima_tanda.txt generado correctamente")


def guardar_datos_tanda(productos):
    lineas = []

    for numero, url in enumerate(productos, start=1):

        print(
            f"Obteniendo datos del producto "
            f"{numero}/{len(productos)}..."
        )

        nombre, precio = obtener_datos_producto(url)

        nombre = (
            nombre
            .replace("\n", " ")
            .replace("|", "-")
            .strip()
        )

        linea = f"{nombre} | {precio}"

        lineas.append(linea)

        print(f"   {numero}. {linea}")

    with open(
        "datos_tanda.txt",
        "w",
        encoding="utf-8"
    ) as archivo:
        archivo.write("\n".join(lineas))

    print("✅ datos_tanda.txt generado correctamente")


if __name__ == "__main__":

    print("--- EXTRAYENDO PRODUCTOS MÁS VENDIDOS ---")

    productos = obtener_productos_mas_vendidos()

    if productos:

        print(f"✅ Se obtuvieron {len(productos)} productos")

        guardar_ultima_tanda(productos)
        guardar_datos_tanda(productos)

    else:
        print("❌ No se pudieron extraer productos.")
