import os
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Términos de búsqueda con alto volumen de ofertas activa en ML Argentina
TERMINOS_BUSQUEDA = [
    "ofertas",
    "descuento",
    "liquidacion",
    "celulares",
    "notebook",
    "zapatillas",
    "smart tv",
    "herramientas"
]

def obtener_oferta():
    for termino in TERMINOS_BUSQUEDA:
        url = f"https://api.mercadolibre.com/sites/MLA/search?q={termino}&limit=50"
        headers = {"User-Agent": "Mozilla/5.0"}
        res = requests.get(url, headers=headers)
        
        if res.status_code == 200:
            datos = res.json()
            for item in datos.get("results", []):
                precio_orig = item.get("original_price")
                precio_act = item.get("price")
                
                # Chequeo de descuento
                if precio_orig and precio_act and precio_act < precio_orig:
                    descuento = int(((precio_orig - precio_act) / precio_orig) * 100)
                    
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
    
    # Respaldo de seguridad: Toma el primer producto con mejor precio si no detecta original_price en la API
    url_fallback = "https://api.mercadolibre.com/sites/MLA/search?q=oferta%20del%20dia&limit=10"
    res = requests.get(url_fallback)
    if res.status_code == 200:
        item = res.json().get("results", [])[0]
        titulo = item.get("title")
        precio_act = item.get("price")
        permalink = item.get("permalink")
        link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
        
        return (
            f"⚡ *OFERTA DESTACADA DEL DÍA*\n\n"
            f"📦 *{titulo}*\n\n"
            f"✅ *Precio imperdible: ${precio_act:,.0f}*\n\n"
            f"🛒 *Comprar en Mercado Libre:* {link_afiliado}\n\n"
            f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
        )

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
