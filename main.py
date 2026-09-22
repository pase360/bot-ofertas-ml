import random
import requests
from bs4 import BeautifulSoup


def obtener_productos_mas_vendidos():
    url = "https://www.mercadolibre.com.ar/mas-vendidos"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/120.0.0.0 Safari/537.36"
        )
    }

    links_encontrados = []

    try:
        response = requests.get(
            url,
            headers=headers,
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
                        links_encontrados.append(
                            link_limpio
                        )

        else:
            print(
                "DEBUG Error al acceder a la página: "
                f"{response.status_code}"
            )

    except Exception as e:
        print(
            f"Excepción extrayendo productos: {e}"
        )

    if len(links_encontrados) >= 10:
        return random.sample(
            links_encontrados,
            10
        )

    return links_encontrados[:10]


def guardar_ultima_tanda(productos):
    if not productos:
        contenido = (
            "No se pudieron extraer productos "
            "en esta ejecución."
        )
    else:
        contenido = "\n".join(productos)

    try:
        with open(
            "ultima_tanda.txt",
            "w",
            encoding="utf-8"
        ) as archivo:
            archivo.write(contenido)

        print(
            "✅ ultima_tanda.txt generado correctamente"
        )

    except Exception as e:
        print(
            f"❌ Error guardando ultima_tanda.txt: {e}"
        )


if __name__ == "__main__":

    print(
        "--- EXTRAYENDO PRODUCTOS MÁS VENDIDOS ---"
    )

    productos = obtener_productos_mas_vendidos()

    if productos:
        print(
            f"✅ Se obtuvieron {len(productos)} productos:"
        )

        for numero, producto in enumerate(
            productos,
            start=1
        ):
            print(
                f"{numero}. {producto}"
            )

    else:
        print(
            "❌ No se pudieron extraer productos "
            "en esta ejecución."
        )

    guardar_ultima_tanda(productos)
