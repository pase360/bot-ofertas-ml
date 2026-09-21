import os
import random
import requests
import urllib.parse

CLIENT_ID = os.environ.get("ML_CLIENT_ID", "3518144087916123")
CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "zyaMZNRVOXXJ25DFRIMxLsG9n0ioXyhV")

# Categorías principales de Mercado Libre Argentina (IDs oficiales y estables)
CATEGORIAS_OFICIALES = [
    "MLA1002", # Celulares y Teléfonos
    "MLA1652", # Computación (Notebooks)
    "MLA1000", # Electrónica, Audio y Video
    "MLA1574", # Hogar y Electrodomésticos
    "MLA1144", # Deportes y Fitness
    "MLA1276", # Deportes y Fitness / Bicicletas
    "MLA1430", # Ropa y Accesorios
    "MLA1540", # Netbooks y Accesorios
    "MLA1743", # Autos, Motos y Otros
    "MLA1334"  # Libros, Revistas y Comics
]

def obtener_token_acceso():
    url_token = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }
    try:
        response = requests.post(url_token, data=payload, timeout=10)
        if response.status_code == 200:
            return response.json().get("access_token")
        else:
            print(f"Error al obtener token: {response.text}")
    except Exception as e:
        print(f"Excepción al conectar con OAuth: {e}")
    return None

def obtener_productos():
    token = obtener_token_acceso()
    if not token:
        print("⚠️ No se pudo obtener el token de acceso.")
        return []

    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    links_encontrados = []
    # Seleccionamos 4 categorías al azar de nuestra lista estable
    categorias_elegidas = random.sample(CATEGORIAS_OFICIALES, min(4, len(CATEGORIAS_OFICIALES)))

    for cat_id in categorias_elegidas:
        try:
            url_api = f"https://api.mercadolibre.com/sites/MLA/search?category={cat_id}&limit=15"
            response = requests.get(url_api, headers=headers, timeout=10)
            print(f"DEBUG Categoría {cat_id} - Status: {response.status_code}")
            
            if response.status_code == 200:
                resultados = response.json().get("results", [])
                for item in resultados:
                    permalink = item.get("permalink")
                    if permalink:
                        link_limpio = permalink.split('?')[0]
                        if link_limpio not in links_encontrados:
                            links_encontrados.append(link_limpio)
        except Exception as e:
            print(f"Error consultando categoría {cat_id}: {e}")

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
    print("--- CONSULTANDO PRODUCTOS DE MERCADO LIBRE ---")
    
    productos = obtener_productos()
    
    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron obtener productos en esta ejecución."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
