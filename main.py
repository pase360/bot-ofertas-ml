import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Catálogo masivo con categorías, enlaces de afiliado e imágenes de alta calidad
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

def obtener_oferta():
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
    
    return mensaje, imagen_url

if __name__ == "__main__":
    mensaje, imagen = obtener_oferta()
    print("--- MENSAJE PARA WHATSAPP ---")
    print(mensaje)
    print(f"\n--- IMAGEN ASOCIADA ---")
    print(imagen)
