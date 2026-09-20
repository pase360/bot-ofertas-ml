import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Lista de productos específicos con enlaces directos y precios reales en Argentina
PRODUCTOS_OFERTA = [
    {
        "titulo": "Notebook Lenovo IdeaPad Slim Core i3 8gb Ssd 128gb",
        "precio": "$754.699",
        "url": "https://www.mercadolibre.com.ar/notebook-lenovo-ideapad-slim-core-i3-n305-8gb-ssd-128gb-156-win11/p/MLA33333333", # Reemplazable por permalink directo de producto
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_798451-MLA70215489123_062023-O.jpg"
    },
    {
        "titulo": "Smartphone Samsung Galaxy A05s 128gb 4gb Ram",
        "precio": "$299.999",
        "url": "https://www.mercadolibre.com.ar/samsung-galaxy-a05s-dual-sim-128gb-verde-claro-4gb-ram/p/MLA28456123",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_994755-MLA74971488183_032024-O.jpg"
    },
    {
        "titulo": "Auriculares Inalámbricos Xiaomi Redmi Buds 4 Active",
        "precio": "$34.999",
        "url": "https://www.mercadolibre.com.ar/xiaomi-redmi-buds-4-active-black/p/MLA22554411",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_835213-MLA53965518290_022023-O.jpg"
    },
    {
        "titulo": "Zapatillas Urbanas Puma De Hombre o Mujer",
        "precio": "$65.999",
        "url": "https://www.mercadolibre.com.ar/zapatillas-puma-court-flex-v2/p/MLA19887766",
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
    
    # Integramos tu tag de afiliado directamente al link específico del producto
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
