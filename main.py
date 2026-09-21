import os
import random
import requests
import urllib.parse
from bs4 import BeautifulSoup

# Categorías mixtas para buscar productos de alta demanda y rotación
CATEGORIAS_BUSQUEDA = [
    "https://listado.mercadolibre.com.ar/televisores/smart-tv/_NoIndex_True",
    "https://listado.mercadolibre.com.ar/audio/auriculares-inalambricos/_NoIndex_True",
    "https://listado.mercadolibre.com.ar/zapatillas-deportivas/_NoIndex_True",
    "https://listado.mercadolibre.com.ar/computacion/notebooks/_NoIndex_True",
    "https://listado.mercadolibre.com.ar/hogar/electrodomesticos/_NoIndex_True"
]

def obtener_productos_aleatorios():
    links_encontrados = []
    
    # Headers para simular un navegador y evitar bloqueos básicos de scraping
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for url_cat in CATEGORIAS_BUSQUEDA:
        try:
            response = requests.get(url_cat, headers=headers, timeout=10)
            if response.status_code == 200:
                soup = BeautifulSoup(response.text, 'html.parser')
                # Buscamos los links de los productos en los listados de Mercado Libre
                items = soup.select('a.ui-search-item__group__element, a.poly-component__title')
                for item in items:
                    link = item.get('href')
                    if link and "mercadolibre.com.ar" in link and "#reco_item_pos" not in link:
                        # Limpiamos parámetros innecesarios para dejar el link base del producto
                        link_limpio = link.split('#')[0].split('?')[0]
                        if link_limpio not in links_encontrados:
                            links_encontrados.append(link_limpio)
        except Exception as e:
            print(f"Error al escrapear {url_cat}: {e}")

    # Si encontramos suficientes, mezclamos y seleccionamos 10; si no, completamos con lo que haya
    if len(links_encontrados) >= 10:
        return random.sample(links_encontrados, 10)
    else:
        return links_encontrados[:10]

def enviar_a_whatsapp(mensaje):
    phone = os.environ.get("WHATSAPP_PHONE", "").strip().replace("+", "")
    apikey = os.environ.get("WHATSAPP_APIKEY", "").strip()

    if not phone or not apikey:
        print("⚠️ Faltan las credenciales de WhatsApp.")
        return

    mensaje_codificado = urllib.parse.quote(mensaje)
    url = f"https://api.textmebot.com/send.php?phone={phone}&text={mensaje_codificado}&apikey={apikey}"

    try:
        res = requests.get(url, timeout=15)
        print(f"Respuesta: {res.text}")
    except Exception as e:
        print(f"Error de red: {str(e)}")

if __name__ == "__main__":
    print("--- BUSCANDO 10 PRODUCTOS ---")
    
    productos = obtener_productos_aleatorios()
    
    if productos:
        # Armamos el mensaje exclusivamente con los links uno debajo del otro
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron extraer productos en esta ejecución."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
