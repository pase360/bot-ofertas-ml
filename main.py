import random
import re
import json
import html
import requests
from bs4 import BeautifulSoup

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Linux; Android 14; Mobile) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/153.0.0.0 Mobile Safari/537.36"
    ),
    "Accept-Language": "es-AR,es;q=0.9",
}


def obtener_productos_mas_vendidos():
    url = "https://www.mercadolibre.com.ar/mas-vendidos"
    links_encontrados = []

    try:
        response = requests.get(url, headers=HEADERS, timeout=20)
        print(f"DEBUG Status Más Vendidos: {response.status_code}")

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, "html.parser")

            for a in soup.find_all("a", href=True):
                href = a["href"]

                if (
                    ("/p/MLA" in href or "/MLA-" in href)
                    and "mas-vendidos" not in href
                ):
                    link = href.split("?")[0]

                    if link.startswith("/"):
                        link = "https://www.mercadolibre.com.ar" + link

                    if link not in links_encontrados:
                        links_encontrados.append(link)

    except Exception as e:
        print(f"ERROR Más Vendidos: {e}")

    if len(links_encontrados) >= 10:
        return random.sample(links_encontrados, 10)

    return links_encontrados[:10]


def formatear_precio(valor):
    try:
        numero = float(valor)
        return "$" + f"{numero:,.0f}".replace(",", ".")
    except Exception:
        return "Precio no disponible"


def buscar_json(objeto):
    """
    Recorre estructuras JSON embebidas en la página buscando
    título, precio y datos de cuotas.
    """
    resultados = []

    def recorrer(obj):
        if isinstance(obj, dict):
            titulo = (
                obj.get("title")
                or obj.get("name")
            )

            precio = (
                obj.get("price")
                or obj.get("amount")
            )

            cuotas = None

            installments = obj.get("installments")

            if isinstance(installments, dict):
                cantidad = (
                    installments.get("quantity")
                    or installments.get("installments")
                )
                importe = (
                    installments.get("amount")
                    or installments.get("installment_amount")
                )

                if cantidad:
                    if importe:
                        cuotas = (
                            f"{cantidad} cuotas de "
                            f"{formatear_precio(importe)}"
                        )
                    else:
                        cuotas = f"{cantidad} cuotas"

            if titulo and precio:
                resultados.append(
                    (str(titulo), precio, cuotas)
                )

            for valor in obj.values():
                recorrer(valor)

        elif isinstance(obj, list):
            for valor in obj:
                recorrer(valor)

    recorrer(objeto)

    return resultados


def obtener_datos_producto(url):
    print(f"   Abriendo producto: {url}")

    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=20,
            allow_redirects=True
        )

        print(f"   HTTP producto: {response.status_code}")

        if response.status_code != 200:
            return (
                "Nombre no disponible",
                "Precio no disponible",
                "Consultar cuotas"
            )

        texto = response.text
        soup = BeautifulSoup(texto, "html.parser")

        # 1. Intentar JSON-LD
        for script in soup.find_all(
            "script",
            attrs={"type": "application/ld+json"}
        ):
            try:
                contenido = script.string or script.get_text()

                if not contenido:
                    continue

                datos = json.loads(contenido)

                candidatos = buscar_json(datos)

                if candidatos:
                    nombre, precio, cuotas = candidatos[0]

                    return (
                        html.unescape(nombre).strip(),
                        formatear_precio(precio),
                        cuotas or "Consultar cuotas"
                    )

            except Exception:
                pass

        # 2. Buscar metadatos OpenGraph
        nombre = None
        precio = None

        meta_titulo = soup.find(
            "meta",
            property="og:title"
        )

        if meta_titulo:
            nombre = meta_titulo.get("content")

        selectores_precio = [
            ("meta", {"property": "product:price:amount"}),
            ("meta", {"itemprop": "price"}),
        ]

        for etiqueta, atributos in selectores_precio:
            encontrado = soup.find(etiqueta, attrs=atributos)

            if encontrado:
                precio = (
                    encontrado.get("content")
                    or encontrado.get("value")
                )

                if precio:
                    break

        # 3. Buscar precio dentro del HTML
        if not precio:
            patrones = [
                r'"price"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
                r'"amount"\s*:\s*([0-9]+(?:\.[0-9]+)?)',
            ]

            for patron in patrones:
                match = re.search(patron, texto)

                if match:
                    precio = match.group(1)
                    break

        # 4. Buscar cuotas en el texto visible
        cuotas = "Consultar cuotas"

        texto_visible = soup.get_text(" ", strip=True)

        match_cuotas = re.search(
            r'(\d{1,2})\s+cuotas(?:\s+de\s+\$?\s*([\d\.\,]+))?',
            texto_visible,
            re.IGNORECASE
        )

        if match_cuotas:
            cantidad = match_cuotas.group(1)
            importe = match_cuotas.group(2)

            if importe:
                cuotas = f"{cantidad} cuotas de ${importe}"
            else:
                cuotas = f"{cantidad} cuotas"

        if nombre and precio:
            return (
                html.unescape(nombre).strip(),
                formatear_precio(precio),
                cuotas
            )

    except Exception as e:
        print(f"   ERROR producto: {e}")

    return (
        "Nombre no disponible",
        "Precio no disponible",
        "Consultar cuotas"
    )


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

        nombre, precio, cuotas = obtener_datos_producto(url)

        nombre = (
            nombre
            .replace("\n", " ")
            .replace("|", "-")
            .strip()
        )

        linea = f"{nombre} | {precio} | {cuotas}"
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
