"""
CRUD de categorías (tipos de producto).
Los nombres se normalizan siempre a Capitalizado (primera mayúscula,
resto minúsculas). Es global a la app.
"""
from db import get_conn, GENERAL_ID


def _norm(nombre: str) -> str:
    """Normaliza: 'ELECTRÓNICA' → 'Electrónica', 'juguetes' → 'Juguetes'."""
    n = (nombre or "").strip()
    if not n:
        return n
    return n.capitalize()


def listar_categorias(solo_activas: bool = True) -> list[dict]:
    sql = "SELECT * FROM categorias"
    if solo_activas:
        sql += " WHERE activo=1"
    sql += " ORDER BY nombre COLLATE NOCASE"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def obtener_categoria(cat_id) -> dict | None:
    if cat_id is None:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM categorias WHERE id=?", (cat_id,)
        ).fetchone()
        return dict(row) if row else None


def buscar_por_nombre(nombre: str) -> dict | None:
    if not (nombre or "").strip():
        return None
    n = _norm(nombre)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM categorias WHERE nombre=? COLLATE NOCASE",
            (n,),
        ).fetchone()
        return dict(row) if row else None


def crear_categoria(nombre: str) -> int:
    nombre = _norm(nombre)
    if not nombre:
        raise ValueError("El nombre no puede estar vacío")
    if len(nombre) < 2:
        raise ValueError("El nombre debe tener al menos 2 caracteres")

    with get_conn() as conn:
        existe = conn.execute(
            "SELECT * FROM categorias WHERE nombre=? COLLATE NOCASE",
            (nombre,),
        ).fetchone()
        if existe:
            if existe["activo"]:
                raise ValueError(f"Ya existe el tipo «{nombre}»")
            conn.execute(
                "UPDATE categorias SET activo=1 WHERE id=?",
                (existe["id"],),
            )
            return existe["id"]
        cur = conn.execute(
            "INSERT INTO categorias(nombre, activo) VALUES(?, 1)",
            (nombre,),
        )
        return cur.lastrowid


def renombrar_categoria(cat_id: int, nombre_nuevo: str) -> None:
    nombre_nuevo = _norm(nombre_nuevo)
    if not nombre_nuevo:
        raise ValueError("El nombre no puede estar vacío")
    with get_conn() as conn:
        cat = conn.execute(
            "SELECT * FROM categorias WHERE id=?", (cat_id,)
        ).fetchone()
        if cat is None:
            raise ValueError("Categoría no encontrada")
        if cat["nombre"] == nombre_nuevo:
            raise ValueError("El nombre nuevo es igual al actual")
        otro = conn.execute(
            "SELECT 1 FROM categorias WHERE nombre=? COLLATE NOCASE "
            "AND id<>?",
            (nombre_nuevo, cat_id),
        ).fetchone()
        if otro:
            raise ValueError(f"Ya existe el tipo «{nombre_nuevo}»")
        conn.execute(
            "UPDATE categorias SET nombre=? WHERE id=?",
            (nombre_nuevo, cat_id),
        )


def eliminar_categoria(cat_id: int) -> None:
    with get_conn() as conn:
        conn.execute(
            "UPDATE categorias SET activo=0 WHERE id=?", (cat_id,)
        )


def contar_productos_por_categoria(local_id=None) -> dict:
    """{categoria_id (o None): n_productos_activos}"""
    sql = ("SELECT categoria_id, COUNT(*) AS n FROM productos "
           "WHERE activo=1")
    params = []
    if local_id is not None and local_id != GENERAL_ID:
        sql += " AND local_id=?"
        params.append(local_id)
    sql += " GROUP BY categoria_id"
    with get_conn() as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()
        return {r["categoria_id"]: r["n"] for r in rows}