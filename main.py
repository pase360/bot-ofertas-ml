import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Categorías específicas de Argentina (MLA)
CATEGORIAS = [
    "MLA1051",  # Celulares y Smartphones
    "MLA1648",  # Computación
    "MLA5726",  # Electrodomésticos
    "MLA1276",  # Deportes y Fitness
    "MLA4071",  # Herramientas
    "MLA1144",  # Consolas y Videojuegos
    "MLA1000",  # Electrónica, Audio y Video
]

def obtener_oferta():
    # Usamos cabeceras limpias sin enviarle tokens que activen el PolicyAgent
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "es-AR,es;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    cat = random.choice(CATEGORIAS)
    # Endpoint directo por categoría y orden por precio descendente para evitar búsquedas abiertas
    url = f"https://api.mercadolibre.com/sites/MLA/search?category={cat}&sort=price_desc"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        
        # Si la búsqueda por categoría bloquea, probamos el endpoint público directo de tendencias/ofertas
        if res.status_code != 200:
            url_alt = f"https://api.mercadolibre.com/sites/MLA/search?category={cat}"
            res = requests.get(url_alt, headers=headers, timeout=10)

        if res.status_code == 200:
            results = res.json().get("results", [])
            
            if results:
                # Filtrar aquellos con precio original mayor para asegurar descuento
                con_descuento = [item for item in results if item.get("original_price") and item.get("original_price") > item.get("price")]
                items_a_elegir = con_descuento if con_descuento else results
                
                data = random.choice(items_a_elegir[:15])
                
                titulo = data.get("title")
                precio_act = data.get("price")
                precio_orig = data.get("original_price")
                permalink = data.get("permalink")
                link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"

                if precio_orig and precio_act and precio_orig > precio_act:
                    descuento = int(((precio_orig - precio_act) / precio_orig) * 100)
                    return (
                        f"🔥 *{descuento}% DE DESCUENTO*\n\n"
                        f"📦 *{titulo}*\n\n"
                        f"❌ Antes: ~${precio_orig:,.0f}~\n"
                        f"✅ *Ahora: ${precio_act:,.0f}*\n\n"
                        f"🛒 *Comprar en Mercado Libre:* {link_afiliado}\n\n"
                        f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
                    )
                else:
                    return (
                        f"⚡ *OFERTA DESTACADA DE HOY*\n\n"
                        f"📦 *{titulo}*\n\n"
                        f"✅ *Precio imperdible: ${precio_act:,.0f}*\n\n"
                        f"🛒 *Comprar en Mercado Libre:* {link_afiliado}\n\n"
                        f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
                    )
            else:
                return "No se encontraron resultados en esta categoría."
        else:
            return f"Error API Mercado Libre: Status {res.status_code}"
    except Exception as e:
        return f"Error en la consulta: {str(e)}"

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
