"""
Lógica del POS: carrito, venta, descuentos, pagos, ticket.
Carrito vive en memoria (app._carrito_pos) hasta confirmar.
"""
from datetime import datetime
from db import get_conn, GENERAL_ID, MONEDAS_VALIDAS
import inventario as inv
from clientes import obtener_cliente


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _username(usuario) -> str:
    if isinstance(usuario, dict):
        return str(usuario.get("username", ""))
    return str(usuario)


# ── Carrito (puro Python, no toca BD) ──

def nuevo_carrito() -> dict:
    return {
        "items": [],
        "cliente_id": None,
        "descuento_global_pct": 0.0,
        "notas": "",
    }


def agregar_item(carrito, producto, cantidad=1) -> None:
    """Agrega o suma cantidad de un producto al carrito.
    Valida contra el stock disponible ANTES de agregar."""
    cantidad = float(cantidad)
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que 0")

    stock_disponible = float(producto.get("stock") or 0)

    # Si ya está en el carrito, sumar
    for it in carrito["items"]:
        if it["producto_id"] == producto["id"]:
            nueva = float(it["cantidad"]) + cantidad
            if nueva > stock_disponible + 0.001:
                raise ValueError(
                    f"Solo hay {inv.fmt_cantidad(stock_disponible)} "
                    f"disponibles de «{producto['nombre']}»")
            it["cantidad"] = nueva
            return

    # Nuevo ítem
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
    """Edita cantidad y/o rebaja de un ítem del carrito.
    Valida stock contra la BD antes de aceptar la nueva cantidad."""
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
    """Descuento adicional por ítem, proporcional a su subtotal."""
    subs = [subtotal_item(it) for it in carrito["items"]]
    total_sub = sum(subs)
    if total_sub <= 0 or descuento_total <= 0:
        return [0.0] * len(subs)
    return [descuento_total * (s / total_sub) for s in subs]


# ── Correlativo ──

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


# ── Venta definitiva ──

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

    # Validar stock (por si acaso cambió desde que se agregó al carrito)
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

    # Cliente
    cliente_id = carrito.get("cliente_id")
    if cliente_id:
        c = obtener_cliente(cliente_id)
        if c is None or not c["activo"]:
            raise ValueError("Cliente no encontrado o inactivo")

    # Procesar pagos
    from configuracion_negocio import obtener_metodo_pago
    total_pagado_cup = 0.0
    pagos_proc = []
    hay_fiado = False
    pagos_no_fiado_cup = 0.0
    for p in pagos:
        metodo = (p.get("metodo") or "").strip()
        if not metodo:
            raise ValueError("Cada pago debe tener método")
        m_conf = obtener_metodo_pago(metodo)
        if m_conf is None or not m_conf["activo"]:
            raise ValueError(f"Método de pago inválido: «{metodo}»")
        moneda = (p.get("moneda") or "CUP").upper()
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
        total_pagado_cup += monto_cup
        if m_conf.get("es_credito"):
            hay_fiado = True
        else:
            pagos_no_fiado_cup += monto_cup
        pagos_proc.append({
            "metodo": metodo, "moneda": moneda, "monto": monto,
            "tasa": tasa, "monto_cup": monto_cup,
        })

    if total_pagado_cup + 0.01 < total_cup:
        raise ValueError(
            f"Los pagos ({total_pagado_cup:.2f} CUP) no cubren el "
            f"total ({total_cup:.2f} CUP)"
        )

    vuelto_cup = max(0.0, total_pagado_cup - total_cup)

    if hay_fiado and not cliente_id:
        raise ValueError(
            "Una venta con «Fiado» requiere un cliente asociado")

    # Estado y saldo
    if hay_fiado:
        saldo_pendiente = max(0.0, total_cup - pagos_no_fiado_cup)
        if saldo_pendiente <= 0.01:
            estado = "pagada"
        elif pagos_no_fiado_cup > 0.01:
            estado = "parcial"
        else:
            estado = "pendiente"
    else:
        saldo_pendiente = 0.0
        estado = "pagada"

    # Descuentos por ítem (proporcional)
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
                 "Venta", f"Ticket {numero_ticket}",
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


# ── Consultas ──

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
    """Anula una orden completa: restaura stock, marca como anulada."""
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
            conn.execute(
                "UPDATE productos SET stock=stock+?, fecha_ultima_mod=? "
                "WHERE id=?",
                (it["cantidad"], fecha, it["producto_id"])
            )
            conn.execute(
                "INSERT INTO movimientos(local_id,producto_id,tipo,"
                "cantidad,motivo,detalle,fecha,usuario) "
                "VALUES(?,?,'ENTRADA',?,?,?,?,?)",
                (o["local_id"], it["producto_id"], it["cantidad"],
                 "Anulación", f"Ticket {o['numero_ticket']}",
                 fecha, username)
            )
        conn.execute(
            "UPDATE ordenes_venta SET estado='anulada', "
            "saldo_pendiente=0 WHERE id=?", (orden_id,)
        )
    inv.invalidar_cache()


# ── Estadísticas rápidas ──

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

def editar_items_orden(orden_id, items_nuevos, usuario, fecha=None):
    """
    Reemplaza los items de una orden existente.
    items_nuevos: [{"producto_id", "nombre", "codigo", "cantidad",
                    "precio_unitario", "rebaja"}]
    Recalcula total, saldo y stock. Mantiene pagos y abonos ya hechos.
    """
    username = _username(usuario)
    fecha = fecha or _ahora()
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

        # 1. Revertir stock de items viejos
        old_items = conn.execute(
            "SELECT * FROM orden_items WHERE orden_id=?", (orden_id,)
        ).fetchall()
        for it in old_items:
            if it["producto_id"]:
                conn.execute(
                    "UPDATE productos SET stock=stock+?, "
                    "fecha_ultima_mod=? WHERE id=?",
                    (it["cantidad"], fecha, it["producto_id"]))

        # 2. Borrar movimientos de la venta y items viejos
        conn.execute(
            "DELETE FROM movimientos WHERE tipo='SALIDA' "
            "AND motivo='Venta' AND detalle=?",
            (f"Ticket {o['numero_ticket']}",))
        conn.execute(
            "DELETE FROM orden_items WHERE orden_id=?", (orden_id,))

        # 3. Validar stock y calcular subtotal nuevo
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

        # Preservar el % de descuento global de la orden original
        desc_pct = 0.0
        if float(o["subtotal"] or 0) > 0:
            desc_pct = (float(o["descuento_global"] or 0)
                        / float(o["subtotal"])) * 100.0
        descuento_total = subtotal * (desc_pct / 100.0)
        total_nuevo = round(subtotal - descuento_total, 2)

        # 4. Recalcular pagado real y saldo
        pagos_sum = conn.execute(
            "SELECT COALESCE(SUM(monto_cup),0) AS t FROM pagos "
            "WHERE orden_id=?", (orden_id,)
        ).fetchone()["t"]
        abonos_sum = conn.execute(
            "SELECT COALESCE(SUM(monto_cup),0) AS t FROM abonos "
            "WHERE orden_id=?", (orden_id,)
        ).fetchone()["t"]
        pagado_real = float(pagos_sum or 0) + float(abonos_sum or 0)

        if pagado_real >= total_nuevo - 0.01:
            nuevo_saldo = 0.0
            nuevo_estado = "pagada"
        elif pagado_real > 0.01:
            nuevo_saldo = round(total_nuevo - pagado_real, 2)
            nuevo_estado = "parcial"
        else:
            nuevo_saldo = total_nuevo
            nuevo_estado = "pendiente"

        # 5. Crear items nuevos + ajustar stock + movimientos
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
                 "Venta", f"Ticket {o['numero_ticket']}",
                 rebaja_final, float(it["precio_unitario"]),
                 float(p["precio_costo"] or 0), fecha, username))

        # 6. Actualizar cabecera
        conn.execute(
            "UPDATE ordenes_venta SET subtotal=?, descuento_global=?, "
            "total=?, saldo_pendiente=?, estado=? WHERE id=?",
            (round(subtotal, 2), round(descuento_total, 2),
             total_nuevo, nuevo_saldo, nuevo_estado, orden_id))

    inv.invalidar_cache()
    return {
        "total": total_nuevo,
        "estado": nuevo_estado,
        "saldo_pendiente": nuevo_saldo,
    }
    
    
