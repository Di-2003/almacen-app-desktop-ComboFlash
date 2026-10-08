"""
Sesiones de caja opcionales.
- Varias sesiones por día por usuario.
- Cuadre: saldo inicial + Σpagos + Σabonos - Σgastos de la sesión.
- Cierre: compara con conteo físico y calcula diferencia.
"""
from datetime import datetime
from db import get_conn


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def sesion_abierta(local_id, usuario=None) -> dict | None:
    sql = "SELECT * FROM caja_sesiones WHERE local_id=? AND cerrada IS NULL"
    params = [local_id]
    if usuario:
        sql += " AND usuario=?"
        params.append(usuario)
    sql += " ORDER BY id DESC LIMIT 1"
    with get_conn() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
        return dict(row) if row else None


def abrir_sesion(local_id, usuario, saldo_inicial=0.0,
                 notas=None) -> int:
    if sesion_abierta(local_id, usuario):
        raise ValueError("Ya tienes una sesión abierta en este local")
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO caja_sesiones(local_id,usuario,abierta,"
            "saldo_inicial,notas_apertura) VALUES(?,?,?,?,?)",
            (local_id, usuario, _ahora(),
             float(saldo_inicial or 0),
             (notas or "").strip() or None)
        )
        return cur.lastrowid


def calcular_saldo_sistema(sesion_id) -> float:
    """Saldo esperado = inicial + pagos + abonos - gastos de la sesión."""
    with get_conn() as conn:
        s = conn.execute(
            "SELECT * FROM caja_sesiones WHERE id=?", (sesion_id,)
        ).fetchone()
        if s is None:
            raise ValueError("Sesión no encontrada")
        fin = s["cerrada"] or "9999-12-31 23:59:59"
        pagos = conn.execute(
            "SELECT COALESCE(SUM(p.monto_cup),0) AS t FROM pagos p "
            "JOIN ordenes_venta o ON o.id=p.orden_id "
            "WHERE o.local_id=? AND p.fecha >= ? AND p.fecha <= ?",
            (s["local_id"], s["abierta"], fin)
        ).fetchone()
        abonos = conn.execute(
            "SELECT COALESCE(SUM(a.monto_cup),0) AS t FROM abonos a "
            "JOIN ordenes_venta o ON o.id=a.orden_id "
            "WHERE o.local_id=? AND a.fecha >= ? AND a.fecha <= ?",
            (s["local_id"], s["abierta"], fin)
        ).fetchone()
        # v10: gastos asociados a esta sesión de caja
        gastos_sesion = conn.execute(
            "SELECT COALESCE(SUM(monto_cup),0) AS t FROM gastos "
            "WHERE caja_sesion_id=?",
            (sesion_id,)
        ).fetchone()
    return (float(s["saldo_inicial"] or 0)
            + float(pagos["t"] or 0)
            + float(abonos["t"] or 0)
            - float(gastos_sesion["t"] or 0))


def cerrar_sesion(sesion_id, saldo_final, notas=None) -> dict:
    with get_conn() as conn:
        s = conn.execute(
            "SELECT * FROM caja_sesiones WHERE id=?", (sesion_id,)
        ).fetchone()
        if s is None:
            raise ValueError("Sesión no encontrada")
        if s["cerrada"]:
            raise ValueError("Esta sesión ya está cerrada")
    saldo_sis = calcular_saldo_sistema(sesion_id)
    dif = float(saldo_final or 0) - saldo_sis
    with get_conn() as conn:
        conn.execute(
            "UPDATE caja_sesiones SET cerrada=?, saldo_final=?, "
            "saldo_sistema=?, diferencia=?, notas_cierre=? WHERE id=?",
            (_ahora(), float(saldo_final or 0), saldo_sis, dif,
             (notas or "").strip() or None, sesion_id)
        )
    return {"saldo_sistema": saldo_sis, "diferencia": dif,
            "saldo_final": float(saldo_final or 0)}


def listar_sesiones(local_id, limite: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM caja_sesiones WHERE local_id=? "
            "ORDER BY abierta DESC LIMIT ?", (local_id, limite)
        ).fetchall()
        return [dict(r) for r in rows]


def resumen_sesion(sesion_id) -> dict:
    with get_conn() as conn:
        s = conn.execute(
            "SELECT * FROM caja_sesiones WHERE id=?", (sesion_id,)
        ).fetchone()
        if s is None:
            return {}
        fin = s["cerrada"] or "9999-12-31 23:59:59"
        por_metodo = conn.execute(
            "SELECT p.metodo, p.moneda, SUM(p.monto) AS monto, "
            "SUM(p.monto_cup) AS monto_cup, COUNT(*) AS n "
            "FROM pagos p JOIN ordenes_venta o ON o.id=p.orden_id "
            "WHERE o.local_id=? AND p.fecha >= ? AND p.fecha <= ? "
            "GROUP BY p.metodo, p.moneda ORDER BY p.metodo",
            (s["local_id"], s["abierta"], fin)
        ).fetchall()
        por_metodo_ab = conn.execute(
            "SELECT a.metodo, a.moneda, SUM(a.monto) AS monto, "
            "SUM(a.monto_cup) AS monto_cup, COUNT(*) AS n "
            "FROM abonos a JOIN ordenes_venta o ON o.id=a.orden_id "
            "WHERE o.local_id=? AND a.fecha >= ? AND a.fecha <= ? "
            "GROUP BY a.metodo, a.moneda ORDER BY a.metodo",
            (s["local_id"], s["abierta"], fin)
        ).fetchall()
        gastos_ses = conn.execute(
            "SELECT COALESCE(SUM(monto_cup),0) AS t FROM gastos "
            "WHERE caja_sesion_id=?",
            (sesion_id,)
        ).fetchone()
    return {
        "sesion": dict(s),
        "por_metodo": [dict(r) for r in por_metodo],
        "por_metodo_abonos": [dict(r) for r in por_metodo_ab],
        "gastos_sesion": float(gastos_ses["t"] or 0),
    }