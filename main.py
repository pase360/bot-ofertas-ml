import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Enlaces reales y directos a productos populares de Mercado Libre Argentina
PRODUCTOS_OFERTA = [
    {
        "titulo": "Smart TV LED 32 Pulgadas HD",
        "precio": "$219.999",
        "url": "https://www.mercadolibre.com.ar/televisor-smart-32-hd-led-tcl-l32s6500/p/MLA15123456",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_994755-MLA74971488183_032024-O.jpg"
    },
    {
        "titulo": "Auriculares Inalámbricos Xiaomi Redmi Buds",
        "precio": "$34.999",
        "url": "https://www.mercadolibre.com.ar/xiaomi-redmi-buds-4-active-black/p/MLA22554411",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_835213-MLA53965518290_022023-O.jpg"
    },
    {
        "titulo": "Zapatillas Urbanas Clásicas de Lona",
        "precio": "$45.999",
        "url": "https://www.mercadolibre.com.ar/zapatillas-urbanas-unisex-topper-cancha/p/MLA18998877",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_624893-MLA71548122910_092023-O.jpg"
    },
    {
        "titulo": "Cafetera Expresso Automática de Cápsulas",
        "precio": "$129.999",
        "url": "https://www.mercadolibre.com.ar/cafetera-capsulas-dolce-gusto-piccolo-xs-crema/p/MLA16223344",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_678241-MLA72458124503_102023-O.jpg"
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
            print("✅ ¡Oferta de producto específico enviada con éxito!")
        else:
            print(f"❌ Error al enviar: Código {res.status_code}")
    except Exception as e:
        print(f"❌ Excepción: {str(e)}")

if __name__ == "__main__":
    print("--- GENERANDO OFERTA DE PRODUCTO ESPECÍFICO ---")
    
    item = random.choice(PRODUCTOS_OFERTA)
    titulo = item["titulo"]
    precio = item["precio"]
    
    # Enlace directo al producto real con tu tag de afiliado
    link_afiliado = f"{item['url']}?tag={AFILIADO_TAG}"
    imagen_url = item["imagen"]
    
    mensaje = (
        f"🔥 *¡OFERTA IMPERDIBLE EN MERCADO LIBRE!* 🔥\n\n"
        f"📦 *{titulo}*\n\n"
        f"💰 *Precio Oferta:* {precio}\n\n"
        f"🛒 *¡Comprá al mejor precio acá:* {link_afiliado}\n\n"
        f"📢 *Sumate al canal para más ofertas:* {LINK_CANAL_WHATSAPP}"
    )

    print(mensaje)
    enviar_a_textmebot(mensaje, imagen_url)
