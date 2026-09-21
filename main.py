import os
import random
import requests
import urllib.parse

CLIENT_ID = os.environ.get("ML_CLIENT_ID", "3518144087916123")
CLIENT_SECRET = os.environ.get("ML_CLIENT_SECRET", "zyaMZNRVOXXJ25DFRIMxLsG9n0ioXyhV")

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
        print(f"Excepción al conectar con OAuth de ML: {e}")
    return None

def obtener_productos_de_ofertas():
    token = obtener_token_acceso()
    if not token:
        print("⚠️ No se pudo obtener el token de acceso.")
        return []

    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    links_encontrados = []
    
    try:
        # Endpoint oficial de ofertas y descuentos en Mercado Libre Argentina (MLA)
        url_api = "https://api.mercadolibre.com/catalog_deals/MLA"
        response = requests.get(url_api, headers=headers, timeout=10)
        print(f"DEBUG API Ofertas Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            # Las ofertas suelen venir organizadas en una lista o en la clave 'results' / 'elements'
            ofertas = data.get("results", []) or data.get("elements", [])
            print(f"DEBUG Ofertas totales encontradas: {len(ofertas)}")
            
            for item in ofertas:
                # Dependiendo de la estructura, extraemos el id del producto (id o item_id) y armamos el permalink o lo buscamos
                item_id = item.get("id") or item.get("item_id")
                if item_id:
                    # Consultamos el detalle del item para obtener su link directo y limpio
                    url_item = f"https://api.mercadolibre.com/items/{item_id}"
                    res_item = requests.get(url_item, headers=headers, timeout=5)
                    if res_item.status_code == 200:
                        permalink = res_item.json().get("permalink")
                        if permalink:
                            link_limpio = permalink.split('?')[0]
                            if link_limpio not in links_encontrados:
                                links_encontrados.append(link_limpio)
        else:
            print(f"DEBUG Error en API de Ofertas: {response.text}")
            
    except Exception as e:
        print(f"Excepción consultando ofertas: {e}")

    # Si conseguimos suficientes, mezclamos y devolvemos 10
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
    print("--- CONSULTANDO API DE OFERTAS DE MERCADO LIBRE ---")
    
    productos = obtener_productos_de_ofertas()
    
    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron obtener productos en esta ejecución de ofertas."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
