import os
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

CATEGORIAS = [
    "MLA1051",  # Celulares
    "MLA1648",  # Computación
    "MLA5726",  # Electrodomésticos
    "MLA1276",  # Deportes
    "MLA4071",  # Herramientas
    "MLA1144",  # Consolas
    "MLA1574",  # Hogar
    "MLA1246",  # Belleza
    "MLA1039",  # Cámaras
    "MLA1182",  # Música
]

def obtener_oferta():
    for cat_id in CATEGORIAS:
        # Buscamos los primeros 30 productos de la categoría
        url = f"https://api.mercadolibre.com/sites/MLA/search?category={cat_id}&limit=30"
        res = requests.get(url)
        if res.status_code == 200:
            datos = res.json()
            for item in datos.get("results", []):
                precio_orig = item.get("original_price")
                precio_act = item.get("price")
                
                # Verificamos si existe descuento real
                if precio_orig and precio_act and precio_act < precio_orig:
                    descuento = int(((precio_orig - precio_act) / precio_orig) * 100)
                    
                    # Filtro flexibilizado a partir de 10% de descuento
                    if descuento >= 10:
                        titulo = item.get("title")
                        permalink = item.get("permalink")
                        link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
                        
                        mensaje = (
                            f"🔥 *{descuento}% DE DESCUENTO*\n\n"
                            f"📦 *{titulo}*\n\n"
                            f"❌ Antes: ~${precio_orig:,.0f}~\n"
                            f"✅ *Ahora: ${precio_act:,.0f}*\n\n"
                            f"🛒 *Comprar en Mercado Libre:* {link_afiliado}\n\n"
                            f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
                        )
                        return mensaje
    return None

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    if oferta_msg:
        print("--- OFERTA ENCONTRADA ---")
        print(oferta_msg)
    else:
        print("No se encontraron ofertas en esta ejecución.")
