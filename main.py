import os
import random
import requests
from bs4 import BeautifulSoup
import urllib.parse


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
        response = requests.get(url, headers=headers, timeout=15)

        print(f"DEBUG Status Más Vendidos: {response.status_code}")

        if response.status_code == 200:
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

        else:
            print(
                f"DEBUG Error al acceder a la página: "
                f"{response.status_code}"
            )

    except Exception as e:
        print(f"Excepción extrayendo productos: {e}")

    if len(links_encontrados) >= 10:
        return random.sample(links_encontrados, 10)

    return links_encontrados[:10]


def guardar_ultima_tanda(productos):
    if not productos:
        contenido = "No se pudieron extraer productos en esta ejecución."
    else:
        contenido = "\n".join(productos)

    try:
        with open(
            "ultima_tanda.txt",
            "w",
            encoding="utf-8"
        ) as archivo:
            archivo.write(contenido)

        print("✅ ultima_tanda.txt generado correctamente")

    except Exception as e:
        print(f"❌ Error guardando ultima_tanda.txt: {e}")


def enviar_a_whatsapp(mensaje):
    phone = (
        os.environ.get("WHATSAPP_PHONE", "")
        .strip()
        .replace("+", "")
    )

    apikey = os.environ.get(
        "WHATSAPP_APIKEY",
        ""
    ).strip()

    if not phone or not apikey:
        print("⚠️ Faltan las credenciales de WhatsApp.")
        return

    mensaje_codificado = urllib.parse.quote(mensaje)

    url = (
        "https://api.textmebot.com/send.php"
        f"?phone={phone}"
        f"&text={mensaje_codificado}"
        f"&apikey={apikey}"
    )

    try:
        res = requests.get(url, timeout=15)

        print(
            f"Respuesta WhatsApp: "
            f"{res.text}"
        )

    except Exception as e:
        print(
            f"Error de red WhatsApp: "
            f"{str(e)}"
        )


if __name__ == "__main__":

    print(
        "--- EXTRAYENDO PRODUCTOS MÁS VENDIDOS ---"
    )

    productos = obtener_productos_mas_vendidos()

    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = (
            "No se pudieron extraer productos "
            "en esta ejecución."
        )

    print("Mensaje generado:")
    print(mensaje)

    guardar_ultima_tanda(productos)

    # Lo dejamos temporalmente hasta comprobar
    # que Automate pueda leer la tanda desde GitHub.
    enviar_a_whatsapp(mensaje)
