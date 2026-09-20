import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Catálogo directo optimizado para afiliados (sin bloqueos de API)
PRODUCTOS_Y_CATEGORIAS = [
    {
        "titulo": "Smartphones y Celulares Libres en Oferta",
        "url": "https://www.mercadolibre.com.ar/celulares-telefonos/smartphones"
    },
    {
        "titulo": "Notebooks y Laptops Destacadas",
        "url": "https://www.mercadolibre.com.ar/computacion/notebooks-PCs"
    },
    {
        "titulo": "Auriculares Inalámbricos y Audio",
        "url": "https://www.mercadolibre.com.ar/audio/auriculares"
    },
    {
        "titulo": "Zapatillas y Calzado Deportivo",
        "url": "https://www.mercadolibre.com.ar/zapatillas"
    },
    {
        "titulo": "Smart TVs y LED 4K",
        "url": "https://www.mercadolibre.com.ar/televisores/televisores"
    },
    {
        "titulo": "Herramientas y Construcción",
        "url": "https://www.mercadolibre.com.ar/herramientas"
    },
    {
        "titulo": "Electrodomésticos para el Hogar",
        "url": "https://www.mercadolibre.com.ar/electrodomesticos"
    },
    {
        "titulo": "Consolas y Videojuegos",
        "url": "https://www.mercadolibre.com.ar/video-juegos/consolas"
    }
]

def obtener_oferta():
    item = random.choice(PRODUCTOS_Y_CATEGORIAS)
    titulo = item["titulo"]
    link_base = item["url"]
    link_afiliado = f"{link_base}?tag={AFILIADO_TAG}"

    return (
        f"🔥 *OFERTA DESTACADA DE HOY*\n\n"
        f"📦 *{titulo}*\n\n"
        f"🛒 *Mirá todas las opciones y descuentos acá:* {link_afiliado}\n\n"
        f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
    )

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
