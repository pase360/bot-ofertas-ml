import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Lista amplia de publicaciones reales de diferentes categorías
PRODUCTOS_MLB = [
    "MLA1388349234", "MLA1412093842", "MLA1108239012", 
    "MLA1428392011", "MLA1142938472", "MLA1392810482", 
    "MLA1120394821", "MLA1372910293", "MLA1182930492",
    "MLA1365492019", "MLA1492019283", "MLA1145628190"
]

def obtener_producto():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    # Mezclamos los productos para intentar con uno al azar
    random.shuffle(PRODUCTOS_MLB)

    for item_id in PRODUCTOS_MLB:
        url = f"https://api.mercadolibre.com/items/{item_id}"
        
        try:
            res = requests.get(url, headers=headers, timeout=10)
            
            if res.status_code == 200:
                data = res.json()
                
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
                        f"⚡ *PRODUCTO DESTACADO*\n\n"
                        f"📦 *{titulo}*\n\n"
                        f"✅ *Precio: ${precio_act:,.0f}*\n\n"
                        f"🛒 *Comprar en Mercado Libre:* {link_afiliado}\n\n"
                        f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
                    )
        except Exception:
            continue

    return "Error: No se pudo cargar ningún producto de la lista."

if __name__ == "__main__":
    oferta_msg = obtener_producto()
    print("--- PRODUCTO ENCONTRADO ---")
    print(oferta_msg)
