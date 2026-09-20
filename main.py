import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

TERMINOS = ["celulares", "notebook", "zapatillas", "smart tv", "herramientas", "ofertas"]

def obtener_oferta():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/115.0.0.0 Safari/537.36"
    }
    
    for termino in TERMINOS:
        url = f"https://api.mercadolibre.com/sites/MLA/search?q={termino}&limit=30"
        res = requests.get(url, headers=headers)
        
        if res.status_code == 200:
            datos = res.json()
            for item in datos.get("results", []):
                precio_orig = item.get("original_price")
                precio_act = item.get("price")
                
                # Si tiene precio original y es mayor al actual, calculamos el descuento
                if precio_orig and precio_act and precio_orig > precio_act:
                    descuento = int(((precio_orig - precio_act) / precio_orig) * 100)
                    if descuento >= 10:
                        titulo = item.get("title")
                        permalink = item.get("permalink")
                        link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
                        
                        return (
                            f"🔥 *{descuento}% DE DESCUENTO*\n\n"
                            f"📦 *{titulo}*\n\n"
                            f"❌ Antes: ~${precio_orig:,.0f}~\n"
                            f"✅ *Ahora: ${precio_act:,.0f}*\n\n"
                            f"🛒 *Comprar en Mercado Libre:* {link_afiliado}\n\n"
                            f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
                        )

    # Si no encontró ninguno con filtro estricto, agarra la primera publicación destacada
    url_backup = "https://api.mercadolibre.com/sites/MLA/search?q=oferta&limit=5"
    res_b = requests.get(url_backup, headers=headers)
    if res_b.status_code == 200 and res_b.json().get("results"):
        item = res_b.json()["results"][0]
        titulo = item.get("title")
        precio_act = item.get("price")
        permalink = item.get("permalink")
        link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
        
        return (
            f"⚡ *OFERTA DESTACADA*\n\n"
            f"📦 *{titulo}*\n\n"
            f"✅ *Precio imperdible: ${precio_act:,.0f}*\n\n"
            f"🛒 *Comprar en Mercado Libre:* {link_afiliado}\n\n"
            f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
        )

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
