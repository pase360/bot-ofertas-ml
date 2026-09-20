import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

def obtener_oferta_categoria():
    # Categorías oficiales de Mercado Libre Argentina (estables y siempre activas)
    categorias = [
        "MLA1051", # Celulares y Smartphones
        "MLA1648", # Computación y Notebooks
        "MLA1000", # Electrodomésticos
        "MLA1430"  # Ropa y Calzado
    ]
    cat_id = random.choice(categorias)
    
    url = f"https://api.mercadolibre.com/sites/MLA/search?category={cat_id}&sort=sold_quantity"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                # Tomamos uno de los productos más vendidos de la categoría
                item = random.choice(results[:10])
                titulo = item.get("title")
                precio = item.get("price")
                
                precio_formateado = f"${precio:,.0f}".replace(",", ".") if precio else "Consultar"
                
                permalink = item.get("permalink")
                link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
                
                imagen = item.get("thumbnail", "").replace("http://", "https://")
                if "-I.jpg" in imagen:
                    imagen = imagen.replace("-I.jpg", "-O.jpg")
                elif "-M.jpg" in imagen:
                    imagen = imagen.replace("-M.jpg", "-O.jpg")
                    
                return titulo, precio_formateado, link_afiliado, imagen
    except Exception as e:
        print(f"⚠️ Error en la consulta: {e}")
        
    return None

def enviar_a_whatsapp(mensaje, imagen_url):
    phone = os.environ.get("WHATSAPP_PHONE")
    apikey = os.environ.get("WHATSAPP_APIKEY")

    if not phone or not apikey:
        print("⚠️ Faltan las credenciales de WhatsApp en los Secrets.")
        return

    texto_completo = f"{mensaje}\n\n📷 {imagen_url}"
    url = f"https://api.textmebot.com/send.php?recipient={phone}&apikey={apikey}&text={requests.utils.quote(texto_completo)}"

    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            print("✅ ¡Oferta real enviada con éxito!")
        else:
            print(f"❌ Error al enviar a WhatsApp: Código {res.status_code}")
    except Exception as e:
        print(f"❌ Excepción en el envío: {str(e)}")

if __name__ == "__main__":
    print("--- CONSULTANDO CATEGORÍAS OFICIALES DE MERCADO LIBRE ---")
    
    producto = obtener_oferta_categoria()
    
    if producto:
        titulo, precio, link_afiliado, imagen_url = producto
        
        mensaje = (
            f"🔥 *OFERTA DESTACADA DE MERCADO LIBRE*\n\n"
            f"📦 *{titulo}*\n\n"
            f"💰 *Precio:* {precio}\n\n"
            f"🛒 *Comprá acá con descuento:* {link_afiliado}\n\n"
            f"📢 *Sumate o compartí el canal:* {LINK_CANAL_WHATSAPP}"
        )

        print(mensaje)
        enviar_a_whatsapp(mensaje, imagen_url)
    else:
        print("❌ No se pudo obtener el producto en este intento.")
