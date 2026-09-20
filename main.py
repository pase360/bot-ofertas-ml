import os
import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

CATEGORIAS = [
    "MLA1051",  # Celulares
    "MLA1648",  # Computación
    "MLA5726",  # Electrodomésticos
    "MLA1276",  # Deportes
    "MLA4071",  # Herramientas
    "MLA1144",  # Consolas
]

def obtener_access_token():
    client_id = os.environ.get("MELI_CLIENT_ID")
    client_secret = os.environ.get("MELI_CLIENT_SECRET")

    if not client_id or not client_secret:
        return None

    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"
    }

    try:
        res = requests.post(url, data=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("access_token")
    except Exception:
        pass
    return None

def obtener_oferta():
    token = obtener_access_token()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    cat = random.choice(CATEGORIAS)
    
    # 1. Obtenemos las tendencias actuales de la categoría
    url_trends = f"https://api.mercadolibre.com/trends/MLA/{cat}"
    
    try:
        res_trends = requests.get(url_trends, headers=headers, timeout=10)
        kw = "ofertas"
        if res_trends.status_code == 200:
            trends = res_trends.json()
            if trends:
                kw = random.choice(trends).get("keyword", "ofertas")

        # 2. Buscamos productos reales basados en la tendencia
        url_search = f"https://api.mercadolibre.com/sites/MLA/search?q={kw}&limit=10"
        res_search = requests.get(url_search, headers=headers, timeout=10)

        if res_search.status_code == 200:
            results = res_search.json().get("results", [])
            
            if results:
                # Priorizar productos con precio original superior al actual (con descuento real)
                con_descuento = [i for i in results if i.get("original_price") and i.get("original_price") > i.get("price")]
                items_pool = con_descuento if con_descuento else results
                
                item = random.choice(items_pool)
                titulo = item.get("title")
                precio_act = item.get("price")
                precio_orig = item.get("original_price")
                permalink = item.get("permalink")
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

        return f"No se encontraron resultados para la búsqueda '{kw}' (Status {res_search.status_code})"

    except Exception as e:
        return f"Error en el proceso: {str(e)}"

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
