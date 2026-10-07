"""
Métricas por período calendario.
Un solo query devuelve todo lo necesario para el Dashboard.
"""
from datetime import datetime, timedelta
from db import get_conn, GENERAL_ID


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


def resumen_periodo(local_id, periodo: str) -> dict:
    """
    Devuelve TODAS las métricas del período en un solo query.
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
            AND LOWER(TRIM(COALESCE(motivo,''))) = 'venta'
            THEN (precio_unitario_momento - rebaja) * cantidad
            ELSE 0 END), 0)
            AS vendido,

        COALESCE(SUM(CASE WHEN tipo='SALIDA'
            AND LOWER(TRIM(COALESCE(motivo,''))) = 'venta'
            THEN precio_costo_momento * cantidad
            ELSE 0 END), 0)
            AS costo_vendido,

        COUNT(CASE WHEN tipo='ENTRADA' THEN 1 END) AS n_entradas,
        COALESCE(SUM(CASE WHEN tipo='ENTRADA'
            THEN cantidad ELSE 0 END), 0) AS cant_entradas,

        COUNT(CASE WHEN tipo='SALIDA'
            AND LOWER(TRIM(COALESCE(motivo,''))) = 'venta'
            THEN 1 END) AS n_ventas,
        COALESCE(SUM(CASE WHEN tipo='SALIDA'
            AND LOWER(TRIM(COALESCE(motivo,''))) = 'venta'
            THEN cantidad ELSE 0 END), 0) AS cant_ventas
    FROM movimientos
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


# ── Compatibilidad con código antiguo ──

def ingresado_periodo(local_id, desde, hasta) -> float:
    return _one_sum(local_id, desde, hasta,
                    "tipo='ENTRADA'",
                    "precio_costo_momento * cantidad")


def vendido_periodo(local_id, desde, hasta) -> float:
    return _one_sum(local_id, desde, hasta,
                    "tipo='SALIDA' AND "
                    "LOWER(TRIM(COALESCE(motivo,'')))='venta'",
                    "(precio_unitario_momento - rebaja) * cantidad")


def costo_vendido_periodo(local_id, desde, hasta) -> float:
    return _one_sum(local_id, desde, hasta,
                    "tipo='SALIDA' AND "
                    "LOWER(TRIM(COALESCE(motivo,'')))='venta'",
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
                      "tipo='SALIDA' AND "
                      "LOWER(TRIM(COALESCE(motivo,'')))='venta'")


def otras_salidas_periodo(local_id, desde, hasta) -> dict:
    return _one_count(local_id, desde, hasta,
                      "tipo='SALIDA' AND "
                      "LOWER(TRIM(COALESCE(motivo,'')))<>'venta'")


def ventas_sin_costo(local_id, desde, hasta) -> int:
    f, p = _filtro(local_id, desde, hasta)
    sql = ("SELECT COUNT(*) AS n FROM movimientos "
           "WHERE tipo='SALIDA' "
           "AND LOWER(TRIM(COALESCE(motivo,'')))='venta' "
           "AND fecha >= ? AND fecha < ? "
           "AND precio_costo_momento <= 0" + f)
    with get_conn() as conn:
        return int(conn.execute(sql, tuple(p)).fetchone()["n"] or 0)


# ── Helpers internos ──

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