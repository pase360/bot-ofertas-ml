import os
import random
import requests
import urllib.parse

# Términos de búsqueda variados para que la API nos devuelva productos de alta demanda
TERMINOS_BUSQUEDA = [
    "smart tv",
    "auriculares inalambricos",
    "zapatillas deportivas",
    "notebook",
    "electrodomesticos hogar",
    "ofertas"
]

def obtener_productos_api():
    links_encontrados = []
    
    # Seleccionamos algunos términos al azar para mezclar categorías
    terminos_seleccionados = random.sample(TERMINOS_BUSQUEDA, min(3, len(TERMINOS_BUSQUEDA)))

    for termino in terminos_seleccionados:
        try:
            # Endpoint público de búsqueda de Mercado Libre (Argentina = MLA)
            url_api = f"https://api.mercadolibre.com/sites/MLA/search?q={urllib.parse.quote(termino)}&limit=15"
            response = requests.get(url_api, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                resultados = data.get("results", [])
                
                for item in resultados:
                    # Extraemos directamente el enlace permanente del producto
                    permalink = item.get("permalink")
                    if permalink:
                        # Limpiamos parámetros de tracking internos si los trae
                        link_limpio = permalink.split('?')[0]
                        if link_limpio not in links_encontrados:
                            links_encontrados.append(link_limpio)
        except Exception as e:
            print(f"Error consultando la API para '{termino}': {e}")

    # Mezclamos todos los resultados encontrados y devolvemos 10
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
    print("--- CONSULTANDO API DE MERCADO LIBRE ---")
    
    productos = obtener_productos_api()
    
    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron obtener productos en esta ejecución."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
