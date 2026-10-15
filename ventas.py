"""
Lógica del POS.

Regla de cobro:
  · Efectivo (cualquier moneda): admite cualquier exceso → vuelto.
  · No-efectivo y Fiado: el exceso sobre el saldo no puede superar
    el equivalente a 1 unidad de la divisa (ej. 1 USD = 770 CUP).
    Esto permite el sobrante por redondeo al alza sin permitir
    errores de digitación grandes.
  · El vuelto se registra en `ordenes_venta.vuelto_cup` y el cajero
    lo entrega físicamente en CUP.
"""
from datetime import datetime
from db import get_conn, GENERAL_ID, MONEDAS_VALIDAS
import inventario as inv
from clientes import obtener_cliente


_MOTIVO_VENTA_POS = "Combos"


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _username(usuario) -> str:
    if isinstance(usuario, dict):
        return str(usuario.get("username", ""))
    return str(usuario)


def nuevo_carrito() -> dict:
    return {
        "items": [],
        "cliente_id": None,
        "descuento_global_pct": 0.0,
        "notas": "",
    }


def agregar_item(carrito, producto, cantidad=1) -> None:
    cantidad = float(cantidad)
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que 0")

    stock_disponible = float(producto.get("stock") or 0)

    for it in carrito["items"]:
        if it["producto_id"] == producto["id"]:
            nueva = float(it["cantidad"]) + cantidad
            if nueva > stock_disponible + 0.001:
                raise ValueError(
                    f"Solo hay {inv.fmt_cantidad(stock_disponible)} "
                    f"disponibles de «{producto['nombre']}»")
            it["cantidad"] = nueva
            return

    if cantidad > stock_disponible + 0.001:
        raise ValueError(
            f"Solo hay {inv.fmt_cantidad(stock_disponible)} "
            f"disponibles de «{producto['nombre']}»")

    carrito["items"].append({
        "producto_id": producto["id"],
        "nombre": producto["nombre"],
        "codigo": producto.get("codigo"),
        "cantidad": cantidad,
        "precio": float(producto["precio_unitario"] or 0),
        "rebaja": 0.0,
    })


def eliminar_item(carrito, indice) -> None:
    if 0 <= indice < len(carrito["items"]):
        carrito["items"].pop(indice)


def editar_item(carrito, indice, cantidad=None, rebaja=None) -> None:
    if not (0 <= indice < len(carrito["items"])):
        return
    it = carrito["items"][indice]

    if cantidad is not None:
        c = float(cantidad)
        if c <= 0:
            raise ValueError("Cantidad inválida")
        with get_conn() as conn:
            row = conn.execute(
                "SELECT stock FROM productos WHERE id=?",
                (it["producto_id"],)
            ).fetchone()
            if row is not None:
                stock = float(row["stock"] or 0)
                if c > stock + 0.001:
                    raise ValueError(
                        f"Solo hay {inv.fmt_cantidad(stock)} "
                        f"disponibles de «{it['nombre']}»")
        it["cantidad"] = c

    if rebaja is not None:
        r = float(rebaja)
        if r < 0:
            raise ValueError("La rebaja no puede ser negativa")
        if r > it["precio"] + 0.001:
            raise ValueError("La rebaja supera el precio")
        it["rebaja"] = r


def subtotal_item(it) -> float:
    return (float(it["precio"]) - float(it["rebaja"])) * float(it["cantidad"])


def calcular_totales(carrito) -> dict:
    subtotal = sum(subtotal_item(it) for it in carrito["items"])
    pct = float(carrito.get("descuento_global_pct") or 0)
    descuento = subtotal * (pct / 100.0)
    total = subtotal - descuento
    return {
        "subtotal": round(subtotal, 2),
        "descuento_pct": pct,
        "descuento": round(descuento, 2),
        "total": round(max(0.0, total), 2),
    }


def _distribuir_descuento(carrito, descuento_total) -> list[float]:
    subs = [subtotal_item(it) for it in carrito["items"]]
    total_sub = sum(subs)
    if total_sub <= 0 or descuento_total <= 0:
        return [0.0] * len(subs)
    return [descuento_total * (s / total_sub) for s in subs]


def _siguiente_ticket() -> str:
    anio = datetime.now().year
    clave = f"ticket_correlativo_{anio}"
    with get_conn() as conn:
        row = conn.execute(
            "SELECT valor FROM configuracion WHERE clave=?", (clave,)
        ).fetchone()
        n = int(row["valor"]) + 1 if row else 1
        conn.execute(
            "INSERT INTO configuracion(clave,valor) VALUES(?,?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
            (clave, str(n))
        )
    return f"T-{anio}-{n:04d}"


def registrar_venta(carrito, pagos, usuario, local_id,
                    fecha=None, notas=None) -> dict:
    username = _username(usuario)
    if local_id == GENERAL_ID:
        raise ValueError("No se puede vender en 'General'")
    if not carrito.get("items"):
        raise ValueError("El carrito está vacío")
    if not pagos:
        raise ValueError("Debe haber al menos un pago")
    if len(pagos) > 3:
        raise ValueError("Máximo 3 pagos por venta")

    fecha = fecha or _ahora()
    totales = calcular_totales(carrito)
    total_cup = totales["total"]
    if total_cup <= 0:
        raise ValueError("El total debe ser mayor que 0")

    with get_conn() as conn:
        for it in carrito["items"]:
            p = conn.execute(
                "SELECT * FROM productos WHERE id=?",
                (it["producto_id"],)
            ).fetchone()
            if p is None or not p["activo"]:
                raise ValueError(f"Producto inactivo: «{it['nombre']}»")
            if float(it["cantidad"]) > float(p["stock"] or 0) + 0.001:
                raise ValueError(
                    f"Stock insuficiente de «{it['nombre']}»: "
                    f"disponible {inv.fmt_cantidad(p['stock'])}, "
                    f"solicitado {inv.fmt_cantidad(it['cantidad'])}"
                )

    cliente_id = carrito.get("cliente_id")
    if cliente_id:
        c = obtener_cliente(cliente_id)
        if c is None or not c["activo"]:
            raise ValueError("Cliente no encontrado o inactivo")

    from configuracion_negocio import (
        obtener_metodo_pago, moneda_efectiva_metodo,
    )

    saldo_restante = total_cup
    pagos_proc = []
    hay_fiado = False
    total_pagado_cup = 0.0

    for p in pagos:
        metodo = (p.get("metodo") or "").strip()
        if not metodo:
            raise ValueError("Cada pago debe tener método")
        m_conf = obtener_metodo_pago(metodo)
        if m_conf is None or not m_conf["activo"]:
            raise ValueError(f"Método de pago inválido: «{metodo}»")
        mf = moneda_efectiva_metodo(m_conf)
        moneda = (p.get("moneda") or "CUP").upper()
        if mf:
            moneda = mf
        if moneda not in MONEDAS_VALIDAS:
            moneda = "CUP"
        try:
            monto = float(p.get("monto") or 0)
        except (TypeError, ValueError):
            raise ValueError("Monto de pago inválido")
        if monto <= 0:
            raise ValueError("Cada pago debe ser mayor que 0")
        tasa = p.get("tasa")
        if tasa is None:
            tasa = inv.get_tasa(moneda)
        tasa = float(tasa)
        monto_cup = monto * tasa

        es_efectivo = m_conf.get("clave") == "Efectivo"
        es_credito = bool(m_conf.get("es_credito"))

        if not es_efectivo:
            # No-efectivo y Fiado: exceso máximo de 1 unidad de divisa
            exceso = monto_cup - saldo_restante
            if exceso > tasa + 0.01:
                raise ValueError(
                    f"El monto ({monto_cup:.2f} CUP) supera el saldo "
                    f"pendiente ({saldo_restante:.2f} CUP) por más de "
                    f"1 {moneda} ({tasa:.2f} CUP). Revisa el monto."
                )

        total_pagado_cup += monto_cup
        saldo_restante -= monto_cup
        if saldo_restante < 0:
            saldo_restante = 0.0

        if es_credito:
            hay_fiado = True

        pagos_proc.append({
            "metodo": metodo,
            "moneda": moneda,
            "monto": monto,
            "tasa": tasa,
            "monto_cup": monto_cup,
            "es_efectivo": es_efectivo,
            "es_credito": es_credito,
        })

    if hay_fiado and not cliente_id:
        raise ValueError(
            "Una venta con «Fiado» requiere un cliente asociado")

    if not hay_fiado:
        if total_pagado_cup + 0.01 < total_cup:
            raise ValueError(
                f"Los pagos ({total_pagado_cup:.2f} CUP) no cubren "
                f"el total ({total_cup:.2f} CUP)"
            )

    vuelto_cup = max(0.0, total_pagado_cup - total_cup)

    if hay_fiado:
        saldo_pendiente = max(0.0, total_cup - total_pagado_cup)
        if saldo_pendiente <= 0.01:
            saldo_pendiente = 0.0
            estado = "pagada"
        elif total_pagado_cup > 0.01:
            estado = "parcial"
        else:
            estado = "pendiente"
    else:
        saldo_pendiente = 0.0
        estado = "pagada"

    descuentos_item = _distribuir_descuento(carrito, totales["descuento"])
    numero_ticket = _siguiente_ticket()

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO ordenes_venta(local_id,cliente_id,"
            "numero_ticket,fecha,subtotal,descuento_global,total,"
            "vuelto_cup,estado,saldo_pendiente,usuario,notas) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
            (local_id, cliente_id, numero_ticket, fecha,
             totales["subtotal"], totales["descuento"], total_cup,
             vuelto_cup, estado, saldo_pendiente, username,
             (notas or "").strip() or None)
        )
        orden_id = cur.lastrowid

        for i, it in enumerate(carrito["items"]):
            sub = subtotal_item(it)
            desc_extra = descuentos_item[i]
            rebaja_total_unit = float(it["rebaja"]) + (
                desc_extra / float(it["cantidad"])
                if it["cantidad"] else 0.0
            )
            if rebaja_total_unit > float(it["precio"]) + 0.001:
                raise ValueError(
                    f"El descuento supera el precio de «{it['nombre']}»")
            importe = round(
                (float(it["precio"]) - rebaja_total_unit)
                * float(it["cantidad"]), 2)

            conn.execute(
                "INSERT INTO orden_items(orden_id,producto_id,nombre,"
                "codigo,cantidad,precio_unitario,rebaja,importe) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (orden_id, it["producto_id"], it["nombre"],
                 it.get("codigo"), it["cantidad"], it["precio"],
                 rebaja_total_unit, importe)
            )

            prod = conn.execute(
                "SELECT * FROM productos WHERE id=?",
                (it["producto_id"],)
            ).fetchone()
            nuevo_stock = float(prod["stock"] or 0) - float(it["cantidad"])
            if nuevo_stock < -0.001:
                raise ValueError(
                    f"Stock insuficiente de «{it['nombre']}»")
            conn.execute(
                "UPDATE productos SET stock=?, fecha_ultima_mod=? "
                "WHERE id=?",
                (nuevo_stock, fecha, it["producto_id"])
            )
            conn.execute(
                "INSERT INTO movimientos(local_id,producto_id,tipo,"
                "cantidad,motivo,detalle,rebaja,"
                "precio_unitario_momento,precio_costo_momento,"
                "fecha,usuario) "
                "VALUES(?,?,'SALIDA',?,?,?,?,?,?,?,?)",
                (local_id, it["producto_id"], it["cantidad"],
                 _MOTIVO_VENTA_POS, f"Ticket {numero_ticket}",
                 rebaja_total_unit, float(it["precio"]),
                 float(prod["precio_costo"] or 0), fecha, username)
            )

        for p in pagos_proc:
            conn.execute(
                "INSERT INTO pagos(orden_id,metodo,moneda,monto,tasa,"
                "monto_cup,fecha,usuario) VALUES(?,?,?,?,?,?,?,?)",
                (orden_id, p["metodo"], p["moneda"], p["monto"],
                 p["tasa"], p["monto_cup"], fecha, username)
            )

    inv.invalidar_cache()
    return {
        "orden_id": orden_id,
        "numero_ticket": numero_ticket,
        "total": total_cup,
        "vuelto": vuelto_cup,
        "saldo_pendiente": saldo_pendiente,
        "estado": estado,
        "fecha": fecha,
    }


def obtener_orden(orden_id) -> dict | None:
    with get_conn() as conn:
        o = conn.execute(
            "SELECT o.*, c.nombre AS cliente_nombre, "
            "l.nombre AS local_nombre "
            "FROM ordenes_venta o "
            "LEFT JOIN clientes c ON c.id=o.cliente_id "
            "JOIN locales l ON l.id=o.local_id "
            "WHERE o.id=?", (orden_id,)
        ).fetchone()
        if o is None:
            return None
        o = dict(o)
        o["items"] = [dict(r) for r in conn.execute(
            "SELECT * FROM orden_items WHERE orden_id=? ORDER BY id",
            (orden_id,)
        ).fetchall()]
        o["pagos"] = [dict(r) for r in conn.execute(
            "SELECT * FROM pagos WHERE orden_id=? ORDER BY id",
            (orden_id,)
        ).fetchall()]
        o["abonos"] = [dict(r) for r in conn.execute(
            "SELECT * FROM abonos WHERE orden_id=? ORDER BY fecha",
            (orden_id,)
        ).fetchall()]
        return o


def listar_ordenes(local_id=None, desde=None, hasta=None,
                estado=None, texto=None, limite=100) -> list[dict]:
    sql = ("SELECT o.*, c.nombre AS cliente_nombre "
        "FROM ordenes_venta o "
        "LEFT JOIN clientes c ON c.id=o.cliente_id WHERE 1=1")
    params = []
    if local_id is not None and local_id != GENERAL_ID:
        sql += " AND o.local_id=?"
        params.append(local_id)
    if desde:
        sql += " AND o.fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND o.fecha <= ?"
        params.append(hasta)
    if estado:
        sql += " AND o.estado=?"
        params.append(estado)
    if texto:
        t = f"%{texto}%"
        sql += " AND (o.numero_ticket LIKE ? OR c.nombre LIKE ?)"
        params += [t, t]
    sql += " ORDER BY o.fecha DESC LIMIT ?"
    params.append(limite)
    with get_conn() as conn:
        return [dict(r) for r in
                conn.execute(sql, tuple(params)).fetchall()]


def anular_orden(orden_id, usuario) -> None:
    username = _username(usuario)
    with get_conn() as conn:
        o = conn.execute(
            "SELECT * FROM ordenes_venta WHERE id=?", (orden_id,)
        ).fetchone()
        if o is None:
            raise ValueError("Orden no encontrada")
        if o["estado"] == "anulada":
            raise ValueError("Esta orden ya está anulada")
        items = conn.execute(
            "SELECT * FROM orden_items WHERE orden_id=?", (orden_id,)
        ).fetchall()
        fecha = _ahora()
        for it in items:
            if it["producto_id"] is None:
                continue
            ya_devuelto = conn.execute(
                "SELECT COALESCE(SUM(cantidad),0) AS c "
                "FROM devoluciones WHERE item_id=?",
                (it["id"],)
            ).fetchone()["c"]
            pendiente = float(it["cantidad"] or 0) - float(ya_devuelto or 0)
            if pendiente <= 0.001:
                continue
            conn.execute(
                "UPDATE productos SET stock=stock+?, fecha_ultima_mod=? "
                "WHERE id=?",
                (pendiente, fecha, it["producto_id"])
            )
            conn.execute(
                "INSERT INTO movimientos(local_id,producto_id,tipo,"
                "cantidad,motivo,detalle,fecha,usuario) "
                "VALUES(?,?,'ENTRADA',?,?,?,?,?)",
                (o["local_id"], it["producto_id"], pendiente,
                 "Anulación", f"Ticket {o['numero_ticket']}",
                 fecha, username)
            )
        conn.execute(
            "UPDATE ordenes_venta SET estado='anulada', "
            "saldo_pendiente=0 WHERE id=?", (orden_id,)
        )
    inv.invalidar_cache()


def totales_periodo(local_id, desde, hasta) -> dict:
    filtro = ""
    params = [desde, hasta]
    if local_id is not None and local_id != GENERAL_ID:
        filtro = " AND local_id=?"
        params.append(local_id)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS n, COALESCE(SUM(total),0) AS total "
            f"FROM ordenes_venta WHERE fecha >= ? AND fecha < ?{filtro} "
            "AND estado <> 'anulada'",
            tuple(params)
        ).fetchone()
    return {"n": int(row["n"] or 0), "total": float(row["total"] or 0)}


def _calcular_pagado(conn, orden_id) -> float:
    p = conn.execute(
        "SELECT COALESCE(SUM(p.monto_cup),0) AS t FROM pagos p "
        "JOIN metodos_pago m ON m.clave=p.metodo "
        "WHERE p.orden_id=? AND m.es_credito=0", (orden_id,)
    ).fetchone()["t"]
    a = conn.execute(
        "SELECT COALESCE(SUM(monto_cup),0) AS t FROM abonos "
        "WHERE orden_id=?", (orden_id,)
    ).fetchone()["t"]
    return float(p or 0) + float(a or 0)


def _sincronizar_pago_fiado(conn, orden_id, saldo_nuevo):
    pago_fiado = conn.execute(
        "SELECT p.* FROM pagos p "
        "JOIN metodos_pago m ON m.clave=p.metodo "
        "WHERE p.orden_id=? AND m.es_credito=1 LIMIT 1",
        (orden_id,)
    ).fetchone()
    if pago_fiado is None:
        return
    if saldo_nuevo < 0.01:
        conn.execute("DELETE FROM pagos WHERE id=?",
                     (pago_fiado["id"],))
    else:
        tasa = float(pago_fiado["tasa"] or 1.0)
        nuevo_monto_orig = (round(saldo_nuevo / tasa, 4)
                            if tasa > 0 else saldo_nuevo)
        conn.execute(
            "UPDATE pagos SET monto=?, monto_cup=? WHERE id=?",
            (nuevo_monto_orig, saldo_nuevo, pago_fiado["id"])
        )


def _recalcular_estado_orden(conn, orden_id):
    o = conn.execute(
        "SELECT * FROM ordenes_venta WHERE id=?", (orden_id,)
    ).fetchone()
    if o is None or o["estado"] in ("anulada", "devuelta"):
        return

    cobrado = _calcular_pagado(conn, orden_id)
    total = float(o["total"] or 0)
    saldo = max(0.0, total - cobrado)
    vuelto = max(0.0, cobrado - total)

    _sincronizar_pago_fiado(conn, orden_id, saldo)

    if cobrado <= 0.01:
        estado = "pendiente"
    elif saldo <= 0.01:
        estado = "pagada"
    else:
        estado = "parcial"

    conn.execute(
        "UPDATE ordenes_venta SET saldo_pendiente=?, estado=?, "
        "vuelto_cup=? WHERE id=?",
        (saldo, estado, vuelto, orden_id),
    )


def recalcular_orden_completa(conn, orden_id):
    o = conn.execute(
        "SELECT * FROM ordenes_venta WHERE id=?", (orden_id,)
    ).fetchone()
    if o is None or o["estado"] in ("anulada", "devuelta"):
        return

    items = conn.execute(
        "SELECT cantidad, precio_unitario, rebaja "
        "FROM orden_items WHERE orden_id=?",
        (orden_id,)
    ).fetchall()

    subtotal = 0.0
    for it in items:
        cant = float(it["cantidad"] or 0)
        pu = float(it["precio_unitario"] or 0)
        reb = float(it["rebaja"] or 0)
        subtotal += (pu - reb) * cant

    sub_orig = float(o["subtotal"] or 0)
    desc_orig = float(o["descuento_global"] or 0)
    desc_pct = (desc_orig / sub_orig * 100.0) if sub_orig > 0 else 0.0
    descuento_total = subtotal * (desc_pct / 100.0)
    total_nuevo = max(0.0, round(subtotal - descuento_total, 2))

    conn.execute(
        "UPDATE ordenes_venta SET subtotal=?, descuento_global=?, "
        "total=? WHERE id=?",
        (round(subtotal, 2), round(descuento_total, 2),
         total_nuevo, orden_id)
    )

    _recalcular_estado_orden(conn, orden_id)


def editar_items_orden(orden_id, items_nuevos, usuario, fecha=None):
    username = _username(usuario)
    if not items_nuevos:
        raise ValueError("La orden debe tener al menos un ítem")

    with get_conn() as conn:
        o = conn.execute(
            "SELECT * FROM ordenes_venta WHERE id=?", (orden_id,)
        ).fetchone()
        if o is None:
            raise ValueError("Orden no encontrada")
        if o["estado"] == "anulada":
            raise ValueError("No se puede editar una orden anulada")
        if o["estado"] == "devuelta":
            raise ValueError("No se puede editar una orden devuelta")

        fecha = fecha or o["fecha"]

        n_pagos_reales = conn.execute(
            "SELECT COUNT(*) AS n FROM pagos p "
            "JOIN metodos_pago m ON m.clave=p.metodo "
            "WHERE p.orden_id=? AND m.es_credito=0", (orden_id,)
        ).fetchone()["n"]
        n_abonos = conn.execute(
            "SELECT COUNT(*) AS n FROM abonos WHERE orden_id=?",
            (orden_id,)
        ).fetchone()["n"]
        if n_pagos_reales == 0 and n_abonos == 0:
            raise ValueError(
                "La orden no puede quedar sin pagos. "
                "Agrega al menos uno desde el botón «Pagos».")

        old_items = conn.execute(
            "SELECT * FROM orden_items WHERE orden_id=?", (orden_id,)
        ).fetchall()
        for it in old_items:
            if it["producto_id"]:
                conn.execute(
                    "UPDATE productos SET stock=stock+?, "
                    "fecha_ultima_mod=? WHERE id=?",
                    (it["cantidad"], fecha, it["producto_id"]))

        conn.execute(
            "DELETE FROM movimientos WHERE tipo='SALIDA' "
            "AND LOWER(TRIM(COALESCE(motivo,''))) IN "
            "('venta','combos') "
            "AND detalle LIKE ?",
            (f"%{o['numero_ticket']}%",))
        conn.execute(
            "DELETE FROM orden_items WHERE orden_id=?", (orden_id,))

        subtotal = 0.0
        for it in items_nuevos:
            p = conn.execute(
                "SELECT * FROM productos WHERE id=?",
                (it["producto_id"],)
            ).fetchone()
            if p is None or not p["activo"]:
                raise ValueError(f"Producto inválido: {it['nombre']}")
            if float(it["cantidad"]) > float(p["stock"] or 0) + 0.001:
                raise ValueError(
                    f"Stock insuficiente de «{it['nombre']}»: "
                    f"disponible {inv.fmt_cantidad(p['stock'])}, "
                    f"solicitado {inv.fmt_cantidad(it['cantidad'])}")
            sub = (float(it["precio_unitario"])
                   - float(it["rebaja"])) * float(it["cantidad"])
            subtotal += sub

        desc_pct = 0.0
        if float(o["subtotal"] or 0) > 0:
            desc_pct = (float(o["descuento_global"] or 0)
                        / float(o["subtotal"])) * 100.0
        descuento_total = subtotal * (desc_pct / 100.0)
        total_nuevo = round(subtotal - descuento_total, 2)

        pagos_no_efectivo_no_credito = conn.execute(
            "SELECT COALESCE(SUM(p.monto_cup),0) AS t FROM pagos p "
            "JOIN metodos_pago m ON m.clave=p.metodo "
            "WHERE p.orden_id=? AND m.es_credito=0 "
            "AND p.metodo <> 'Efectivo'",
            (orden_id,)
        ).fetchone()["t"]
        abonos_suma = conn.execute(
            "SELECT COALESCE(SUM(monto_cup),0) AS t FROM abonos "
            "WHERE orden_id=?", (orden_id,)
        ).fetchone()["t"]
        pagos_efectivo = conn.execute(
            "SELECT COALESCE(SUM(p.monto_cup),0) AS t FROM pagos p "
            "JOIN metodos_pago m ON m.clave=p.metodo "
            "WHERE p.orden_id=? AND m.es_credito=0 "
            "AND p.metodo = 'Efectivo'",
            (orden_id,)
        ).fetchone()["t"]

        pagos_sin_vuelto = (float(pagos_no_efectivo_no_credito or 0)
                            + float(abonos_suma or 0))
        if pagos_sin_vuelto > total_nuevo + 0.01:
            raise ValueError(
                f"Los pagos no-efectivo + abonos "
                f"({pagos_sin_vuelto:.2f} CUP) superan el nuevo "
                f"total ({total_nuevo:.2f} CUP). Ajusta los pagos "
                f"antes de modificar los items.")

        cobrado_total = (float(pagos_no_efectivo_no_credito or 0)
                         + float(pagos_efectivo or 0)
                         + float(abonos_suma or 0))

        if cobrado_total >= total_nuevo - 0.01:
            nuevo_saldo = 0.0
            nuevo_estado = "pagada"
        elif cobrado_total > 0.01:
            nuevo_saldo = round(total_nuevo - cobrado_total, 2)
            nuevo_estado = "parcial"
        else:
            nuevo_saldo = total_nuevo
            nuevo_estado = "pendiente"

        total_subs_base = sum(
            (float(it["precio_unitario"]) - float(it["rebaja"]))
            * float(it["cantidad"]) for it in items_nuevos)

        for it in items_nuevos:
            sub_base = ((float(it["precio_unitario"])
                         - float(it["rebaja"]))
                        * float(it["cantidad"]))
            desc_extra_total = (descuento_total * (sub_base / total_subs_base)
                                if total_subs_base > 0 else 0.0)
            rebaja_final = (float(it["rebaja"])
                            + (desc_extra_total / float(it["cantidad"])
                               if it["cantidad"] else 0.0))
            if rebaja_final > float(it["precio_unitario"]) + 0.001:
                raise ValueError(
                    f"El descuento supera el precio de «{it['nombre']}»")
            importe = round(
                (float(it["precio_unitario"]) - rebaja_final)
                * float(it["cantidad"]), 2)

            conn.execute(
                "INSERT INTO orden_items(orden_id,producto_id,nombre,"
                "codigo,cantidad,precio_unitario,rebaja,importe) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (orden_id, it["producto_id"], it["nombre"],
                 it.get("codigo"), it["cantidad"],
                 it["precio_unitario"], rebaja_final, importe))

            p = conn.execute(
                "SELECT * FROM productos WHERE id=?",
                (it["producto_id"],)
            ).fetchone()
            conn.execute(
                "UPDATE productos SET stock=stock-?, "
                "fecha_ultima_mod=? WHERE id=?",
                (it["cantidad"], fecha, it["producto_id"]))

            conn.execute(
                "INSERT INTO movimientos(local_id,producto_id,tipo,"
                "cantidad,motivo,detalle,rebaja,"
                "precio_unitario_momento,precio_costo_momento,"
                "fecha,usuario) "
                "VALUES(?,?,'SALIDA',?,?,?,?,?,?,?,?)",
                (o["local_id"], it["producto_id"], it["cantidad"],
                 _MOTIVO_VENTA_POS, f"Ticket {o['numero_ticket']}",
                 rebaja_final, float(it["precio_unitario"]),
                 float(p["precio_costo"] or 0), fecha, username))

        conn.execute(
            "UPDATE ordenes_venta SET subtotal=?, descuento_global=?, "
            "total=?, saldo_pendiente=?, estado=? WHERE id=?",
            (round(subtotal, 2), round(descuento_total, 2),
             total_nuevo, nuevo_saldo, nuevo_estado, orden_id))

        _sincronizar_pago_fiado(conn, orden_id, nuevo_saldo)

    inv.invalidar_cache()
    return {
        "total": total_nuevo,
        "estado": nuevo_estado,
        "saldo_pendiente": nuevo_saldo,
    }


def editar_pago(pago_id, nuevo_metodo, nueva_moneda=None,
                usuario=None):
    from configuracion_negocio import (
        obtener_metodo_pago, moneda_efectiva_metodo,
    )
    m = obtener_metodo_pago(nuevo_metodo)
    if m is None or not m["activo"]:
        raise ValueError(f"Método de pago inválido: «{nuevo_metodo}»")

    with get_conn() as conn:
        p = conn.execute(
            "SELECT * FROM pagos WHERE id=?", (pago_id,)
        ).fetchone()
        if p is None:
            raise ValueError("Pago no encontrado")
        o = conn.execute(
            "SELECT * FROM ordenes_venta WHERE id=?", (p["orden_id"],)
        ).fetchone()
        if o is None:
            raise ValueError("Orden no encontrada")
        if o["estado"] == "anulada":
            raise ValueError("No se puede editar una orden anulada")

        monto_cup_actual = float(p["monto_cup"] or 0)

        moneda_fija = moneda_efectiva_metodo(m)
        if moneda_fija:
            moneda = moneda_fija
        elif nueva_moneda:
            moneda = (nueva_moneda or "CUP").upper()
            if moneda not in MONEDAS_VALIDAS:
                moneda = "CUP"
        else:
            moneda = (p["moneda"] or "CUP").upper()

        t_nueva = inv.get_tasa(moneda)
        if t_nueva <= 0:
            raise ValueError("La tasa de cambio es inválida")
        monto = round(monto_cup_actual / t_nueva, 6)
        if monto <= 0:
            raise ValueError("El monto resultante es 0")

        tasa_final = monto_cup_actual / monto if monto else 1.0

        conn.execute(
            "UPDATE pagos SET metodo=?, moneda=?, monto=?, tasa=?, "
            "monto_cup=? WHERE id=?",
            (nuevo_metodo, moneda, monto, tasa_final,
             monto_cup_actual, pago_id),
        )

    return {
        "metodo": nuevo_metodo,
        "moneda": moneda,
        "monto": monto,
        "tasa": tasa_final,
        "monto_cup": monto_cup_actual,
    }


def agregar_pago_a_orden(orden_id, metodo, moneda, monto, usuario):
    from configuracion_negocio import (
        obtener_metodo_pago, moneda_efectiva_metodo,
    )
    m = obtener_metodo_pago(metodo)
    if m is None or not m["activo"]:
        raise ValueError(f"Método de pago inválido: «{metodo}»")

    mf = moneda_efectiva_metodo(m)
    if mf:
        moneda = mf

    moneda = (moneda or "CUP").upper()
    if moneda not in MONEDAS_VALIDAS:
        moneda = "CUP"

    monto = float(monto)
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que 0")

    with get_conn() as conn:
        o = conn.execute(
            "SELECT * FROM ordenes_venta WHERE id=?", (orden_id,)
        ).fetchone()
        if o is None:
            raise ValueError("Orden no encontrada")
        if o["estado"] == "anulada":
            raise ValueError("No se puede editar una orden anulada")
        if o["estado"] == "devuelta":
            raise ValueError("No se puede editar una orden devuelta")

        existe = conn.execute(
            "SELECT 1 FROM pagos WHERE orden_id=? AND metodo=?",
            (orden_id, metodo)
        ).fetchone()
        if existe:
            raise ValueError(
                f"Ya existe un pago con «{metodo}» en esta orden. "
                f"Edita o elimina el existente antes de agregar otro.")

        pagado = _calcular_pagado(conn, orden_id)
        total = float(o["total"] or 0)
        saldo = max(0.0, total - pagado)

        tasa = inv.get_tasa(moneda)
        monto_cup = monto * tasa

        es_credito = bool(m.get("es_credito"))
        es_efectivo = m.get("clave") == "Efectivo"

        if not es_efectivo:
            exceso = monto_cup - saldo
            if exceso > tasa + 0.01:
                raise ValueError(
                    f"El monto ({monto_cup:.2f} CUP) supera el saldo "
                    f"({saldo:.2f} CUP) por más de 1 {moneda} "
                    f"({tasa:.2f} CUP). Revisa el monto."
                )

        cur = conn.execute(
            "INSERT INTO pagos(orden_id,metodo,moneda,monto,tasa,"
            "monto_cup,fecha,usuario) VALUES(?,?,?,?,?,?,?,?)",
            (orden_id, metodo, moneda, monto, tasa, monto_cup,
             _ahora(),
             _username(usuario) if usuario else ""),
        )
        pago_id = cur.lastrowid

        _recalcular_estado_orden(conn, orden_id)

    inv.invalidar_cache()
    return pago_id


def eliminar_pago(pago_id, usuario):
    with get_conn() as conn:
        p = conn.execute(
            "SELECT * FROM pagos WHERE id=?", (pago_id,)
        ).fetchone()
        if p is None:
            raise ValueError("Pago no encontrado")
        o = conn.execute(
            "SELECT * FROM ordenes_venta WHERE id=?", (p["orden_id"],)
        ).fetchone()
        if o is None:
            raise ValueError("Orden no encontrada")
        if o["estado"] == "anulada":
            raise ValueError("No se puede editar una orden anulada")

        conn.execute("DELETE FROM pagos WHERE id=?", (pago_id,))
        _recalcular_estado_orden(conn, p["orden_id"])

    inv.invalidar_cache()


def cambiar_metodo_pago(pago_id, nuevo_metodo, usuario):
    return editar_pago(pago_id=pago_id, nuevo_metodo=nuevo_metodo,
                       usuario=usuario)


def set_cliente_orden(orden_id, cliente_id, usuario=None):
    with get_conn() as conn:
        o = conn.execute(
            "SELECT * FROM ordenes_venta WHERE id=?", (orden_id,)
        ).fetchone()
        if o is None:
            raise ValueError("Orden no encontrada")
        if o["estado"] == "anulada":
            raise ValueError("No se puede editar una orden anulada")
        if o["estado"] == "devuelta":
            raise ValueError("No se puede editar una orden devuelta")
        if cliente_id is not None:
            c = conn.execute(
                "SELECT 1 FROM clientes WHERE id=? AND activo=1",
                (cliente_id,)
            ).fetchone()
            if c is None:
                raise ValueError("Cliente no encontrado o inactivo")
        conn.execute(
            "UPDATE ordenes_venta SET cliente_id=? WHERE id=?",
            (cliente_id, orden_id)
        )