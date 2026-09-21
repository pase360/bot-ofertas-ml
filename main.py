import os
import random
import requests
import urllib.parse

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

OFERTAS_CATEGORIAS = [
    {
        "titulo": "Smart TVs LED en Oferta y Cuotas",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/televisores/smart-tv/_NoIndex_True"
    },
    {
        "titulo": "Auriculares Inalambricos Mas Vendidos",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/audio/auriculares-inalambricos/_NoIndex_True"
    },
    {
        "titulo": "Zapatillas Deportivas Primeras Marcas",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/zapatillas-deportivas/_NoIndex_True"
    },
    {
        "titulo": "Notebooks y Laptops con Descuento",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/computacion/notebooks/_NoIndex_True"
    }
]

def enviar_a_whatsapp(mensaje):
    # Limpiamos espacios y quitamos el '+' si lo pusiste por error en el teléfono
    phone = os.environ.get("WHATSAPP_PHONE", "").strip().replace("+", "")
    apikey = os.environ.get("WHATSAPP_APIKEY", "").strip()

    print(f"DEBUG Teléfono limpio: {phone}")
    print(f"DEBUG APIKEY longitud limpia: {len(apikey)}")

    if not phone or not apikey:
        print("⚠️ Faltan las credenciales de WhatsApp en los Secrets de GitHub.")
        return

    mensaje_codificado = urllib.parse.quote(mensaje)
    url = f"https://api.callmebot.com/whatsapp.php?phone={phone}&text={mensaje_codificado}&apikey={apikey}"

    try:
        res = requests.get(url, timeout=15)
        print(f"Respuesta de CallMeBot (Código {res.status_code}): {res.text}")
        
        # Validamos si realmente dio éxito de entrega real
        if "Message queued" in res.text or "Success" in res.text or res.status_code == 200 and "ERROR" not in res.text:
            print("✅ ¡Mensaje aceptado y en camino a tu WhatsApp!")
        else:
            print("❌ La pasarela rechazó la clave o el teléfono. Revisa que tu número no tenga el signo '+' en los Secrets.")
    except Exception as e:
        print(f"❌ Excepción de red: {str(e)}")

if __name__ == "__main__":
    print("--- GENERANDO OFERTA ---")
    
    item = random.choice(OFERTAS_CATEGORIAS)
    titulo = item["titulo"]
    precio = item["precio"]
    link_afiliado = f"{item['url_base']}?tag={AFILIADO_TAG}"
    
    mensaje = (
        f"OFERTA DESTACADA MERCADO LIBRE\n\n"
        f"{titulo}\n"
        f"Estado: {precio}\n\n"
        f"Comprá acá: {link_afiliado}\n\n"
        f"Canal de ofertas: {LINK_CANAL_WHATSAPP}"
    )

    print(mensaje)
    enviar_a_whatsapp(mensaje)
