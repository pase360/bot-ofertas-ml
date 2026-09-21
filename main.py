import os
import random
import requests
import urllib.parse

# Credenciales de tu App de Mercado Libre
CLIENT_ID = os.environ.get("ML_CLIENT_ID", "3518144087916123")
CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "zyaMZNRVOXXJ25DFRIMxLsG9n0ioXyhV")

TERMINOS_BUSQUEDA = [
    "smart tv",
    "auriculares inalambricos",
    "zapatillas deportivas",
    "notebook",
    "electrodomesticos",
    "ofertas"
]

def obtener_token_acceso():
    """Genera un token de acceso temporal usando las credenciales de la App"""
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
            print(f"Error al obtener token de ML: {response.text}")
    except Exception as e:
        print(f"Excepción al conectar con OAuth de ML: {e}")
    return None

def obtener_productos_con_api():
    token = obtener_token_acceso()
    if not token:
        print("⚠️ No se pudo autenticar con la API de Mercado Libre.")
        return []

    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    links_encontrados = []
    terminos_seleccionados = random.sample(TERMINOS_BUSQUEDA, min(3, len(TERMINOS_BUSQUEDA)))

    for termino in terminos_seleccionados:
        try:
            url_api = f"https://api.mercadolibre.com/sites/MLA/search?q={urllib.parse.quote(termino)}&limit=15"
            response = requests.get(url_api, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                resultados = data.get("results", [])
                
                for item in resultados:
                    permalink = item.get("permalink")
                    if permalink:
                        link_limpio = permalink.split('?')[0]
                        if link_limpio not in links_encontrados:
                            links_encontrados.append(link_limpio)
        except Exception as e:
            print(f"Error buscando '{termino}': {e}")

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
    print("--- CONSULTANDO API OFICIAL DE MERCADO LIBRE ---")
    
    productos = obtener_productos_con_api()
    
    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron obtener productos autenticados en esta ejecución."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
