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

def obtener_productos_de_tendencias():
    token = obtener_token_acceso()
    if not token:
        print("⚠️ No se pudo obtener el token de acceso.")
        return []

    headers = {
        "Authorization": f"Bearer {token}"
    }
    
    links_encontrados = []
    
    try:
        # Obtenemos las tendencias de búsqueda actuales en Argentina
        url_trends = "https://api.mercadolibre.com/trends/MLA"
        response = requests.get(url_trends, headers=headers, timeout=10)
        print(f"DEBUG Trends Status: {response.status_code}")
        
        if response.status_code == 200:
            tendencias = response.json()
            # Tomamos algunas palabras clave en tendencia al azar
            keywords = [t.get("keyword") for t in tendencias if "keyword" in t]
            palabras_elegidas = random.sample(keywords, min(5, len(keywords)))
            
            for palabra in palabras_elegidas:
                # Usamos el endpoint público de items directos o consulta por URL limpia de tendencia si está disponible, 
                # o armamos la consulta usando la keyword permitida en tendencias
                url_search = f"https://api.mercadolibre.com/sites/MLA/search?q={urllib.parse.quote(palabra)}&limit=5"
                res_search = requests.get(url_search, headers=headers, timeout=5)
                if res_search.status_code == 200:
                    resultados = res_search.json().get("results", [])
                    for item in resultados:
                        permalink = item.get("permalink")
                        if permalink:
                            link_limpio = permalink.split('?')[0]
                            if link_limpio not in links_encontrados:
                                links_encontrados.append(link_limpio)
        else:
            print(f"Error en tendencias: {response.text}")
    except Exception as e:
        print(f"Excepción en tendencias: {e}")

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
    print("--- CONSULTANDO TENDENCIAS DE MERCADO LIBRE ---")
    
    productos = obtener_productos_de_tendencias()
    
    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron obtener productos en esta ejecución."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
