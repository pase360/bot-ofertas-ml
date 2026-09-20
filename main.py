import os
import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Lista de IDs de productos populares y activos en Mercado Libre Argentina
PRODUCTOS_SEED = [
    "MLA1388349234", "MLA1145628190", "MLA1412093842", "MLA1365492019",
    "MLA1108239012", "MLA1428392011", "MLA1142938472", "MLA1392810482",
    "MLA1120394821", "MLA1492019283", "MLA1372910293", "MLA1182930492"
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

    # Seleccionamos un pool al azar de IDs para consultar
    ids_seleccionados = random.sample(PRODUCTOS_SEED, min(5, len(PRODUCTOS_SEED)))
    
    for item_id in ids_seleccionados:
        try:
            url_item = f"https://api.mercadolibre.com/items/{item_id}"
            res = requests.get(url_item, headers=headers, timeout=10)

            if res.status_code == 200:
                data = res.json()
                
                # Verificar que el producto esté activo
                if data.get("status") == "active":
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
        except Exception:
            continue

    return "No se pudo obtener ningún producto activo en este intento."

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
