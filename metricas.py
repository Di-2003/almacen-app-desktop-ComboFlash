"""
Métricas por período calendario.
Un solo query devuelve todo lo necesario para el Dashboard.
"""
from datetime import datetime, timedelta
from db import get_conn, GENERAL_ID


# ═══════════════════════════════════════════════════════════
# CONSTANTES COMPARTIDAS
# ═══════════════════════════════════════════════════════════
#
# En este proyecto existen DOS motivos válidos para una venta:
#
#   'Venta'  → ventas históricas (POS antiguo)
#   'Combos' → motivo actual del POS y de la salida manual
#              (configurable en configuracion.motivo_default_salida)
#
# Cualquier query que cuente ventas DEBE incluir ambos, o perderá
# movimientos. Centralizamos aquí para no repetir la lista.

VENTA_MOTIVOS = ("venta", "combos")

# Fragmento SQL reutilizable. Usa el alias `m` para la tabla movimientos.
SQL_ES_VENTA = (
    "LOWER(TRIM(COALESCE(m.motivo,''))) "
    "IN ('venta','combos')"
)

# Variante sin alias, para queries sobre `movimientos` que no usan
# alias (por ejemplo, las funciones de compatibilidad del final).
SQL_ES_VENTA_SIN_ALIAS = (
    "LOWER(TRIM(COALESCE(motivo,''))) "
    "IN ('venta','combos')"
)

# Fragmento SQL: excluye movimientos cuyo detalle apunta a una
# orden en estado 'anulada'. También requiere alias `m`.
SQL_NO_ANULADA = """
NOT EXISTS (
    SELECT 1 FROM ordenes_venta o
    WHERE o.estado = 'anulada'
      AND m.detalle = 'Ticket ' || o.numero_ticket
)
"""


def rango_calendario(periodo: str) -> tuple[str, str]:
    """
    Devuelve (desde, hasta) en formato 'YYYY-MM-DD HH:MM:SS'.
    'semana' empieza LUNES 00:00.
    """
    ahora = datetime.now()
    if periodo == "hoy":
        desde = ahora.replace(hour=0, minute=0, second=0, microsecond=0)
        hasta = desde + timedelta(days=1)
    elif periodo == "semana":
        desde = (ahora - timedelta(days=ahora.weekday())).replace(
            hour=0, minute=0, second=0, microsecond=0)
        hasta = desde + timedelta(days=7)
    elif periodo == "mes":
        desde = ahora.replace(day=1, hour=0, minute=0,
                              second=0, microsecond=0)
        if desde.month == 12:
            hasta = desde.replace(year=desde.year + 1, month=1)
        else:
            hasta = desde.replace(month=desde.month + 1)
    elif periodo == "anio":
        desde = ahora.replace(month=1, day=1, hour=0, minute=0,
                              second=0, microsecond=0)
        hasta = desde.replace(year=desde.year + 1)
    else:  # total
        return ("0000-01-01 00:00:00", "9999-12-31 23:59:59")
    return (desde.strftime("%Y-%m-%d %H:%M:%S"),
            hasta.strftime("%Y-%m-%d %H:%M:%S"))


# ═══════════════════════════════════════════════════════════
# RESUMEN DEL DASHBOARD
# ═══════════════════════════════════════════════════════════

def resumen_periodo(local_id, periodo: str) -> dict:
    """
    Devuelve TODAS las métricas del período en un solo query.

    Cuenta como venta los motivos en VENTA_MOTIVOS ('Venta' del POS
    histórico y 'Combos' del POS actual) y excluye movimientos de
    órdenes ANULADAS.
    """
    desde, hasta = rango_calendario(periodo)

    filtro = ""
    params = [desde, hasta]
    if local_id is not None and local_id != GENERAL_ID:
        filtro = " AND local_id = ?"
        params.append(local_id)

    sql = f"""
    SELECT
        COALESCE(SUM(CASE WHEN tipo='ENTRADA'
            THEN precio_costo_momento * cantidad ELSE 0 END), 0)
            AS ingresado,

        COALESCE(SUM(CASE WHEN tipo='SALIDA'
            AND {SQL_ES_VENTA} AND {SQL_NO_ANULADA}
            THEN (precio_unitario_momento - rebaja) * cantidad
            ELSE 0 END), 0)
            AS vendido,

        COALESCE(SUM(CASE WHEN tipo='SALIDA'
            AND {SQL_ES_VENTA} AND {SQL_NO_ANULADA}
            THEN precio_costo_momento * cantidad
            ELSE 0 END), 0)
            AS costo_vendido,

        COUNT(CASE WHEN tipo='ENTRADA' THEN 1 END) AS n_entradas,
        COALESCE(SUM(CASE WHEN tipo='ENTRADA'
            THEN cantidad ELSE 0 END), 0) AS cant_entradas,

        COUNT(CASE WHEN tipo='SALIDA'
            AND {SQL_ES_VENTA} AND {SQL_NO_ANULADA}
            THEN 1 END) AS n_ventas,
        COALESCE(SUM(CASE WHEN tipo='SALIDA'
            AND {SQL_ES_VENTA} AND {SQL_NO_ANULADA}
            THEN cantidad ELSE 0 END), 0) AS cant_ventas
    FROM movimientos m
    WHERE fecha >= ? AND fecha < ?{filtro}
    """

    with get_conn() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()

    ingresado = float(row["ingresado"] or 0)
    vendido = float(row["vendido"] or 0)
    costo = float(row["costo_vendido"] or 0)
    ganancia = vendido - costo
    pct = (ganancia / costo * 100) if costo > 0 else 0.0

    return {
        "ingresado": ingresado,
        "vendido": vendido,
        "costo_vendido": costo,
        "ganancia": ganancia,
        "pct_ganancia": pct,
        "n_entradas": int(row["n_entradas"] or 0),
        "cant_entradas": float(row["cant_entradas"] or 0),
        "n_ventas": int(row["n_ventas"] or 0),
        "cant_ventas": float(row["cant_ventas"] or 0),
        "desde": desde,
        "hasta": hasta,
    }


# ═══════════════════════════════════════════════════════════
# DATOS PARA GRÁFICOS Y TABLAS DEL DASHBOARD
# ═══════════════════════════════════════════════════════════

def ventas_ultimos_dias(local_id, dias: int = 30) -> list[tuple[str, float]]:
    """
    Devuelve [(fecha_yyyy_mm_dd, total_cup), ...] con TODOS los días
    del rango (rellena con 0 los días sin ventas).
    """
    hoy = datetime.now()
    desde = (hoy - timedelta(days=dias - 1)).replace(
        hour=0, minute=0, second=0, microsecond=0)
    desde_str = desde.strftime("%Y-%m-%d %H:%M:%S")

    filtro = ""
    params: list = [desde_str]
    if local_id is not None and local_id != GENERAL_ID:
        filtro = " AND local_id=?"
        params.append(local_id)

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT DATE(fecha) AS dia, "
            "COALESCE(SUM(total),0) AS total "
            "FROM ordenes_venta "
            "WHERE fecha >= ? AND estado <> 'anulada'" + filtro +
            " GROUP BY DATE(fecha) ORDER BY dia",
            tuple(params),
        ).fetchall()

    por_dia = {r["dia"]: float(r["total"]) for r in rows}
    resultado: list[tuple[str, float]] = []
    for i in range(dias):
        dia = (desde + timedelta(days=i)).strftime("%Y-%m-%d")
        resultado.append((dia, por_dia.get(dia, 0.0)))
    return resultado


def top_productos_vendidos(local_id, desde: str, hasta: str,
                            limite: int = 10) -> list[dict]:
    """
    Top N productos por CANTIDAD vendida en el período.
    Usa `orden_items` de órdenes no anuladas (POS fiel).
    """
    filtro = ""
    params: list = [desde, hasta]
    if local_id is not None and local_id != GENERAL_ID:
        filtro = " AND o.local_id=?"
        params.append(local_id)
    params.append(limite)

    sql = (
        "SELECT oi.nombre AS nombre, "
        "       SUM(oi.cantidad) AS cantidad, "
        "       SUM(oi.importe) AS total "
        "FROM orden_items oi "
        "JOIN ordenes_venta o ON o.id = oi.orden_id "
        "WHERE o.fecha >= ? AND o.fecha < ? "
        "  AND o.estado <> 'anulada'" + filtro +
        " GROUP BY oi.nombre "
        " ORDER BY cantidad DESC, total DESC "
        " LIMIT ?"
    )
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [{
        "nombre": r["nombre"],
        "cantidad": float(r["cantidad"] or 0),
        "total": float(r["total"] or 0),
    } for r in rows]


def ventas_por_metodo_pago(local_id, desde: str,
                            hasta: str) -> list[dict]:
    """
    Distribución de cobros por método de pago (en CUP).
    Suma pagos NO crédito (Fiado no es cobro) + abonos aplicados.
    """
    filtro = ""
    params: list = [desde, hasta]
    if local_id is not None and local_id != GENERAL_ID:
        filtro = " AND o.local_id=?"
        params.append(local_id)

    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.metodo AS metodo, "
            "       COALESCE(SUM(p.monto_cup),0) AS total "
            "FROM pagos p "
            "JOIN ordenes_venta o ON o.id = p.orden_id "
            "JOIN metodos_pago m ON m.clave = p.metodo "
            "WHERE o.fecha >= ? AND o.fecha < ? "
            "  AND o.estado <> 'anulada' "
            "  AND m.es_credito = 0" + filtro +
            " GROUP BY p.metodo "
            " ORDER BY total DESC",
            tuple(params),
        ).fetchall()

    return [{
        "metodo": r["metodo"],
        "total": float(r["total"] or 0),
    } for r in rows if float(r["total"] or 0) > 0.01]


def productos_estancados(local_id, dias: int = 30,
                          limite: int = 15) -> list[dict]:
    """
    Productos activos con stock > 0 que NO han tenido venta real
    en los últimos `dias`.

    Venta real = SALIDA con motivo en VENTA_MOTIVOS ('Venta' o
    'Combos') y que NO pertenezca a una orden anulada.
    """
    fecha_limite = (datetime.now() - timedelta(days=dias)).strftime(
        "%Y-%m-%d %H:%M:%S")

    filtro = ""
    if local_id is not None and local_id != GENERAL_ID:
        filtro = " AND p.local_id=?"
        params = [local_id, fecha_limite, limite]
    else:
        params = [fecha_limite, limite]

    sql = (
        "SELECT p.id, p.nombre, p.codigo, p.stock, "
        "       p.precio_unitario, p.precio_costo "
        "FROM productos p "
        "WHERE p.activo = 1 AND p.stock > 0" + filtro +
        f" AND NOT EXISTS ("
        f"   SELECT 1 FROM movimientos m "
        f"   WHERE m.producto_id = p.id "
        f"     AND m.tipo = 'SALIDA' "
        f"     AND {SQL_ES_VENTA} "
        f"     AND m.fecha >= ? "
        f"     AND {SQL_NO_ANULADA}"
        f" ) "
        "ORDER BY (p.stock * p.precio_costo) DESC "
        "LIMIT ?"
    )

    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
    return [{
        "id": r["id"],
        "nombre": r["nombre"],
        "codigo": r["codigo"],
        "stock": float(r["stock"] or 0),
        "precio_unitario": float(r["precio_unitario"] or 0),
        "precio_costo": float(r["precio_costo"] or 0),
    } for r in rows]


def productos_stock_critico(local_id, limite: int = 15) -> list[dict]:
    """
    Productos activos con stock bajo (color rojo según sus umbrales).
    El cálculo de color lo hace `inventario.color_de_producto`;
    aquí solo filtramos la lista.
    """
    import inventario as inv
    prods = inv.listar_productos(local_id, solo_activos=True)
    criticos = [p for p in prods
                if inv.color_de_producto(p) == "rojo"]
    criticos.sort(key=lambda p: (
        float(p["stock"] or 0),
        -float(p["precio_unitario"] or 0),
    ))
    return criticos[:limite]


# ═══════════════════════════════════════════════════════════
# Compatibilidad con código antiguo
# ═══════════════════════════════════════════════════════════
# FIX: todas estas funciones usaban `='venta'` y por tanto NO
# contaban las ventas nuevas con motivo 'Combos'. Ahora usan
# SQL_ES_VENTA_SIN_ALIAS.

def ingresado_periodo(local_id, desde, hasta) -> float:
    return _one_sum(local_id, desde, hasta,
                    "tipo='ENTRADA'",
                    "precio_costo_momento * cantidad")


def vendido_periodo(local_id, desde, hasta) -> float:
    return _one_sum(local_id, desde, hasta,
                    "tipo='SALIDA' AND " + SQL_ES_VENTA_SIN_ALIAS,
                    "(precio_unitario_momento - rebaja) * cantidad")


def costo_vendido_periodo(local_id, desde, hasta) -> float:
    return _one_sum(local_id, desde, hasta,
                    "tipo='SALIDA' AND " + SQL_ES_VENTA_SIN_ALIAS,
                    "precio_costo_momento * cantidad")


def ganancia_periodo(local_id, desde, hasta) -> float:
    return (vendido_periodo(local_id, desde, hasta)
            - costo_vendido_periodo(local_id, desde, hasta))


def porcentaje_ganancia_periodo(local_id, desde, hasta) -> float:
    c = costo_vendido_periodo(local_id, desde, hasta)
    if c <= 0:
        return 0.0
    return ganancia_periodo(local_id, desde, hasta) / c * 100


def entradas_periodo(local_id, desde, hasta) -> dict:
    return _one_count(local_id, desde, hasta, "tipo='ENTRADA'")


def ventas_periodo(local_id, desde, hasta) -> dict:
    return _one_count(local_id, desde, hasta,
                      "tipo='SALIDA' AND " + SQL_ES_VENTA_SIN_ALIAS)


def otras_salidas_periodo(local_id, desde, hasta) -> dict:
    return _one_count(local_id, desde, hasta,
                      "tipo='SALIDA' AND NOT ("
                      + SQL_ES_VENTA_SIN_ALIAS + ")")


def ventas_sin_costo(local_id, desde, hasta) -> int:
    f, p = _filtro(local_id, desde, hasta)
    sql = ("SELECT COUNT(*) AS n FROM movimientos "
           "WHERE tipo='SALIDA' "
           f"AND {SQL_ES_VENTA_SIN_ALIAS} "
           "AND fecha >= ? AND fecha < ? "
           "AND precio_costo_momento <= 0" + f)
    with get_conn() as conn:
        return int(conn.execute(sql, tuple(p)).fetchone()["n"] or 0)


# ═══════════════════════════════════════════════════════════
# Helpers internos
# ═══════════════════════════════════════════════════════════

def _filtro(local_id, desde, hasta):
    if local_id is None or local_id == GENERAL_ID:
        return "", [desde, hasta]
    return " AND local_id=?", [desde, hasta, local_id]


def _one_sum(local_id, desde, hasta, where, expr):
    f, p = _filtro(local_id, desde, hasta)
    sql = (f"SELECT COALESCE(SUM({expr}), 0) AS t "
           f"FROM movimientos WHERE {where} "
           f"AND fecha >= ? AND fecha < ?{f}")
    with get_conn() as conn:
        return float(conn.execute(sql, tuple(p)).fetchone()["t"] or 0)


def _one_count(local_id, desde, hasta, where):
    f, p = _filtro(local_id, desde, hasta)
    sql = (f"SELECT COUNT(*) AS n, "
        f"COALESCE(SUM(cantidad),0) AS cant "
        f"FROM movimientos WHERE {where} "
        f"AND fecha >= ? AND fecha < ?{f}")
    with get_conn() as conn:
        row = conn.execute(sql, tuple(p)).fetchone()
    return {"n": int(row["n"] or 0),
            "cantidad": float(row["cant"] or 0)}


