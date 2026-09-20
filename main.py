import os
import random
import requests

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

def buscar_oferta_real_meli():
    # Palabras clave de productos con alta rotación y conversión en Argentina
    busquedas = ["smartphone libre", "notebook", "auriculares inalambricos", "zapatillas deportivas", "smart tv 4k", "perfume importado", "consola playstation"]
    q = random.choice(busquedas)
    
    # Consultamos la API de Mercado Libre ordenada por cantidad de ventas (los que más se venden)
    url = f"https://api.mercadolibre.com/sites/MLA/search?q={q}&sort=sold_quantity"
    
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            data = response.json()
            results = data.get("results", [])
            if results:
                # Tomamos uno de los primeros puestos (alta demanda)
                item = random.choice(results[:5])
                titulo = item.get("title")
                precio = item.get("price")
                
                # Formateamos el precio en pesos argentinos
                precio_formateado = f"${precio:,.0f}".replace(",", ".") if precio else "Consultar"
                
                permalink = item.get("permalink")
                # Agregamos tu tag de afiliado al enlace exacto del producto
                link_afiliado = f"{permalink}?tag={AFILIADO_TAG}"
                
                # Obtenemos la imagen oficial del producto y mejoramos la calidad a versión grande (-O.jpg)
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

    # Enviamos el mensaje estructurado con el link de la imagen real
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
