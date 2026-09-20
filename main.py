import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

CATEGORIAS_CON_IMAGENES = [
    {
        "titulo": "Smartphones y Celulares Libres",
        "url": "https://www.mercadolibre.com.ar/celulares-telefonos/smartphones",
        "imagen": "https://images.unsplash.com/photo-1511707171634-5f897ff02aa9?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Notebooks y Laptops en Oferta",
        "url": "https://www.mercadolibre.com.ar/computacion/notebooks-PCs",
        "imagen": "https://images.unsplash.com/photo-1496181133206-80ce9b88a853?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Auriculares y Audio Inalámbrico",
        "url": "https://www.mercadolibre.com.ar/audio/auriculares",
        "imagen": "https://images.unsplash.com/photo-1505740420928-5e560c06d30e?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Zapatillas y Calzado Deportivo",
        "url": "https://www.mercadolibre.com.ar/zapatillas",
        "imagen": "https://images.unsplash.com/photo-1542291026-7eec264c27ff?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Smart TVs y Pantallas 4K",
        "url": "https://www.mercadolibre.com.ar/televisores/televisores",
        "imagen": "https://images.unsplash.com/photo-1593359677879-a4bb92f829d1?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Herramientas y Construcción",
        "url": "https://www.mercadolibre.com.ar/herramientas",
        "imagen": "https://images.unsplash.com/photo-1504148455328-c376907d081c?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Electrodomésticos para el Hogar",
        "url": "https://www.mercadolibre.com.ar/electrodomesticos",
        "imagen": "https://images.unsplash.com/photo-1556911220-e15b29be8c8f?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Consolas y Videojuegos",
        "url": "https://www.mercadolibre.com.ar/video-juegos/consolas",
        "imagen": "https://images.unsplash.com/photo-1612287230202-1ff1d85d1bdf?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Perfumes e Importados",
        "url": "https://www.mercadolibre.com.ar/belleza-y-cuidado-personal/perfumes",
        "imagen": "https://images.unsplash.com/photo-1523293182086-7651a899d37f?q=80&w=1000&auto=format&fit=crop"
    },
    {
        "titulo": "Deportes y Fitness",
        "url": "https://www.mercadolibre.com.ar/deportes-y-fitness",
        "imagen": "https://images.unsplash.com/photo-1517838277536-f5f99be501cd?q=80&w=1000&auto=format&fit=crop"
    }
]

def enviar_a_whatsapp(mensaje, imagen_url):
    phone = os.environ.get("WHATSAPP_PHONE")
    apikey = os.environ.get("WHATSAPP_APIKEY")

    if not phone or not apikey:
        print("⚠️ No se encontraron las credenciales de WhatsApp en los Secrets de GitHub.")
        return

    # Envío mediante API configurada con texto e imagen
    url = f"https://api.textmebot.com/send.php?recipient={phone}&apikey={apikey}&text={requests.utils.quote(mensaje + '\n\n📸 ' + imagen_url)}"

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            print("✅ ¡Oferta e imagen enviadas a WhatsApp con éxito!")
        else:
            print(f"❌ Error al enviar a WhatsApp: Código {res.status_code}")
    except Exception as e:
        print(f"❌ Excepción en el envío: {str(e)}")

if __name__ == "__main__":
    item = random.choice(CATEGORIAS_CON_IMAGENES)
    titulo = item["titulo"]
    link_afiliado = f"{item['url']}?tag={AFILIADO_TAG}"
    imagen_url = item["imagen"]

    mensaje = (
        f"🔥 *OFERTA DESTACADA DE HOY*\n\n"
        f"📦 *{titulo}*\n\n"
        f"🛒 *Mirá los descuentos acá:* {link_afiliado}\n\n"
        f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
    )

    print("--- PROCESANDO OFERTA ---")
    print(mensaje)
    
    # Dispara el envío real
    enviar_a_whatsapp(mensaje, imagen_url)
