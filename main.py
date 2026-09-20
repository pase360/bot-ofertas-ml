import requests
import random

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Lista amplia de términos de alta rotación
TERMINOS = [
    "celular", "notebook", "televisor", "zapatillas", "herramientas", 
    "auriculares", "cafetera", "reloj", "freidora de aire", "consola"
]

def obtener_oferta():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    # Elegimos un término al azar para que varíe en cada ejecución
    termino = random.choice(TERMINOS)
    url = f"https://api.mercadolibre.com/sites/MLA/search?q={termino}&limit=20"
    
    try:
        res = requests.get(url, headers=headers, timeout=10)
        if res.status_code == 200:
            items = res.json().get("results", [])
            if items:
                # Elegimos uno de los primeros resultados
                item = items[0]
                titulo = item.get("title")
                precio_act = item.get("price")
                precio_orig = item.get("original_price")
                permalink = item.get("permalink")
                link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
                
                # Si tiene descuento lo calculamos, si no, mostramos la oferta destacada
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
        
    return "No se encontraron ítems para este término."

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
