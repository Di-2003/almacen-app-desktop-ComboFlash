"""
CRUD de clientes + cuentas por cobrar + abonos parciales.
Cliente global (no por local).
"""
from datetime import datetime
from db import get_conn


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm(v):
    s = (v or "").strip()
    return s or None


# ── CRUD ──

def listar_clientes(solo_activos: bool = True,
                    texto: str | None = None) -> list[dict]:
    sql = "SELECT * FROM clientes"
    cond, params = [], []
    if solo_activos:
        cond.append("activo=1")
    if texto:
        cond.append("(nombre LIKE ? OR telefono LIKE ? OR email LIKE ?)")
        t = f"%{texto}%"
        params += [t, t, t]
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY nombre COLLATE NOCASE"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


def obtener_cliente(cid) -> dict | None:
    if cid is None:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM clientes WHERE id=?", (cid,)
        ).fetchone()
        return dict(row) if row else None


def crear_cliente(nombre, telefono=None, direccion=None, email=None,
                  limite_credito=0, notas=None) -> int:
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre no puede estar vacío")
    if len(nombre) < 2:
        raise ValueError("El nombre debe tener al menos 2 caracteres")
    with get_conn() as conn:
        existe = conn.execute(
            "SELECT 1 FROM clientes WHERE nombre=? COLLATE NOCASE",
            (nombre,)
        ).fetchone()
        if existe:
            raise ValueError(f"Ya existe un cliente «{nombre}»")
        cur = conn.execute(
            "INSERT INTO clientes(nombre,telefono,direccion,email,"
            "limite_credito,activo,creado,notas) "
            "VALUES(?,?,?,?,?,1,?,?)",
            (nombre, _norm(telefono), _norm(direccion), _norm(email),
             float(limite_credito or 0), _ahora(), _norm(notas))
        )
        return cur.lastrowid


def editar_cliente(cid, nombre=None, telefono=None, direccion=None,
                   email=None, limite_credito=None, notas=None) -> None:
    with get_conn() as conn:
        c = conn.execute(
            "SELECT * FROM clientes WHERE id=?", (cid,)
        ).fetchone()
        if c is None:
            raise ValueError("Cliente no encontrado")
        campos, vals = [], []
        if nombre is not None:
            n = (nombre or "").strip()
            if not n or len(n) < 2:
                raise ValueError("Nombre inválido")
            if n.lower() != c["nombre"].lower():
                otro = conn.execute(
                    "SELECT 1 FROM clientes WHERE nombre=? COLLATE NOCASE "
                    "AND id<>?", (n, cid)
                ).fetchone()
                if otro:
                    raise ValueError(f"Ya existe un cliente «{n}»")
            campos.append("nombre=?")
            vals.append(n)
        if telefono is not None:
            campos.append("telefono=?")
            vals.append(_norm(telefono))
        if direccion is not None:
            campos.append("direccion=?")
            vals.append(_norm(direccion))
        if email is not None:
            campos.append("email=?")
            vals.append(_norm(email))
        if limite_credito is not None:
            campos.append("limite_credito=?")
            vals.append(float(limite_credito))
        if notas is not None:
            campos.append("notas=?")
            vals.append(_norm(notas))
        if not campos:
            return
        vals.append(cid)
        conn.execute(
            f"UPDATE clientes SET {', '.join(campos)} WHERE id=?",
            tuple(vals)
        )


def activar_cliente(cid: int, activo: bool) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE clientes SET activo=? WHERE id=?",
            (1 if activo else 0, cid)
        )


# ── Cuentas por cobrar ──

def saldo_pendiente(cid) -> float:
    """Deuda total del cliente (todas las órdenes pendientes/parciales)."""
    if cid is None:
        return 0.0
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(saldo_pendiente),0) AS s "
            "FROM ordenes_venta WHERE cliente_id=? "
            "AND estado IN ('pendiente','parcial')",
            (cid,)
        ).fetchone()
        return float(row["s"] or 0.0)


def listar_con_deuda() -> list[dict]:
    """Clientes con saldo pendiente, ordenados por deuda descendente."""
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT c.*, COALESCE(SUM(o.saldo_pendiente),0) AS deuda "
            "FROM clientes c "
            "LEFT JOIN ordenes_venta o ON o.cliente_id=c.id "
            "  AND o.estado IN ('pendiente','parcial') "
            "WHERE c.activo=1 "
            "GROUP BY c.id HAVING deuda > 0 "
            "ORDER BY deuda DESC"
        ).fetchall()
        return [dict(r) for r in rows]


def historial_compras(cid, limite: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ordenes_venta WHERE cliente_id=? "
            "ORDER BY fecha DESC LIMIT ?", (cid, limite)
        ).fetchall()
        return [dict(r) for r in rows]


def listar_ordenes_pendientes(cid) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM ordenes_venta WHERE cliente_id=? "
            "AND estado IN ('pendiente','parcial') "
            "ORDER BY fecha ASC", (cid,)
        ).fetchall()
        return [dict(r) for r in rows]


# ── Abonos ──

def registrar_abono(orden_id, monto, moneda, metodo, usuario,
                    tasa=None, notas=None) -> dict:
    """
    Registra un abono parcial a una orden con saldo pendiente.
    Ajusta el saldo y el estado (parcial/pagada).
    """
    from inventario import get_tasa
    monto = float(monto)
    if monto <= 0:
        raise ValueError("El abono debe ser mayor que 0")
    moneda = (moneda or "CUP").upper()
    if tasa is None:
        tasa = get_tasa(moneda)
    tasa = float(tasa)
    monto_cup = monto * tasa
    username = (usuario["username"]
                if isinstance(usuario, dict) else str(usuario))

    with get_conn() as conn:
        o = conn.execute(
            "SELECT * FROM ordenes_venta WHERE id=?", (orden_id,)
        ).fetchone()
        if o is None:
            raise ValueError("Orden no encontrada")
        saldo = float(o["saldo_pendiente"] or 0)
        if saldo <= 0.01:
            raise ValueError("Esta orden no tiene saldo pendiente")
        if monto_cup > saldo + 0.01:
            raise ValueError(
                f"El abono ({monto_cup:.2f} CUP) supera el saldo "
                f"pendiente ({saldo:.2f} CUP)")
        conn.execute(
            "INSERT INTO abonos(orden_id,monto,moneda,tasa,monto_cup,"
            "metodo,fecha,usuario,notas) VALUES(?,?,?,?,?,?,?,?,?)",
            (orden_id, monto, moneda, tasa, monto_cup, metodo,
            _ahora(), username, _norm(notas))
        )
        nuevo_saldo = max(0.0, saldo - monto_cup)
        nuevo_estado = "pagada" if nuevo_saldo <= 0.01 else "parcial"
        conn.execute(
            "UPDATE ordenes_venta SET saldo_pendiente=?, estado=? "
            "WHERE id=?", (nuevo_saldo, nuevo_estado, orden_id)
        )
    return {"saldo": nuevo_saldo, "estado": nuevo_estado,
            "monto_cup": monto_cup}


def listar_abonos(orden_id) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM abonos WHERE orden_id=? ORDER BY fecha DESC",
            (orden_id,)
        ).fetchall()
        return [dict(r) for r in rows]