import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

CATEGORIAS = ["MLA1051", "MLA1648", "MLA5726", "MLA1276", "MLA4071"]

def obtener_oferta():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }
    
    # 1. Intento por categorías
    for cat_id in CATEGORIAS:
        url = f"https://api.mercadolibre.com/sites/MLA/search?category={cat_id}&limit=50"
        res = requests.get(url, headers=headers)
        if res.status_code == 200:
            for item in res.json().get("results", []):
                p_orig = item.get("original_price")
                p_act = item.get("price")
                if p_orig and p_act and p_orig > p_act:
                    desc = int(((p_orig - p_act) / p_orig) * 100)
                    if desc >= 10:
                        tit = item.get("title")
                        link = f"{item.get('permalink')}?tag={AFILIADO_TAG}"
                        return (
                            f"🔥 *{desc}% DE DESCUENTO*\n\n"
                            f"📦 *{tit}*\n\n"
                            f"❌ Antes: ~${p_orig:,.0f}~\n"
                            f"✅ *Ahora: ${p_act:,.0f}*\n\n"
                            f"🛒 *Comprar:* {link}\n\n"
                            f"📢 *Canal:* {LINK_CANAL_WHATSAPP}"
                        )

    # 2. Respaldo asegurado si la búsqueda por categoría no trae precios originales
    url_backup = "https://api.mercadolibre.com/sites/MLA/search?q=oferta&limit=10"
    res_b = requests.get(url_backup, headers=headers)
    if res_b.status_code == 200 and res_b.json().get("results"):
        item = res_b.json()["results"][0]
        tit = item.get("title")
        p_act = item.get("price")
        link = f"{item.get('permalink')}?tag={AFILIADO_TAG}"
        return (
            f"⚡ *OFERTA DESTACADA*\n\n"
            f"📦 *{tit}*\n\n"
            f"✅ *Precio imperdible: ${p_act:,.0f}*\n\n"
            f"🛒 *Comprar:* {link}\n\n"
            f"📢 *Canal:* {LINK_CANAL_WHATSAPP}"
        )
    return "No se pudo recuperar ninguna oferta."

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
