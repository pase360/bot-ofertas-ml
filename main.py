import os
import random
import time
from playwright.sync_api import sync_playwright

AFILIADO_TAG = "jlvidela"
LINK_CANAL_WHATSAPP = "https://whatsapp.com/channel/0029VbDkrupBA1f1PtP0nk0V"

OFERTAS_CATEGORIAS = [
    {
        "titulo": "Smart TVs LED en Oferta y Cuotas",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/televisores/smart-tv/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_994755-MLA74971488183_032024-O.jpg"
    },
    {
        "titulo": "Auriculares Inalámbricos Más Vendidos",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/audio/auriculares-inalambricos/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_835213-MLA53965518290_022023-O.jpg"
    },
    {
        "titulo": "Zapatillas Deportivas Primeras Marcas",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/zapatillas-deportivas/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_624893-MLA71548122910_092023-O.jpg"
    },
    {
        "titulo": "Notebooks y Laptops con Descuento",
        "precio": "Ver precios y modelos actualizados",
        "url_base": "https://listado.mercadolibre.com.ar/computacion/notebooks/_NoIndex_True",
        "imagen": "https://http2.mlstatic.com/D_NQ_NP_678241-MLA72458124503_102023-O.jpg"
    }
]

def publicar_en_canal_automatico(mensaje, imagen_url):
    print("🤖 Iniciando el navegador automático para publicar en el canal...")
    
    with sync_playwright() as p:
        user_data_dir = "./whatsapp_session"
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"]
        )
        
        page = browser.new_page()
        
        try:
            print(f"🔗 Abriendo el canal: {LINK_CANAL_WHATSAPP}")
            page.goto(LINK_CANAL_WHATSAPP, timeout=60000)
            
            # Damos tiempo a que cargue la interfaz de WhatsApp Web
            time.sleep(15)
            
            # Buscamos el cuadro de texto para escribir el mensaje en el canal
            print("✍️ Escribiendo la oferta...")
            # Selector genérico para el campo de escritura en canales/chats de WhatsApp Web
            caja_texto = page.locator('div[contenteditable="true"][data-tab="1"]')
            caja_texto.wait_for(timeout=30000)
            caja_texto.click()
            caja_texto.fill(mensaje)
            
            # Pequeña pausa para asegurar que el texto se cargó
            time.sleep(2)
            
            # Presionamos Enter para enviar
            page.keyboard.press("Enter")
            
            time.sleep(5)
            print("✅ ¡Oferta publicada en el canal con éxito!")
            
        except Exception as e:
            print(f"❌ Error en la automatización del navegador: {str(e)}")
        finally:
            browser.close()

if __name__ == "__main__":
    print("--- GENERANDO OFERTA DE CATEGORÍA ---")
    
    item = random.choice(OFERTAS_CATEGORIAS)
    titulo = item["titulo"]
    precio = item["precio"]
    
    link_afiliado = f"{item['url_base']}?tag={AFILIADO_TAG}"
    imagen_url = item["imagen"]
    
    mensaje = (
        f"🔥 *¡OFERTAS DESTACADAS EN MERCADO LIBRE!* 🔥\n\n"
        f"📦 *{titulo}*\n\n"
        f"💰 *Estado:* {precio}\n\n"
        f"🛒 *Mirá todas las opciones y comprá acá:* {link_afiliado}\n\n"
        f"📢 *Sumate al canal para más ofertas:* {LINK_CANAL_WHATSAPP}"
    )

    print(mensaje)
    publicar_en_canal_automatico(mensaje, imagen_url)
