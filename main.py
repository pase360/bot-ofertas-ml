import requests
import random
import xml.etree.ElementTree as ET

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Feeds de ofertas / productos destacados de Mercado Libre Argentina
FEEDS_OFERTAS = [
    "https://listado.mercadolibre.com.ar/ofertas_rss",
    "https://listado.mercadolibre.com.ar/tecnologia_rss",
    "https://listado.mercadolibre.com.ar/celulares-telefonos_rss"
]

def obtener_oferta():
    # Simulamos un cliente normal con headers limpios
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    }

    url_feed = random.choice(FEEDS_OFERTAS)

    try:
        res = requests.get(url_feed, headers=headers, timeout=15)
        
        # Si el RSS responde bien
        if res.status_code == 200:
            root = ET.fromstring(res.text)
            items = root.findall("./channel/item")
            
            if items:
                item = random.choice(items[:15])
                titulo = item.find("title").text if item.find("title") is not None else "Oferta Destacada"
                link_original = item.find("link").text if item.find("link") is not None else ""
                
                # Limpiamos el link e inyectamos el tag de afiliado
                link_base = link_original.split("?")[0] if link_original else ""
                link_afiliado = f"{link_base}?tag={AFILIADO_TAG}" if link_base else link_original

                return (
                    f"🔥 *OFERTA DESTACADA DE HOY*\n\n"
                    f"📦 *{titulo}*\n\n"
                    f"🛒 *Ver Oferta en Mercado Libre:* {link_afiliado}\n\n"
                    f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
                )

        # Plan B de respaldo directo por API de ítems públicos si falla el RSS
        url_fallback = "https://api.mercadolibre.com/items/MLA1388349234" # Búsqueda directa alternativa
        res_fb = requests.get(url_fallback, headers=headers, timeout=10)
        if res_fb.status_code == 200:
            data = res_fb.json()
            titulo = data.get("title")
            precio = data.get("price")
            permalink = data.get("permalink")
            link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
            
            return (
                f"⚡ *OFERTA IMPERDIBLE*\n\n"
                f"📦 *{titulo}*\n\n"
                f"✅ *Precio: ${precio:,.0f}*\n\n"
                f"🛒 *Comprar en Mercado Libre:* {link_afiliado}\n\n"
                f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
            )
            
        return f"Error en la consulta: Status {res.status_code}"

    except Exception as e:
        return f"Error al procesar ofertas: {str(e)}"

if __name__ == "__main__":
    oferta_msg = obtener_oferta()
    print("--- OFERTA ENCONTRADA ---")
    print(oferta_msg)
