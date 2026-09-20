import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

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
    }
]

def enviar_via_meta_cloud(mensaje, imagen_url):
    token = os.environ.get("WHATSAPP_TOKEN")
    phone_id = os.environ.get("WHATSAPP_PHONE_ID")
    # El destino puede ser tu número de prueba inicial o el destinatario/canal autorizado
    destinatario = os.environ.get("WHATSAPP_DESTINATARIO") 

    if not token or not phone_id or not destinatario:
        print("⚠️ Faltan credenciales de la Cloud API de Meta en los Secrets.")
        return

    url = f"https://graph.facebook.com/v18.0/{phone_id}/messages"
    
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Enviamos primero la imagen con texto descriptivo mediante la Cloud API oficial
    payload = {
        "messaging_product": "whatsapp",
        "recipient_type": "individual",
        "to": destinatario,
        "type": "image",
        "image": {
            "link": imagen_url,
            "caption": mensaje
        }
    }

    try:
        res = requests.post(url, json=payload, headers=headers, timeout=15)
        if res.status_code == 200:
            print("✅ ¡Oferta e imagen publicadas con éxito mediante la API oficial de Meta!")
        else:
            print(f"❌ Error en la API de Meta: Código {res.status_code} - {res.text}")
    except Exception as e:
        print(f"❌ Excepción en el envío: {str(e)}")

if __name__ == "__main__":
    print("--- PUBLICANDO OFERTA GRATUITA (META CLOUD API) ---")
    
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
        f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
    )

    print(mensaje)
    enviar_via_meta_cloud(mensaje, imagen_url)
