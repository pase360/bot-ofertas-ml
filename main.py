import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Categorías populares en Argentina
CATEGORIAS = [
    "MLA1051",  # Celulares y Smartphones
    "MLA1648",  # Computación
    "MLA5726",  # Electrodomésticos
    "MLA1276",  # Deportes y Fitness
    "MLA4071",  # Herramientas
    "MLA1144",  # Consolas y Videojuegos
]

def obtener_oferta():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }

    cat = random.choice(CATEGORIAS)
    # Endpoint de productos destacados por categoría (Endpoint oficial pública)
    url_highlights = f"https://api.mercadolibre.com/highlights/MLA/category/{cat}"

    try:
        res = requests.get(url_highlights, headers=headers, timeout=10)
        
        if res.status_code == 200:
            content = res.json().get("content", [])
            # Filtrar solo elementos de tipo producto
            item_ids = [item["id"] for item in content if item.get("type") == "item"]
            
            if item_ids:
                item_id = random.choice(item_ids[:10])
                # Consultar detalles del producto directamente por su ID
                res_item = requests.get(f"https://api.mercadolibre.com/items/{item_id}", headers=headers, timeout=10)
                
                if res_item.status_code == 200:
                    data = res_item.json()
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

        return f"Error al consultar destacados (Status {res.status_code})"

    except Exception as e:
        return f"Error en el proceso: {str(e)}"

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
