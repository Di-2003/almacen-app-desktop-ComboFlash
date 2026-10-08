"""
CRUD de proveedores + relación N:M con productos + pagos.
- Proveedor global.
- Un producto (por nombre) puede tener varios proveedores.
- Uno puede ser "principal" (opcional).
- Los pagos se registran contra el proveedor (no contra una entrada específica).
- Saldo del proveedor = Σ(entradas con proveedor) − Σ(pagos).
"""
from datetime import datetime
from db import get_conn, MONEDAS_VALIDAS


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm_telefono(t):
    v = (t or "").strip()
    return v or None


def _norm_nombre(n: str) -> str:
    """Capitaliza cada palabra: 'distribuidora el sol' → 'Distribuidora El Sol'."""
    n = (n or "").strip()
    if not n:
        return n
    return " ".join(w.capitalize() for w in n.split())


def _username(usuario) -> str:
    if isinstance(usuario, dict):
        return str(usuario.get("username", ""))
    return str(usuario)


# ══════════════════════════════════════════════════════════════
# CRUD PROVEEDORES
# ══════════════════════════════════════════════════════════════

def listar_proveedores(solo_activos: bool = True,
                       texto: str | None = None) -> list[dict]:
    sql = "SELECT * FROM proveedores"
    cond, params = [], []
    if solo_activos:
        cond.append("activo=1")
    if texto:
        cond.append("(nombre LIKE ? OR telefono LIKE ?)")
        t = f"%{texto}%"
        params += [t, t]
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY nombre COLLATE NOCASE"
    with get_conn() as conn:
        return [dict(r) for r in
                conn.execute(sql, tuple(params)).fetchall()]


def obtener_proveedor(pid) -> dict | None:
    if pid is None:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM proveedores WHERE id=?", (pid,)
        ).fetchone()
        return dict(row) if row else None


def crear_proveedor(nombre: str, telefono: str = None) -> int:
    nombre = _norm_nombre(nombre)
    if not nombre:
        raise ValueError("El nombre no puede estar vacío")
    if len(nombre) < 2:
        raise ValueError("El nombre debe tener al menos 2 caracteres")
    with get_conn() as conn:
        existe = conn.execute(
            "SELECT * FROM proveedores WHERE nombre=? COLLATE NOCASE",
            (nombre,)
        ).fetchone()
        if existe:
            if existe["activo"]:
                raise ValueError(f"Ya existe un proveedor «{nombre}»")
            conn.execute(
                "UPDATE proveedores SET activo=1 WHERE id=?",
                (existe["id"],)
            )
            return existe["id"]
        cur = conn.execute(
            "INSERT INTO proveedores(nombre,telefono,activo,creado) "
            "VALUES(?,?,1,?)",
            (nombre, _norm_telefono(telefono), _ahora())
        )
        return cur.lastrowid


def editar_proveedor(pid: int, nombre: str = None,
                     telefono: str = None) -> None:
    with get_conn() as conn:
        p = conn.execute(
            "SELECT * FROM proveedores WHERE id=?", (pid,)
        ).fetchone()
        if p is None:
            raise ValueError("Proveedor no encontrado")
        campos, vals = [], []
        if nombre is not None:
            n = _norm_nombre(nombre)
            if not n or len(n) < 2:
                raise ValueError("Nombre inválido")
            if n.lower() != p["nombre"].lower():
                otro = conn.execute(
                    "SELECT 1 FROM proveedores WHERE nombre=? "
                    "COLLATE NOCASE AND id<>?", (n, pid)
                ).fetchone()
                if otro:
                    raise ValueError(f"Ya existe un proveedor «{n}»")
            campos.append("nombre=?")
            vals.append(n)
        if telefono is not None:
            campos.append("telefono=?")
            vals.append(_norm_telefono(telefono))
        if not campos:
            return
        vals.append(pid)
        conn.execute(
            f"UPDATE proveedores SET {', '.join(campos)} WHERE id=?",
            tuple(vals)
        )


def activar_proveedor(pid: int, activo: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE proveedores SET activo=? WHERE id=?",
            (1 if activo else 0, pid)
        )


# ══════════════════════════════════════════════════════════════
# N:M producto↔proveedor
# ══════════════════════════════════════════════════════════════

def proveedores_de_producto(nombre_producto: str) -> list[dict]:
    """Devuelve lista de proveedores asociados al producto (por nombre)."""
    if not (nombre_producto or "").strip():
        return []
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.*, pp.es_principal "
            "FROM proveedores p "
            "JOIN producto_proveedores pp ON pp.proveedor_id=p.id "
            "WHERE pp.producto_nombre=? COLLATE NOCASE "
            "ORDER BY pp.es_principal DESC, p.nombre COLLATE NOCASE",
            (nombre_producto,)
        ).fetchall()
        return [dict(r) for r in rows]


def asociar_proveedor(nombre_producto: str, proveedor_id: int,
                      es_principal: int = 0) -> None:
    """Asocia un proveedor a un producto. Idempotente."""
    if not (nombre_producto or "").strip():
        raise ValueError("El nombre del producto no puede estar vacío")
    if obtener_proveedor(proveedor_id) is None:
        raise ValueError("Proveedor no encontrado")

    with get_conn() as conn:
        # Si es principal, primero desmarcar todos los demás
        if es_principal:
            conn.execute(
                "UPDATE producto_proveedores SET es_principal=0 "
                "WHERE producto_nombre=? COLLATE NOCASE",
                (nombre_producto,)
            )
        conn.execute(
            "INSERT OR IGNORE INTO producto_proveedores"
            "(producto_nombre, proveedor_id, es_principal) "
            "VALUES(?,?,?)",
            (nombre_producto, proveedor_id, 1 if es_principal else 0)
        )
        if es_principal:
            conn.execute(
                "UPDATE producto_proveedores SET es_principal=1 "
                "WHERE producto_nombre=? COLLATE NOCASE "
                "AND proveedor_id=?",
                (nombre_producto, proveedor_id)
            )


def desasociar_proveedor(nombre_producto: str,
                         proveedor_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "DELETE FROM producto_proveedores "
            "WHERE producto_nombre=? COLLATE NOCASE "
            "AND proveedor_id=?",
            (nombre_producto, proveedor_id)
        )


def set_proveedor_principal(nombre_producto: str,
                            proveedor_id: int) -> None:
    """Marca un proveedor como principal. Si proveedor_id=0, quita
    cualquier principal."""
    with get_conn() as conn:
        conn.execute(
            "UPDATE producto_proveedores SET es_principal=0 "
            "WHERE producto_nombre=? COLLATE NOCASE",
            (nombre_producto,)
        )
        if proveedor_id:
            conn.execute(
                "UPDATE producto_proveedores SET es_principal=1 "
                "WHERE producto_nombre=? COLLATE NOCASE "
                "AND proveedor_id=?",
                (nombre_producto, proveedor_id)
            )


def proveedor_principal(nombre_producto: str) -> dict | None:
    if not (nombre_producto or "").strip():
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT p.* FROM proveedores p "
            "JOIN producto_proveedores pp ON pp.proveedor_id=p.id "
            "WHERE pp.producto_nombre=? COLLATE NOCASE "
            "AND pp.es_principal=1 LIMIT 1",
            (nombre_producto,)
        ).fetchone()
        return dict(row) if row else None


def productos_de_proveedor(proveedor_id: int) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT producto_nombre FROM producto_proveedores "
            "WHERE proveedor_id=? "
            "ORDER BY producto_nombre COLLATE NOCASE",
            (proveedor_id,)
        ).fetchall()
        return [r["producto_nombre"] for r in rows]


# ══════════════════════════════════════════════════════════════
# PAGOS A PROVEEDORES
# ══════════════════════════════════════════════════════════════

def registrar_pago(proveedor_id: int, monto, moneda: str,
                   usuario, metodo: str = None,
                   notas: str = None, fecha: str = None) -> int:
    try:
        monto = float(monto)
    except (TypeError, ValueError):
        raise ValueError("El monto debe ser un número")
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que 0")

    moneda = (moneda or "CUP").upper()
    if moneda not in MONEDAS_VALIDAS:
        moneda = "CUP"

    if obtener_proveedor(proveedor_id) is None:
        raise ValueError("Proveedor no encontrado")

    from inventario import get_tasa
    tasa = get_tasa(moneda)
    monto_cup = monto * tasa
    fecha = fecha or _ahora()
    username = _username(usuario)

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO pagos_proveedor(proveedor_id,monto,moneda,"
            "tasa,monto_cup,metodo,fecha,usuario,notas) "
            "VALUES(?,?,?,?,?,?,?,?,?)",
            (proveedor_id, monto, moneda, tasa, monto_cup,
             (metodo or "").strip() or None, fecha, username,
             (notas or "").strip() or None)
        )
        return cur.lastrowid


def eliminar_pago(pago_id: int) -> None:
    with get_conn() as conn:
        existe = conn.execute(
            "SELECT 1 FROM pagos_proveedor WHERE id=?", (pago_id,)
        ).fetchone()
        if existe is None:
            raise ValueError("Pago no encontrado")
        conn.execute(
            "DELETE FROM pagos_proveedor WHERE id=?", (pago_id,))


def listar_pagos(proveedor_id: int, limite: int = 100) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM pagos_proveedor WHERE proveedor_id=? "
            "ORDER BY fecha DESC LIMIT ?",
            (proveedor_id, limite)
        ).fetchall()
        return [dict(r) for r in rows]


def total_entradas_proveedor(proveedor_id: int) -> float:
    """Suma del costo de todas las entradas asociadas al proveedor."""
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(precio_costo_momento * cantidad),0) AS t "
            "FROM movimientos "
            "WHERE tipo='ENTRADA' AND proveedor_id=?",
            (proveedor_id,)
        ).fetchone()
    return float(row["t"] or 0)


def total_pagado_proveedor(proveedor_id: int) -> float:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(monto_cup),0) AS t "
            "FROM pagos_proveedor WHERE proveedor_id=?",
            (proveedor_id,)
        ).fetchone()
    return float(row["t"] or 0)


def saldo_proveedor(proveedor_id: int) -> float:
    """Saldo pendiente: >0 le debes, <0 te debe, 0 al día."""
    return (total_entradas_proveedor(proveedor_id)
            - total_pagado_proveedor(proveedor_id))


def listar_con_saldo() -> list[dict]:
    """Proveedores con saldo != 0, ordenados por deuda desc."""
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT p.*,
              COALESCE((
                SELECT SUM(m.precio_costo_momento * m.cantidad)
                FROM movimientos m
                WHERE m.tipo='ENTRADA' AND m.proveedor_id=p.id
              ), 0) AS total_entradas,
              COALESCE((
                SELECT SUM(pp.monto_cup)
                FROM pagos_proveedor pp
                WHERE pp.proveedor_id=p.id
              ), 0) AS total_pagado
            FROM proveedores p
            WHERE p.activo=1
            """
        ).fetchall()
    result = []
    for r in rows:
        d = dict(r)
        d["saldo"] = (float(d["total_entradas"] or 0)
                      - float(d["total_pagado"] or 0))
        if abs(d["saldo"]) > 0.01:
            result.append(d)
    result.sort(key=lambda x: -x["saldo"])
    return result