import os
import random
import requests
import urllib.parse

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

OFERTAS_CATEGORIAS = [
    {
        "titulo": "Smart TVs LED en Oferta y Cuotas",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/televisores/smart-tv/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_994755-MLA74971488183_032024-O.jpg"
    },
    {
        "titulo": "Auriculares Inalámbricos Más Vendidos",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/audio/auriculares-inalambricos/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_835213-MLA53965518290_022023-O.jpg"
    },
    {
        "titulo": "Zapatillas Deportivas Primeras Marcas",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/zapatillas-deportivas/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_624893-MLA71548122910_092023-O.jpg"
    },
    {
        "titulo": "Notebooks y Laptops con Descuento",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/computacion/notebooks/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_678241-MLA72458124503_102023-O.jpg"
    }
]

def enviar_a_whatsapp(mensaje, imagen_url):
    phone = os.environ.get("WHATSAPP_PHONE")
    apikey = os.environ.get("WHATSAPP_APIKEY")

    if not phone or not apikey:
        print("⚠️ Faltan las credenciales de WhatsApp en los Secrets de GitHub.")
        return

    mensaje_completo = f"{mensaje}\n\n📷 Imagen: {imagen_url}"
    mensaje_codificado = urllib.parse.quote(mensaje_completo)
    
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={mensaje_codificado}&apikey={apikey}"

    try:
        res = requests.get(url, timeout=15)
        # El código 201 en CallMeBot indica éxito de envío
        if res.status_code in [200, 201]:
            print("✅ ¡Oferta enviada a tu WhatsApp con éxito!")
        else:
            print(f"❌ Error al enviar a WhatsApp: Código {res.status_code}")
    except Exception as e:
        print(f"❌ Excepción: {str(e)}")

if __name__ == "__main__":
    print("--- GENERANDO OFERTA DE CATEGORÍA ---")
    
    item = random.choice(OFERTAS_CATEGORIAS)
    titulo = item["titulo"]
    precio = item["precio"]
    
    link_afiliado = f"{item['url_base']}?tag={AFILIADO_TAG}"
    imagen_url = item["imagen"]
    
    mensaje = (
        f"🔥 *¡OFERTAS DESTACADAS EN MERCADO LIBRE!* 🔥\n\n"
        f"📦 *{titulo}*\n\n"
        f"💰 *Estado:* {precio}\n\n"
        f"🛒 *Mirá todas las opciones y comprá acá:* {link_afiliado}\n\n"
        f"📢 *Sumate al canal para más ofertas:* {LINK_CANAL_WHATSAPP}"
    )

    print(mensaje)
    enviar_a_whatsapp(mensaje, imagen_url)
