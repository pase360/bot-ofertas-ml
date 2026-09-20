import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

BUSQUEDAS = ["ofertas", "tecnologia", "celulares", "notebook", "herramientas", "electrodomesticos"]

def obtener_oferta():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }

    query = random.choice(BUSQUEDAS)
    url = f"https://api.mercadolibre.com/sites/MLA/search?q={query}"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            
            if results:
                # Priorizar productos que tengan descuento explícito
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
            return f"Error API Mercado Libre: Status {res.status_code}"
    except Exception as e:
        return f"Error en la consulta: {str(e)}"

    return "No se encontraron publicaciones."

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
