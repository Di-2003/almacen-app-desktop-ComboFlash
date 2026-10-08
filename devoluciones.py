"""
Devoluciones parciales o totales, hasta 7 días.
Restaura stock y ajusta la orden.
"""
from datetime import datetime, timedelta
from db import get_conn
import inventario as inv


DIAS_LIMITE = 7


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _puede_devolver(fecha_str, usuario) -> bool:
    if isinstance(usuario, dict) and usuario.get("rol") == "admin":
        return True
    try:
        f = datetime.strptime(fecha_str, "%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return False
    return datetime.now() - f <= timedelta(days=DIAS_LIMITE)


def registrar_devolucion(orden_id, items_devueltos, motivo,
                         usuario) -> dict:
    """
    items_devueltos: [{"item_id": int, "cantidad": float}, ...]
    """
    username = (usuario["username"] if isinstance(usuario, dict)
                else str(usuario))
    if not items_devueltos:
        raise ValueError("Debes seleccionar al menos un ítem")

    with get_conn() as conn:
        orden = conn.execute(
            "SELECT * FROM ordenes_venta WHERE id=?", (orden_id,)
        ).fetchone()
        if orden is None:
            raise ValueError("Orden no encontrada")
        if orden["estado"] == "anulada":
            raise ValueError("Esta orden está anulada")

        if not _puede_devolver(orden["fecha"], usuario):
            raise ValueError(
                f"Solo se puede devolver dentro de {DIAS_LIMITE} días")

        total_devuelto = 0.0
        for it_dev in items_devueltos:
            item = conn.execute(
                "SELECT * FROM orden_items WHERE id=? AND orden_id=?",
                (it_dev["item_id"], orden_id)
            ).fetchone()
            if item is None:
                raise ValueError("Ítem no encontrado en la orden")

            ya = conn.execute(
                "SELECT COALESCE(SUM(cantidad),0) AS c "
                "FROM devoluciones WHERE item_id=?", (item["id"],)
            ).fetchone()["c"]
            disponible = float(item["cantidad"]) - float(ya)
            cant = float(it_dev["cantidad"])
            if cant <= 0:
                raise ValueError("Cantidad debe ser > 0")
            if cant > disponible + 0.001:
                raise ValueError(
                    f"Solo puedes devolver {disponible:.2f} de "
                    f"«{item['nombre']}»")

            precio_efectivo = (float(item["importe"])
                              / float(item["cantidad"]))
            monto = round(precio_efectivo * cant, 2)
            total_devuelto += monto

            if item["producto_id"] is not None:
                conn.execute(
                    "UPDATE productos SET stock=stock+?, "
                    "fecha_ultima_mod=? WHERE id=?",
                    (cant, _ahora(), item["producto_id"])
                )
                conn.execute(
                    "INSERT INTO movimientos(local_id,producto_id,tipo,"
                    "cantidad,motivo,detalle,fecha,usuario) "
                    "VALUES(?,?,'ENTRADA',?,?,?,?,?)",
                    (orden["local_id"], item["producto_id"], cant,
                     "Devolución",
                     f"Ticket {orden['numero_ticket']}",
                     _ahora(), username)
                )

            conn.execute(
                "INSERT INTO devoluciones(orden_id,item_id,producto_id,"
                "cantidad,monto_devuelto,motivo,fecha,usuario) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (orden_id, item["id"], item["producto_id"], cant,
                 monto, (motivo or "").strip() or None,
                 _ahora(), username)
            )

        nuevo_total = max(0.0, float(orden["total"]) - total_devuelto)
        nuevo_saldo = min(float(orden["saldo_pendiente"] or 0),
                          nuevo_total)
        nuevo_estado = orden["estado"]
        if nuevo_total <= 0.01:
            nuevo_estado = "devuelta"
            nuevo_saldo = 0.0
        conn.execute(
            "UPDATE ordenes_venta SET total=?, saldo_pendiente=?, "
            "estado=? WHERE id=?",
            (nuevo_total, nuevo_saldo, nuevo_estado, orden_id)
        )

    inv.invalidar_cache()
    return {
        "orden_id": orden_id,
        "total_devuelto": total_devuelto,
        "nuevo_total": nuevo_total,
        "estado": nuevo_estado,
    }


def listar_devoluciones(orden_id=None, limite=100) -> list[dict]:
    sql = ("SELECT d.*, p.nombre AS producto_nombre, "
        "o.numero_ticket FROM devoluciones d "
        "LEFT JOIN productos p ON p.id=d.producto_id "
        "JOIN ordenes_venta o ON o.id=d.orden_id")
    params = []
    if orden_id is not None:
        sql += " WHERE d.orden_id=?"
        params.append(orden_id)
    sql += " ORDER BY d.fecha DESC LIMIT ?"
    params.append(limite)
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]