import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Base de productos estrella con alta demanda real en Argentina y sus URLs oficiales
OFERTAS_ESTRELLA = [
    {
        "titulo": "Smartphone Samsung Galaxy Libres y Desbloqueados",
        "precio": "$459.999",
        "url": "https://listado.mercadolibre.com.ar/celulares-telefonos/smartphones/samsung",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_994755-MLA74971488183_032024-O.jpg"
    },
    {
        "titulo": "Notebook Laptops Core i5 / Ryzen con Descuento",
        "precio": "$789.999",
        "url": "https://listado.mercadolibre.com.ar/computacion/notebooks",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_678241-MLA72458124503_102023-O.jpg"
    },
    {
        "titulo": "Auriculares Inalámbricos Bluetooth de Alta Gama",
        "precio": "$45.999",
        "url": "https://listado.mercadolibre.com.ar/audio/auriculares-inalambricos",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_835213-MLA53965518290_022023-O.jpg"
    },
    {
        "titulo": "Zapatillas Deportivas Primeras Marcas",
        "precio": "$89.999",
        "url": "https://listado.mercadolibre.com.ar/zapatillas-deportivas",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_624893-MLA71548122910_092023-O.jpg"
    },
    {
        "titulo": "Smart TV LED 4K UHD con Envíos Gratis",
        "precio": "$429.999",
        "url": "https://listado.mercadolibre.com.ar/televisores/smart-tv",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_789451-MLA70215489123_062023-O.jpg"
    }
]

def enviar_a_whatsapp(mensaje, imagen_url):
    phone = os.environ.get("WHATSAPP_PHONE")
    apikey = os.environ.get("WHATSAPP_APIKEY")

    if not phone or not apikey:
        print("⚠️ Faltan las credenciales de WhatsApp en los Secrets.")
        return

    texto_completo = f"{mensaje}\n\n📷 {imagen_url}"
    url = f"https://api.textmebot.com/send.php?recipient={phone}&apikey={apikey}&text={requests.utils.quote(texto_completo)}"

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            print("✅ ¡Oferta publicada con éxito en el canal!")
        else:
            print(f"❌ Error al enviar a WhatsApp: Código {res.status_code}")
    except Exception as e:
        print(f"❌ Excepción en el envío: {str(e)}")

if __name__ == "__main__":
    print("--- PROCESANDO OFERTA PARA EL CANAL ---")
    
    item = random.choice(OFERTAS_ESTRELLA)
    titulo = item["titulo"]
    precio = item["precio"]
    link_afiliado = f"{item['url']}?tag={AFILIADO_TAG}"
    imagen_url = item["imagen"]
    
    mensaje = (
        f"🔥 *OFERTA DESTACADA DE MERCADO LIBRE*\n\n"
        f"📦 *{titulo}*\n\n"
        f"💰 *Precio estimado:* {precio}\n\n"
        f"🛒 *Comprá acá con descuento:* {link_afiliado}\n\n"
        f"📢 *Sumate o compartí el canal:* *{LINK_CANAL_WHATSAPP}*"
    )

    print(mensaje)
    enviar_a_whatsapp(mensaje, imagen_url)
