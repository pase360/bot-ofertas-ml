import os
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

def obtener_access_token():
    client_id = os.environ.get("MELI_CLIENT_ID")
    client_secret = os.environ.get("MELI_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        print("⚠️ No se encontraron las credenciales MELI en el entorno.")
        return None

    url = "https://api.mercadolibre.com/oauth/token"
    payload = {
        "grant_type": "client_credentials",
        "client_id": client_id,
        "client_secret": client_secret
    }
    headers = {"accept": "application/json", "content-type": "application/x-www-form-urlencoded"}

    try:
        res = requests.post(url, data=payload, headers=headers, timeout=10)
        if res.status_code == 200:
            return res.json().get("access_token")
        else:
            print(f"Error autenticando ({res.status_code}): {res.text}")
    except Exception as e:
        print(f"Excepción al autenticar: {e}")
    return None

def obtener_oferta():
    token = obtener_access_token()
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    cat = random.choice(CATEGORIAS)
    # Usamos el endpoint de búsqueda directa por categoría ordenado por relevancia/descuentos
    url = f"https://api.mercadolibre.com/sites/MLA/search?category={cat}&sort=relevance"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            results = res.json().get("results", [])
            
            # Filtramos aquellos productos que tengan precio original mayor al actual (descuento real)
            ofertas = [item for item in results if item.get("original_price") and item.get("original_price") > item.get("price")]
            
            # Si no encontramos con descuento explícito en los primeros resultados, tomamos cualquier producto destacado
            items_a_elegir = ofertas if ofertas else results
            
            if items_a_elegir:
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
    except Exception as e:
        return f"Error en la consulta: {str(e)}"

    return "No se pudieron obtener productos."

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
