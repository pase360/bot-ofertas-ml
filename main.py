import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

def buscar_oferta_real_meli():
    busquedas = [
        "smartphone libre", 
        "notebook", 
        "auriculares inalambricos", 
        "zapatillas deportivas", 
        "smart tv", 
        "consola playstation"
    ]
    q = random.choice(busquedas)
    
    url = f"https://api.mercadolibre.com/sites/MLA/search?q={q}&sort=sold_quantity"
    
    # Encabezados obligatorios para evitar que Mercado Libre rechace la consulta de GitHub
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }
    
    try:
        response = requests.get(url, headers=headers, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                item = random.choice(results[:5])
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
        print(f"⚠️ Error al conectar con la API de Mercado Libre: {e}")
        
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
            print("✅ ¡Oferta real de Mercado Libre enviada con éxito!")
        else:
            print(f"❌ Error al enviar a WhatsApp: Código {res.status_code}")
    except Exception as e:
        print(f"❌ Excepción en el envío: {str(e)}")

if __name__ == "__main__":
    print("--- BUSCANDO PRODUCTO CON ALTA INTENCIÓN DE VENTA ---")
    
    producto = buscar_oferta_real_meli()
    
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
        print("❌ No se pudo obtener ningún producto en esta ejecución.")
