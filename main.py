import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

# Lista de IDs de productos reales y populares en Mercado Libre Argentina (evita errores de búsqueda)
PRODUCTOS_IDS = [
    "MLA1412852332", # Ejemplo de smartphone / tecnología popular
    "MLA1382146917", # Ejemplo de auricular / audio
    "MLA1142563121", # Ejemplo de zapatillas
    "MLA843215699",  # Ejemplo de electrodoméstico
    "MLA923145688"   # Ejemplo de notebook / computación
]

def obtener_producto_seguro():
    # Intentamos con varios IDs hasta que uno responda de forma óptima
    ids_mezclados = PRODUCTOS_IDS.copy()
    random.shuffle(ids_mezclados)
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    for item_id in ids_mezclados:
        url = f"https://api.mercadolibre.com/items/{item_id}"
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code == 200:
                item = response.json()
                titulo = item.get("title")
                precio = item.get("price")
                
                precio_formateado = f"${precio:,.0f}".replace(",", ".") if precio else "Consultar"
                
                permalink = item.get("permalink")
                link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
                
                # Imagen oficial en máxima calidad
                imagen = item.get("secure_thumbnail", "")
                if not imagen:
                    imagen = item.get("thumbnail", "").replace("http://", "https://")
                
                if "-I.jpg" in imagen:
                    imagen = imagen.replace("-I.jpg", "-O.jpg")
                elif "-M.jpg" in imagen:
                    imagen = imagen.replace("-M.jpg", "-O.jpg")
                    
                return titulo, precio_formateado, link_afiliado, imagen
        except Exception as e:
            continue
            
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
            print("✅ ¡Oferta real enviada con éxito al canal/chat!")
        else:
            print(f"❌ Error al enviar a WhatsApp: Código {res.status_code}")
    except Exception as e:
        print(f"❌ Excepción en el envío: {str(e)}")

if __name__ == "__main__":
    print("--- CONSULTANDO PRODUCTO DIRECTO EN MERCADO LIBRE ---")
    
    producto = obtener_producto_seguro()
    
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
        print("❌ No se pudo conectar con los ítems de la API en este intento.")
