import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Categorías con ofertas permanentes
CATEGORIAS = [
    "MLA1051",  # Celulares
    "MLA1648",  # Computación
    "MLA5726",  # Electrodomésticos
    "MLA1276",  # Deportes
    "MLA4071",  # Herramientas
    "MLA1144",  # Consolas
]

def obtener_oferta():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Elegimos una categoría al azar
    cat = random.choice(CATEGORIAS)
    url = f"https://api.mercadolibre.com/highlights/MLA/category/{cat}"
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            content = res.json().get("content", [])
            # Filtramos solo los ítems individuales
            items = [item for item in content if item.get("type") == "item"]
            
            if items:
                # Elegimos una oferta al azar dentro de los destacados
                item_elegido = random.choice(items[:10])
                item_id = item_elegido.get("id")
                
                # Consultamos el detalle del producto específico
                url_item = f"https://api.mercadolibre.com/items/{item_id}"
                res_item = requests.get(url_item, headers=headers, timeout=10)
                
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
    except Exception as e:
        return f"Error en la consulta: {str(e)}"
        
    return "No se pudieron obtener productos destacados."

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
