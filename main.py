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
        # Usamos una carpeta de sesión para mantener el inicio de sesión de WhatsApp Web
        user_data_dir = "./whatsapp_session"
        browser = p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=True,
            args=["--no-sandbox", "--disable-setuid-sandbox"],
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        page = browser.new_page()
        
        try:
            print(f"🔗 Abriendo el canal: {LINK_CANAL_WHATSAPP}")
            page.goto(LINK_CANAL_WHATSAPP, timeout=60000)
            
            # Esperamos a que la interfaz cargue por completo
            print("⏳ Esperando carga de la interfaz de WhatsApp Web...")
            time.sleep(15)
            
            # Intentamos localizar la caja de texto usando múltiples selectores alternativos de WhatsApp Web
            print("✍️ Buscando el campo de escritura...")
            selectors = [
                'div[contenteditable="true"][data-tab="1"]',
                'div[contenteditable="true"]',
                'p.selectable-text'
            ]
            
            caja_texto = None
            for sel in selectors:
                try:
                    caja_texto = page.locator(sel).first
                    caja_texto.wait_for(timeout=10000)
                    if caja_texto.is_visible():
                        break
                except:
                    continue
            
            if not caja_texto or not caja_texto.is_visible():
                raise Exception("No se encontró el campo de texto visible en el canal. Puede requerir vinculación de sesión inicial.")
            
            caja_texto.click()
            # Escribimos el mensaje completo incluyendo la URL de la imagen para previsualización
            mensaje_final = f"{mensaje}\n\n📷 Imagen de referencia: {imagen_url}"
            caja_texto.fill(mensaje_final)
            
            time.sleep(2)
            print("📤 Enviando mensaje...")
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
