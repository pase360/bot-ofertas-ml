import os
import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

BUSQUEDAS = ["ofertas", "tecnologia", "celulares", "notebook", "herramientas", "electrodomesticos"]

def obtener_access_token():
    client_id = os.environ.get("MELI_CLIENT_ID")
    client_secret = os.environ.get("MELI_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("⚠️ No se encontraron las variables de entorno MELI_CLIENT_ID o MELI_CLIENT_SECRET.")
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
        else:
            print(f"Error al obtener token ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"Excepción al solicitar token: {e}")
    return None

def obtener_oferta():
    token = obtener_access_token()
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"

    query = random.choice(BUSQUEDAS)
    url = f"https://api.mercadolibre.com/sites/MLA/search?q={query}"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            
            if results:
                # Filtrar productos con descuento real
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
            return f"Error API Mercado Libre: Status {res.status_code} - {res.text}"
    except Exception as e:
        return f"Error en la consulta: {str(e)}"

    return "No se encontraron publicaciones."

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
