import os
import random
import requests
from bs4 import BeautifulSoup
import urllib.parse

def obtener_productos_mas_vendidos():
    url = "https://www.mercadolibre.com.ar/mas-vendidos"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    links_encontrados = []
    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f"DEBUG Status Más Vendidos: {response.status_code}")
        
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Buscamos todos los enlaces dentro de la página de más vendidos
            for a in soup.find_all('a', href=True):
                href = a['href']
                # Filtramos para quedarnos únicamente con links de productos individuales
                if ('/p/MLA' in href or '/MLA-' in href) and 'mas-vendidos' not in href:
                    link_limpio = href.split('?')[0]
                    if link_limpio.startswith('/'):
                        link_limpio = "https://www.mercadolibre.com.ar" + link_limpio
                    
                    if link_limpio not in links_encontrados:
                        links_encontrados.append(link_limpio)
        else:
            print(f"DEBUG Error al acceder a la página: {response.status_code}")
            
    except Exception as e:
        print(f"Excepción extrayendo productos: {e}")

    # Si encontramos suficientes, devolvemos 10 al azar para variar en cada ejecución
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
        print(f"Respuesta WhatsApp: {res.text}")
    except Exception as e:
        print(f"Error de red WhatsApp: {str(e)}")

if __name__ == "__main__":
    print("--- EXTRAYENDO PRODUCTOS MÁS VENDIDOS ---")
    
    productos = obtener_productos_mas_vendidos()
    
    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron extraer productos en esta ejecución."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
