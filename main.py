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
    except Exception as e:
        print(f"Excepción al conectar con OAuth: {e}")
    return None

def obtener_categorias_dinamicas(headers):
    """Obtiene la lista completa de categorías oficiales de Argentina desde la API"""
    try:
        url = "https://api.mercadolibre.com/sites/MLA/categories"
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            return [cat["id"] for cat in response.json()]
    except Exception as e:
        print(f"Error obteniendo categorías: {e}")
    return []

def obtener_productos_dinamicos():
    token = obtener_token_acceso()
    if not token:
        print("⚠️ No se pudo obtener el token de acceso.")
        return []

    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    # Obtenemos las categorías de forma dinámica de la API
    todas_las_categorias = obtener_categorias_dinamicas(headers)
    if not todas_las_categorias:
        print("⚠️ No se pudieron cargar las categorías dinámicas.")
        return []

    links_encontrados = []
    # Seleccionamos 4 categorías al azar del total disponible en la plataforma
    categorias_elegidas = random.sample(todas_las_categorias, min(4, len(todas_las_categorias)))

    for cat_id in categorias_elegidas:
        try:
            url_api = f"https://api.mercadolibre.com/sites/MLA/search?category={cat_id}&limit=10"
            response = requests.get(url_api, headers=headers, timeout=10)
            
            if response.status_code == 200:
                resultados = response.json().get("results", [])
                for item in resultados:
                    permalink = item.get("permalink")
                    if permalink:
                        link_limpio = permalink.split('?')[0]
                        if link_limpio not in links_encontrados:
                            links_encontrados.append(link_limpio)
        except Exception as e:
            print(f"Error en categoría {cat_id}: {e}")

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
    print("--- CONSULTANDO PRODUCTOS DINÁMICOS DE MERCADO LIBRE ---")
    
    productos = obtener_productos_dinamicos()
    
    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron obtener productos en esta ejecución."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
