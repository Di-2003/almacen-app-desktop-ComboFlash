"""
Gestión de locales: Almacén + tiendas. Y la vista virtual 'General'.

'General' NO se guarda en la tabla `locales`. Es una vista agregada
que el código calcula. Se representa con GENERAL_ID = -1.
"""
from datetime import datetime
from db import get_conn, GENERAL_ID, get_pref, set_pref


NOMBRE_GENERAL = "General"


# ================= consultas =================

def listar_locales(solo_activos: bool = True) -> list[dict]:
    sql = "SELECT * FROM locales"
    if solo_activos:
        sql += " WHERE activo=1"
    sql += " ORDER BY es_almacen DESC, nombre COLLATE NOCASE"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def obtener_local(local_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM locales WHERE id=?", (local_id,)
        ).fetchone()
        return dict(row) if row else None


def obtener_almacen() -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM locales WHERE es_almacen=1 AND activo=1"
        ).fetchone()
        return dict(row) if row else None


def listar_tiendas(solo_activas: bool = True) -> list[dict]:
    """Locales activos que NO son Almacén."""
    sql = "SELECT * FROM locales WHERE es_almacen=0"
    if solo_activas:
        sql += " AND activo=1"
    sql += " ORDER BY nombre COLLATE NOCASE"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def es_general(local_id) -> bool:
    return local_id == GENERAL_ID


def es_almacen(local_id) -> bool:
    if es_general(local_id):
        return False
    loc = obtener_local(local_id)
    return bool(loc and loc["es_almacen"])


# ================= creación / cierre =================

def abrir_tienda(nombre: str) -> int:
    """
    Crea una tienda nueva. Devuelve el id.
    No permite nombres reservados ('General', 'Almacén') ni duplicados.
    """
    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre de la tienda no puede estar vacío")
    if nombre.lower() in ("general", "almacén", "almacen"):
        raise ValueError(f"'{nombre}' es un nombre reservado")
    if len(nombre) < 2:
        raise ValueError("El nombre debe tener al menos 2 caracteres")

    with get_conn() as conn:
        existe = conn.execute(
            "SELECT 1 FROM locales WHERE nombre=? COLLATE NOCASE",
            (nombre,),
        ).fetchone()
        if existe:
            raise ValueError(f"Ya existe un local llamado '{nombre}'")

        cur = conn.execute(
            "INSERT INTO locales(nombre,es_almacen,activo,creado) "
            "VALUES(?,0,1,?)",
            (nombre, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        return cur.lastrowid


def cerrar_tienda(local_id: int, usuario: str) -> None:
    """
    Cierra una tienda: TODOS sus productos se traspasan al Almacén y el
    local queda inactivo (los movimientos históricos se conservan).
    No se puede cerrar el Almacén.

    Además, los productos que quedaban con stock 0 en el local se
    marcan como inactivos para que el resumen no los cuente.
    """
    loc = obtener_local(local_id)
    if loc is None:
        raise ValueError("Local no encontrado")
    if loc["es_almacen"]:
        raise ValueError("No se puede cerrar el Almacén")

    almacen = obtener_almacen()
    if almacen is None:
        raise ValueError("No existe el Almacén (¡problema de integridad!)")

    # Import aquí para evitar ciclo
    from inventario import _traspasar_producto_interno

    with get_conn() as conn:
        productos = conn.execute(
            "SELECT * FROM productos WHERE local_id=? AND activo=1 "
            "AND stock > 0",
            (local_id,),
        ).fetchall()

    fecha = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for p in productos:
        _traspasar_producto_interno(
            nombre_o_codigo=p["nombre"],
            cantidad=float(p["stock"]),
            local_origen_id=local_id,
            local_destino_id=almacen["id"],
            usuario=usuario,
            fecha=fecha,
            motivo_cierre=True,
        )

    with get_conn() as conn:
        # FIX: inactivar cualquier producto que quede en el local
        # (incluye los que tenían stock 0 y no se traspasaron).
        conn.execute(
            "UPDATE productos SET activo=0, fecha_ultima_mod=? "
            "WHERE local_id=? AND activo=1",
            (fecha, local_id),
        )
        conn.execute(
            "UPDATE locales SET activo=0 WHERE id=?", (local_id,)
        )


def renombrar_local(local_id: int, nuevo_nombre: str) -> None:
    nuevo_nombre = (nuevo_nombre or "").strip()
    if not nuevo_nombre:
        raise ValueError("El nombre no puede estar vacío")
    loc = obtener_local(local_id)
    if loc is None:
        raise ValueError("Local no encontrado")
    if loc["es_almacen"]:
        raise ValueError("No se puede renombrar el Almacén")
    if nuevo_nombre.lower() in ("general", "almacén", "almacen"):
        raise ValueError(f"'{nuevo_nombre}' es un nombre reservado")

    with get_conn() as conn:
        existe = conn.execute(
            "SELECT 1 FROM locales WHERE nombre=? COLLATE NOCASE AND id<>?",
            (nuevo_nombre, local_id),
        ).fetchone()
        if existe:
            raise ValueError(f"Ya existe un local llamado '{nuevo_nombre}'")
        conn.execute(
            "UPDATE locales SET nombre=? WHERE id=?",
            (nuevo_nombre, local_id),
        )


# ================= preferencia: local actual por usuario =================

def _clave_pref(username: str) -> str:
    return f"local_actual:{username.lower()}"


def get_local_actual(username: str) -> int:
    """
    Devuelve el local_id que el usuario tenía seleccionado.
    Si no hay, o el local ya no existe, cae a Almacén. Nunca devuelve
    GENERAL_ID por defecto.
    """
    raw = get_pref(_clave_pref(username))
    if raw is None:
        almacen = obtener_almacen()
        return almacen["id"] if almacen else GENERAL_ID
    try:
        val = int(raw)
    except ValueError:
        almacen = obtener_almacen()
        return almacen["id"] if almacen else GENERAL_ID

    if val == GENERAL_ID:
        return GENERAL_ID
    if obtener_local(val) is None:
        almacen = obtener_almacen()
        return almacen["id"] if almacen else GENERAL_ID
    return val


def set_local_actual(username: str, local_id: int) -> None:
    set_pref(_clave_pref(username), str(local_id))


# ================= helpers de presentación =================

def nombre_local(local_id) -> str:
    if es_general(local_id):
        return NOMBRE_GENERAL
    loc = obtener_local(local_id)
    return loc["nombre"] if loc else "¿?"


def listar_para_menu() -> list[tuple[int, str]]:
    """
    Lista ordenada para el menú 'Cambiar de local':
        [(GENERAL_ID, 'General'), (almacen_id, 'Almacén'),
        (t1_id, 'Tienda1'), ...]
    """
    items: list[tuple[int, str]] = [(GENERAL_ID, NOMBRE_GENERAL)]
    for loc in listar_locales(solo_activos=True):
        items.append((loc["id"], loc["nombre"]))
    return items