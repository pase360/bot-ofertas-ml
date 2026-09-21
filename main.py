import os
import random
import requests
import urllib.parse

# URLs institucionales y secciones clave de alta conversión en Mercado Libre Argentina
URLS_BASE_MERCADOLIBRE = [
    "https://www.mercadolibre.com.ar/ofertas",
    "https://www.mercadolibre.com.ar/mas-vendidos",
    "https://www.mercadolibre.com.ar/coupon#nav-header",
    "https://www.mercadolibre.com.ar/suscripciones/mla",
    "https://www.mercadolibre.com.ar/c/tecnologia",
    "https://www.mercadolibre.com.ar/c/electrodomesticos",
    "https://www.mercadolibre.com.ar/c/herramientas-y-construccion",
    "https://www.mercadolibre.com.ar/c/deportes-y-fitness",
    "https://www.mercadolibre.com.ar/c/hogar-muebles-y-jardin",
    "https://www.mercadolibre.com.ar/c/ropa-y-accesorios"
]

def obtener_links_curados():
    # Mezclamos y seleccionamos 10 links variados de las secciones principales
    if len(URLS_BASE_MERCADOLIBRE) >= 10:
        return random.sample(URLS_BASE_MERCADOLIBRE, 10)
    else:
        return URLS_BASE_MERCADOLIBRE

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
    print("--- GENERANDO SELECCIÓN DE ENLACES DE MERCADO LIBRE ---")
    
    productos = obtener_links_curados()
    
    if productos:
        mensaje = "\n".join(productos)
    else:
        mensaje = "No se pudieron generar enlaces en esta ejecución."

    print("Mensaje a enviar:")
    print(mensaje)
    enviar_a_whatsapp(mensaje)
