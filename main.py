            raise RuntimeError(f"Producto {numero}: item repetido {item_id}.")
        if link in links:
            raise RuntimeError(f"Producto {numero}: link repetido.")
        if imagen in imagenes:
            raise RuntimeError(
                f"Producto {numero}: URL de imagen repetida dentro de la tanda. "
                "Se detiene para evitar que un producto reciba la foto de otro."
            )

        ids.add(item_id)
        links.add(link)
        imagenes.add(imagen)

    print("✅ Integridad de tanda verificada: 10 productos, links, precios e imágenes.")


def guardar_tanda(productos):
    validar_tanda_integridad(productos)
    limpiar_ofertas()

    links = []
    datos_txt = []
    imagenes = []

    for numero, datos in enumerate(productos, start=1):
        archivo = crear_imagen_oferta(datos, numero)

        links.append(datos["url_original"])

        nombre = datos["nombre"].replace("|", "-")
        precio = datos["precio"].replace("|", "-")
        cuotas = datos.get("cuotas", "").replace("|", "-")

        datos_txt.append(f"{nombre} | {precio} | {cuotas}")
        imagenes.append(f"{RAW_BASE}/{archivo}")

    Path("ultima_tanda.txt").write_text("\n".join(links), encoding="utf-8")
    Path("datos_tanda.txt").write_text("\n".join(datos_txt), encoding="utf-8")
    Path("imagenes_tanda.txt").write_text("\n".join(imagenes), encoding="utf-8")

    print("✅ ultima_tanda.txt generado")
    print("✅ datos_tanda.txt generado")
    print("✅ imagenes_tanda.txt generado")

    # Queda aparte para no cambiar el circuito actual de Automate.
    crear_imagen_promo_canal()


# =========================================================
# COLA URGENTE PARA AUTOMATE
# =========================================================

def guardar_urgentes(productos):
    """
    Genera archivos separados para demanda detectada. No pisa la tanda normal.
    El detector puede disparar este workflow en cuanto agregue demanda_detectada.txt;
    Automate podrá vigilar estos archivos y publicar cada urgente inmediatamente.
    """
    if not productos:
        return

    links, datos_txt, imagenes = [], [], []
    for numero, datos in enumerate(productos, start=1):
        archivo = crear_imagen_oferta(datos, 1000 + numero)
        links.append(datos["url_original"])
        nombre = datos["nombre"].replace("|", "-")
        precio = datos["precio"].replace("|", "-")
        cuotas = datos.get("cuotas", "").replace("|", "-")
        datos_txt.append(f"{nombre} | {precio} | {cuotas}")
        imagenes.append(f"{RAW_BASE}/{archivo}")

    Path("urgente_links.txt").write_text("\n".join(links), encoding="utf-8")
    Path("urgente_datos.txt").write_text("\n".join(datos_txt), encoding="utf-8")
    Path("urgente_imagenes.txt").write_text("\n".join(imagenes), encoding="utf-8")
    print("🚨 Cola urgente generada:", len(productos), "producto(s) nuevos")


# =========================================================
# MAIN
# =========================================================

def main():
    # 1) DEMANDA URGENTE: si existe, se prepara aparte y sin repetidos.
    urgentes, lineas_resueltas = obtener_productos_demanda(maximo=50)
    if urgentes:
        guardar_urgentes(urgentes)
        guardar_historial_publicados(urgentes)
        _marcar_demanda_procesada(lineas_resueltas)

    # 2) TANDA NORMAL: siempre 10 NUEVOS; nunca completa con repetidos.
    productos = obtener_productos_base()
    if len(productos) != CANTIDAD_PRODUCTOS:
        raise RuntimeError(
            f"La tanda normal debe tener {CANTIDAD_PRODUCTOS} productos nuevos; "
            f"se obtuvieron {len(productos)}."
        )

    print("Productos nuevos seleccionados:", len(productos))
    guardar_tanda(productos)
    guardar_historial_publicados(productos)
    print("✅ PROCESO COMPLETO FINALIZADO SIN REPETIDOS")


if __name__ == "__main__":
    main()
