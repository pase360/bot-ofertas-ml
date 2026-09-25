import json
from datetime import datetime, timezone
from pathlib import Path


ARCHIVO_APRENDIZAJE = Path("aprendizaje_productos.json")
ARCHIVO_CANDIDATOS = Path("productos_demandados.json")


def cargar_json(ruta, defecto):
    if not ruta.exists():
        return defecto

    try:
        return json.loads(
            ruta.read_text(
                encoding="utf-8",
                errors="ignore",
            )
        )
    except Exception:
        return defecto


def cargar_aprendizaje():
    return cargar_json(
        ARCHIVO_APRENDIZAJE,
        {
            "actualizado": None,
            "productos": {},
            "categorias": {},
        },
    )


def cargar_candidatos():
    datos = cargar_json(
        ARCHIVO_CANDIDATOS,
        {"productos": []},
    )

    return datos.get("productos", [])


def numero(valor):
    try:
        return float(valor or 0)
    except (TypeError, ValueError):
        return 0.0


def calcular_rendimiento(datos):
    """
    El rendimiento aprendido se calculará con datos REALES.

    Por ahora, si todavía no existen clics o ventas,
    el puntaje aprendido queda en cero.
    """

    publicaciones = numero(
        datos.get("publicaciones")
    )

    clics = numero(
        datos.get("clics")
    )

    ventas = numero(
        datos.get("ventas")
    )

    comision = numero(
        datos.get("comision_total")
    )

    if publicaciones <= 0:
        return 0.0

    # Tasa de clic por publicación.
    tasa_click = clics / publicaciones

    # Conversión de clic a venta.
    if clics > 0:
        conversion = ventas / clics
    else:
        conversion = 0

    # Puntaje inicial de aprendizaje.
    #
    # No inventamos resultados:
    # solamente pesa cuando existan datos reales.
    puntaje = (
        min(tasa_click, 100) * 0.30
        + min(conversion * 100, 100) * 0.40
        + min(comision / 1000, 100) * 0.30
    )

    return round(puntaje, 2)


def asegurar_producto(
    aprendizaje,
    producto,
):
    item_id = producto.get("item_id")

    if not item_id:
        return None

    productos = aprendizaje.setdefault(
        "productos",
        {},
    )

    if item_id not in productos:
        productos[item_id] = {
            "titulo": producto.get(
                "titulo",
                "",
            ),
            "publicaciones": 0,
            "clics": 0,
            "ventas": 0,
            "comision_total": 0.0,
            "puntaje_aprendido": 0.0,
            "ultima_publicacion": None,
            "ultima_actualizacion": None,
        }

    return productos[item_id]


def registrar_candidatos(
    aprendizaje,
    candidatos,
):
    nuevos = 0

    for producto in candidatos:
        item_id = producto.get("item_id")

        if not item_id:
            continue

        antes = item_id in aprendizaje.get(
            "productos",
            {},
        )

        asegurar_producto(
            aprendizaje,
            producto,
        )

        if not antes:
            nuevos += 1

    return nuevos


def recalcular(aprendizaje):
    for datos in aprendizaje.get(
        "productos",
        {},
    ).values():

        datos["puntaje_aprendido"] = (
            calcular_rendimiento(datos)
        )


def guardar(aprendizaje):
    aprendizaje["actualizado"] = (
        datetime.now(
            timezone.utc
        ).isoformat()
    )

    ARCHIVO_APRENDIZAJE.write_text(
        json.dumps(
            aprendizaje,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def mostrar_resumen(aprendizaje):
    productos = aprendizaje.get(
        "productos",
        {},
    )

    con_datos = 0
    total_clics = 0
    total_ventas = 0
    total_comision = 0.0

    for datos in productos.values():
        clics = numero(
            datos.get("clics")
        )

        ventas = numero(
            datos.get("ventas")
        )

        comision = numero(
            datos.get("comision_total")
        )

        if clics > 0 or ventas > 0:
            con_datos += 1

        total_clics += clics
        total_ventas += ventas
        total_comision += comision

    print()
    print("=== APRENDIZAJE DE PRODUCTOS ===")
    print("Productos conocidos:", len(productos))
    print(
        "Productos con datos reales:",
        con_datos,
    )
    print("Clics registrados:", int(total_clics))
    print("Ventas registradas:", int(total_ventas))
    print(
        "Comisión registrada:",
        round(total_comision, 2),
    )

    if con_datos == 0:
        print()
        print(
            "APRENDIZAJE TODAVIA INACTIVO:"
        )
        print(
            "faltan clics/ventas reales para aprender."
        )


def main():
    print(
        "=== MOTOR DE APRENDIZAJE ==="
    )

    aprendizaje = cargar_aprendizaje()
    candidatos = cargar_candidatos()

    nuevos = registrar_candidatos(
        aprendizaje,
        candidatos,
    )

    recalcular(aprendizaje)
    guardar(aprendizaje)

    print(
        "Candidatos recibidos:",
        len(candidatos),
    )

    print(
        "Productos nuevos incorporados:",
        nuevos,
    )

    mostrar_resumen(aprendizaje)

    print()
    print(
        "Archivo generado:",
        ARCHIVO_APRENDIZAJE,
    )

    print(
        "=== MOTOR FINALIZADO ==="
    )


if __name__ == "__main__":
    main()
