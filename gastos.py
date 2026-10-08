"""
Lógica de gastos operativos y sus categorías.
- Categorías globales, editables.
- Gastos con moneda (CUP/USD/EUR) + monto_cup histórico.
- Gastos por local o globales (local_id NULL).
- Opcionalmente asociados a una sesión de caja abierta.
"""
from datetime import datetime
from db import get_conn, MONEDAS_VALIDAS


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _norm(s):
    v = (s or "").strip()
    return v or None


def _norm_cat(nombre: str) -> str:
    n = (nombre or "").strip()
    if not n:
        return n
    return n.capitalize()


# ══════════════════════════════════════════════════════════════
# CATEGORÍAS DE GASTOS
# ══════════════════════════════════════════════════════════════

def listar_categorias_gastos(solo_activas: bool = True) -> list[dict]:
    sql = "SELECT * FROM categorias_gastos"
    if solo_activas:
        sql += " WHERE activo=1"
    sql += " ORDER BY nombre COLLATE NOCASE"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def obtener_categoria_gasto(cat_id) -> dict | None:
    if cat_id is None:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM categorias_gastos WHERE id=?", (cat_id,)
        ).fetchone()
        return dict(row) if row else None


def crear_categoria_gasto(nombre: str) -> int:
    nombre = _norm_cat(nombre)
    if not nombre:
        raise ValueError("El nombre no puede estar vacío")
    if len(nombre) < 2:
        raise ValueError("El nombre debe tener al menos 2 caracteres")
    with get_conn() as conn:
        existe = conn.execute(
            "SELECT * FROM categorias_gastos WHERE nombre=? COLLATE NOCASE",
            (nombre,)
        ).fetchone()
        if existe:
            if existe["activo"]:
                raise ValueError(f"Ya existe la categoría «{nombre}»")
            conn.execute(
                "UPDATE categorias_gastos SET activo=1 WHERE id=?",
                (existe["id"],)
            )
            return existe["id"]
        cur = conn.execute(
            "INSERT INTO categorias_gastos(nombre, activo) VALUES(?, 1)",
            (nombre,)
        )
        return cur.lastrowid


def renombrar_categoria_gasto(cat_id: int, nuevo: str) -> None:
    nuevo = _norm_cat(nuevo)
    if not nuevo:
        raise ValueError("El nombre no puede estar vacío")
    with get_conn() as conn:
        cat = conn.execute(
            "SELECT * FROM categorias_gastos WHERE id=?", (cat_id,)
        ).fetchone()
        if cat is None:
            raise ValueError("Categoría no encontrada")
        if cat["nombre"] == nuevo:
            raise ValueError("El nombre nuevo es igual al actual")
        otro = conn.execute(
            "SELECT 1 FROM categorias_gastos WHERE nombre=? COLLATE NOCASE "
            "AND id<>?",
            (nuevo, cat_id)
        ).fetchone()
        if otro:
            raise ValueError(f"Ya existe la categoría «{nuevo}»")
        conn.execute(
            "UPDATE categorias_gastos SET nombre=? WHERE id=?",
            (nuevo, cat_id)
        )


def desactivar_categoria_gasto(cat_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE categorias_gastos SET activo=0 WHERE id=?", (cat_id,)
        )


# ══════════════════════════════════════════════════════════════
# GASTOS
# ══════════════════════════════════════════════════════════════

def _username(usuario) -> str:
    if isinstance(usuario, dict):
        return str(usuario.get("username", ""))
    return str(usuario)


def registrar_gasto(monto, moneda, usuario, local_id=None,
                    categoria_id=None, metodo=None, descripcion=None,
                    fecha=None, caja_sesion_id=None) -> int:
    try:
        monto = float(monto)
    except (TypeError, ValueError):
        raise ValueError("El monto debe ser un número")
    if monto <= 0:
        raise ValueError("El monto debe ser mayor que 0")

    moneda = (moneda or "CUP").upper()
    if moneda not in MONEDAS_VALIDAS:
        moneda = "CUP"

    if categoria_id is not None:
        if obtener_categoria_gasto(categoria_id) is None:
            raise ValueError("Categoría inválida")

    from inventario import get_tasa
    tasa = get_tasa(moneda)
    monto_cup = monto * tasa

    fecha = fecha or _ahora()
    username = _username(usuario)

    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO gastos(local_id,categoria_id,monto,moneda,"
            "tasa,monto_cup,metodo,descripcion,fecha,usuario,"
            "caja_sesion_id) "
            "VALUES(?,?,?,?,?,?,?,?,?,?,?)",
            (local_id, categoria_id, monto, moneda, tasa, monto_cup,
             _norm(metodo), _norm(descripcion), fecha, username,
             caja_sesion_id)
        )
        return cur.lastrowid


def editar_gasto(gasto_id, monto=None, moneda=None, categoria_id=None,
                metodo=None, descripcion=None, fecha=None,
                local_id=None) -> None:
    with get_conn() as conn:
        g = conn.execute(
            "SELECT * FROM gastos WHERE id=?", (gasto_id,)
        ).fetchone()
        if g is None:
            raise ValueError("Gasto no encontrado")

        campos, vals = [], []

        if monto is not None:
            try:
                m = float(monto)
            except (TypeError, ValueError):
                raise ValueError("Monto inválido")
            if m <= 0:
                raise ValueError("El monto debe ser mayor que 0")
            campos.append("monto=?")
            vals.append(m)

        if moneda is not None:
            mo = (moneda or "CUP").upper()
            if mo not in MONEDAS_VALIDAS:
                mo = "CUP"
            campos.append("moneda=?")
            vals.append(mo)
        else:
            mo = (g["moneda"] or "CUP").upper()

        if categoria_id is not None:
            if (categoria_id != 0 and
                    obtener_categoria_gasto(categoria_id) is None):
                raise ValueError("Categoría inválida")
            campos.append("categoria_id=?")
            vals.append(categoria_id if categoria_id != 0 else None)

        if metodo is not None:
            campos.append("metodo=?")
            vals.append(_norm(metodo))

        if descripcion is not None:
            campos.append("descripcion=?")
            vals.append(_norm(descripcion))

        if fecha is not None:
            campos.append("fecha=?")
            vals.append(fecha)

        if local_id is not None:
            campos.append("local_id=?")
            vals.append(local_id if local_id != 0 else None)

        if "monto=?" in campos or "moneda=?" in campos:
            from inventario import get_tasa
            nuevo_monto = vals[campos.index("monto=?")] \
                if "monto=?" in campos else float(g["monto"])
            nueva_moneda = vals[campos.index("moneda=?")] \
                if "moneda=?" in campos else mo
            nueva_tasa = get_tasa(nueva_moneda)
            nuevo_cup = nuevo_monto * nueva_tasa
            campos.append("tasa=?")
            campos.append("monto_cup=?")
            vals.extend([nueva_tasa, nuevo_cup])

        if not campos:
            return

        vals.append(gasto_id)
        conn.execute(
            f"UPDATE gastos SET {', '.join(campos)} WHERE id=?",
            tuple(vals)
        )


def eliminar_gasto(gasto_id) -> None:
    with get_conn() as conn:
        existe = conn.execute(
            "SELECT 1 FROM gastos WHERE id=?", (gasto_id,)
        ).fetchone()
        if existe is None:
            raise ValueError("Gasto no encontrado")
        conn.execute("DELETE FROM gastos WHERE id=?", (gasto_id,))


def obtener_gasto(gasto_id) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT g.*, c.nombre AS categoria_nombre, "
            "l.nombre AS local_nombre "
            "FROM gastos g "
            "LEFT JOIN categorias_gastos c ON c.id=g.categoria_id "
            "LEFT JOIN locales l ON l.id=g.local_id "
            "WHERE g.id=?", (gasto_id,)
        ).fetchone()
        return dict(row) if row else None


def listar_gastos(local_id="__all__", desde=None, hasta=None,
                categoria_id="__all__", limite=200) -> list[dict]:
    sql = ("SELECT g.*, c.nombre AS categoria_nombre, "
           "l.nombre AS local_nombre FROM gastos g "
           "LEFT JOIN categorias_gastos c ON c.id=g.categoria_id "
           "LEFT JOIN locales l ON l.id=g.local_id WHERE 1=1")
    params = []

    if local_id != "__all__":
        if local_id is None:
            sql += " AND g.local_id IS NULL"
        else:
            sql += " AND g.local_id=?"
            params.append(local_id)

    if desde:
        sql += " AND g.fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND g.fecha <= ?"
        params.append(hasta)

    if categoria_id != "__all__":
        if categoria_id is None:
            sql += " AND g.categoria_id IS NULL"
        else:
            sql += " AND g.categoria_id=?"
            params.append(categoria_id)

    sql += " ORDER BY g.fecha DESC, g.id DESC LIMIT ?"
    params.append(limite)

    with get_conn() as conn:
        return [dict(r) for r in
                conn.execute(sql, tuple(params)).fetchall()]


def total_gastos_periodo(local_id="__all__", desde=None,
                        hasta=None) -> float:
    sql = "SELECT COALESCE(SUM(monto_cup),0) AS t FROM gastos WHERE 1=1"
    params = []
    if local_id != "__all__":
        if local_id is None:
            sql += " AND local_id IS NULL"
        else:
            sql += " AND local_id=?"
            params.append(local_id)
    if desde:
        sql += " AND fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND fecha <= ?"
        params.append(hasta)
    with get_conn() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
    return float(row["t"] or 0)


def gastos_por_categoria(local_id="__all__", desde=None,
                        hasta=None) -> list[dict]:
    sql = ("SELECT g.categoria_id, "
           "COALESCE(c.nombre, 'Sin categoría') AS nombre, "
           "COALESCE(SUM(g.monto_cup),0) AS total "
           "FROM gastos g "
           "LEFT JOIN categorias_gastos c ON c.id=g.categoria_id "
           "WHERE 1=1")
    params = []
    if local_id != "__all__":
        if local_id is None:
            sql += " AND g.local_id IS NULL"
        else:
            sql += " AND g.local_id=?"
            params.append(local_id)
    if desde:
        sql += " AND g.fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND g.fecha <= ?"
        params.append(hasta)
    sql += " GROUP BY g.categoria_id ORDER BY total DESC"
    with get_conn() as conn:
        return [dict(r) for r in
                conn.execute(sql, tuple(params)).fetchall()]


def gastos_por_local(desde=None, hasta=None) -> list[dict]:
    sql = ("SELECT g.local_id, "
           "COALESCE(l.nombre, 'Global') AS nombre, "
           "COALESCE(SUM(g.monto_cup),0) AS total "
           "FROM gastos g "
           "LEFT JOIN locales l ON l.id=g.local_id "
           "WHERE 1=1")
    params = []
    if desde:
        sql += " AND g.fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND g.fecha <= ?"
        params.append(hasta)
    sql += " GROUP BY g.local_id ORDER BY total DESC"
    with get_conn() as conn:
        return [dict(r) for r in
                conn.execute(sql, tuple(params)).fetchall()]