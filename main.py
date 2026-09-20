import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Lista de búsquedas directas con alta intención de compra en Argentina
OFERTAS_AFILIADAS = [
    {
        "titulo": "Celulares y Smartphones Libres",
        "precio": "Ver ofertas en Mercado Libre",
        "url": "https://listado.mercadolibre.com.ar/celulares-telefonos/smartphones/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_994755-MLA74971488183_032024-O.jpg"
    },
    {
        "titulo": "Notebooks y Laptops en Descuento",
        "precio": "Ver ofertas en Mercado Libre",
        "url": "https://listado.mercadolibre.com.ar/computacion/notebooks/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_678241-MLA72458124503_102023-O.jpg"
    },
    {
        "titulo": "Auriculares Inalámbricos Bluetooth",
        "precio": "Ver ofertas en Mercado Libre",
        "url": "https://listado.mercadolibre.com.ar/audio/auriculares-inalambricos/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_835213-MLA53965518290_022023-O.jpg"
    },
    {
        "titulo": "Zapatillas Deportivas de Marca",
        "precio": "Ver ofertas en Mercado Libre",
        "url": "https://listado.mercadolibre.com.ar/zapatillas-deportivas/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_624893-MLA71548122910_092023-O.jpg"
    }
]

def enviar_a_textmebot(mensaje, imagen_url):
    phone = os.environ.get("WHATSAPP_PHONE")
    apikey = os.environ.get("WHATSAPP_APIKEY")

    if not phone or not apikey:
        print("⚠️ Faltan las credenciales en los Secrets.")
        return

    texto_completo = f"{mensaje}\n\n📷 {imagen_url}"
    url = f"https://api.textmebot.com/send.php?recipient={phone}&apikey={apikey}&text={requests.utils.quote(texto_completo)}"

    try:
        res = requests.get(url, timeout=15)
        if res.status_code == 200:
            print("✅ ¡Oferta con enlace de afiliado enviada con éxito!")
        else:
            print(f"❌ Error al enviar: Código {res.status_code}")
    except Exception as e:
        print(f"❌ Excepción: {str(e)}")

if __name__ == "__main__":
    print("--- GENERANDO OFERTA CON TAG DE AFILIADO ---")
    
    item = random.choice(OFERTAS_AFILIADAS)
    titulo = item["titulo"]
    precio = item["precio"]
    
    # Aquí se le adjunta tu tag exacto al enlace de Mercado Libre
    link_afiliado = f"{item['url']}?tag={AFILIADO_TAG}"
    imagen_url = item["imagen"]
    
    mensaje = (
        f"🔥 *OFERTA DESTACADA DE MERCADO LIBRE*\n\n"
        f"📦 *{titulo}*\n\n"
        f"💰 *Estado:* {precio}\n\n"
        f"🛒 *Comprá acá con descuento:* {link_afiliado}\n\n"
        f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
    )

    print(mensaje)
    enviar_a_textmebot(mensaje, imagen_url)
