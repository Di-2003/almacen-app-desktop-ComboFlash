"""
Lógica de negocio del almacén. Multi-local con códigos Fxyyyy.

Reglas de color (por producto, con sus umbrales):
    🟢 Verde:    stock ≥ umbral_verde
    🟡 Amarillo: umbral_amarillo ≤ stock < umbral_verde
    🔴 Rojo:     0 ≤ stock < umbral_amarillo

ROLES:
  - admin   → todo
  - almacen → operaciones de stock (entradas, salidas, traspasos,
              precios, umbrales, códigos, renombrar, baja)
  - comun   → solo lectura

PROPAGACIÓN: los cambios de precio (costo y venta), código y nombre
se propagan a TODOS los locales donde exista el mismo producto (por
nombre). El stock, umbrales y la actividad son por-local.

CÓDIGOS: formato F[A-Z][0-9]{4}. Auto-sugeridos al crear. Únicos por
local. Se propagan a todos los locales.
"""
import re
import uuid
from datetime import datetime
from db import get_conn, GENERAL_ID
from locales import listar_locales


# ================= ROLES =================

ROL_ADMIN   = "admin"
ROL_ALMACEN = "almacen"
ROL_COMUN   = "comun"

_ROLES_OPERATIVOS  = (ROL_ADMIN, ROL_ALMACEN)
_ROLES_SOLO_ADMIN  = (ROL_ADMIN,)


def _extraer_usuario(usuario) -> tuple[str, str]:
    if isinstance(usuario, dict):
        return str(usuario.get("username", "")), str(usuario.get("rol", ""))
    return str(usuario), ""


def _autorizar(usuario, roles_permitidos: tuple[str, ...]) -> str:
    username, rol = _extraer_usuario(usuario)
    if rol not in roles_permitidos:
        permitidos = ", ".join(roles_permitidos)
        raise PermissionError(
            f"Tu rol «{rol or 'desconocido'}» no permite esta acción. "
            f"Se requiere: {permitidos}."
        )
    return username


# ================= FORMATO =================

def fmt_cantidad(n) -> str:
    if n is None:
        return ""
    n = float(n)
    if n.is_integer():
        return str(int(n))
    return f"{n:.2f}".rstrip("0").rstrip(".")


def fmt_precio(p) -> str:
    if p is None:
        return "0.00"
    return f"{float(p):.2f}"


# ================= CÓDIGOS Fxyyyy =================

LONGITUD_MAX_CODIGO = 20
_PATRON_CODIGO = re.compile(r"^F([A-Z])(\d{4})$")


def normalizar_codigo(codigo: str | None) -> str | None:
    if codigo is None:
        return None
    c = (codigo or "").strip().replace(" ", "").upper()
    if not c:
        return None
    return c[:LONGITUD_MAX_CODIGO]


def siguiente_codigo(local_id: int) -> str:
    with get_conn() as conn:
        filas = conn.execute(
            "SELECT codigo FROM productos WHERE local_id=? "
            "AND codigo IS NOT NULL",
            (local_id,),
        ).fetchall()

    max_letra = None
    max_num = 0

    for f in filas:
        c = (f["codigo"] or "").strip().upper()
        m = _PATRON_CODIGO.match(c)
        if not m:
            continue
        letra = m.group(1)
        num = int(m.group(2))
        if max_letra is None:
            max_letra, max_num = letra, num
        elif letra > max_letra:
            max_letra, max_num = letra, num
        elif letra == max_letra and num > max_num:
            max_num = num

    if max_letra is None:
        return "FA0001"

    if max_num < 9999:
        return f"F{max_letra}{max_num + 1:04d}"

    if max_letra == "Z":
        return None
    siguiente = chr(ord(max_letra) + 1)
    return f"F{siguiente}0001"


def _validar_codigo_unico(conn, local_id: int, codigo: str | None,
                          excluir_id: int | None = None) -> None:
    c = normalizar_codigo(codigo)
    if not c:
        return
    sql = ("SELECT nombre FROM productos WHERE local_id=? AND codigo=? "
           "COLLATE NOCASE")
    params: list = [local_id, c]
    if excluir_id is not None:
        sql += " AND id<>?"
        params.append(excluir_id)
    row = conn.execute(sql, tuple(params)).fetchone()
    if row:
        raise ValueError(
            f"El código «{c}» ya está en uso por «{row['nombre']}» "
            f"en este local."
        )


# ================= MOTIVOS =================

def motivo_default_salida() -> str:
    return get_config("motivo_default_salida") or "Venta"


def motivos_usados_recientes(limite: int = 15) -> list[str]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT motivo, MAX(fecha) AS ultima FROM movimientos "
            "WHERE tipo='SALIDA' AND motivo IS NOT NULL AND motivo<>'' "
            "GROUP BY motivo ORDER BY ultima DESC LIMIT ?",
            (limite,),
        ).fetchall()
        return [r["motivo"] for r in rows]


# ================= CONFIG GLOBAL =================

def get_config(clave: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT valor FROM configuracion WHERE clave=?", (clave,)
        ).fetchone()
        return row["valor"] if row else None


def set_config(clave: str, valor: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO configuracion(clave,valor) VALUES(?,?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
            (clave, str(valor)),
        )


def get_umbrales_default() -> tuple[int, int]:
    return (
        int(get_config("umbral_verde_default") or 50),
        int(get_config("umbral_amarillo_default") or 20),
    )


def get_tasa_usd() -> float:
    try:
        return float(get_config("tasa_usd") or 1.0)
    except (TypeError, ValueError):
        return 1.0


def get_tasa_eur() -> float:
    try:
        return float(get_config("tasa_eur") or 1.0)
    except (TypeError, ValueError):
        return 1.0


def get_tasa(codigo_moneda: str) -> float:
    """Devuelve la tasa de cambio a CUP para la moneda dada."""
    if codigo_moneda in ("USD", "Zelle"):
        return get_tasa_usd()
    if codigo_moneda == "EUR":
        return get_tasa_eur()
    return 1.0  # CUP


def _ahora() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# ================= COLORES =================

def color_stock(stock, uv, ua) -> str:
    if stock >= uv:
        return "verde"
    if stock >= ua:
        return "amarillo"
    return "rojo"


def color_de_producto(prod: dict) -> str:
    return color_stock(prod["stock"], prod["umbral_verde"],
                       prod["umbral_amarillo"])


def formato_rango_verde(uv: int) -> str:
    return f"stock ≥ {uv}"


def formato_rango_amarillo(ua: int, uv: int) -> str:
    return f"{ua} ≤ stock < {uv}"


def formato_rango_rojo(ua: int) -> str:
    return f"0 ≤ stock < {ua}"


def formato_regla_completa(uv: int, ua: int) -> str:
    return (f"🟢 Verde:    {formato_rango_verde(uv)}\n"
            f"🟡 Amarillo: {formato_rango_amarillo(ua, uv)}\n"
            f"🔴 Rojo:     {formato_rango_rojo(ua)}")


def texto_aplicable(prod: dict) -> str:
    c = color_de_producto(prod)
    if c == "verde":
        return formato_rango_verde(prod["umbral_verde"])
    if c == "amarillo":
        return formato_rango_amarillo(prod["umbral_amarillo"],
                                       prod["umbral_verde"])
    return formato_rango_rojo(prod["umbral_amarillo"])


# ================= CONSULTAS DE PRODUCTOS =================

def listar_productos(local_id, solo_activos: bool = True) -> list[dict]:
    if local_id == GENERAL_ID:
        return _listar_general(solo_activos)

    sql = "SELECT * FROM productos WHERE local_id=?"
    if solo_activos:
        sql += " AND activo=1"
    sql += (" ORDER BY "
            "CASE WHEN codigo IS NULL OR codigo='' THEN 1 ELSE 0 END, "
            "codigo COLLATE NOCASE, nombre COLLATE NOCASE")
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, (local_id,)).fetchall()]


def listar_productos_inactivos(local_id) -> list[dict]:
    """Devuelve SOLO los productos inactivos del local.
    En General devuelve lista vacía."""
    if local_id == GENERAL_ID:
        return []
    with get_conn() as conn:
        filas = conn.execute(
            "SELECT * FROM productos WHERE local_id=? AND activo=0 "
            "ORDER BY nombre COLLATE NOCASE",
            (local_id,),
        ).fetchall()
    return [dict(r) for r in filas]


def _listar_general(solo_activos: bool) -> list[dict]:
    locales_ids = [l["id"] for l in listar_locales(solo_activos=True)]
    if not locales_ids:
        return []
    placeholders = ",".join("?" * len(locales_ids))
    activo_sql = " AND activo=1" if solo_activos else ""
    sql = f"""
        SELECT
            MIN(codigo)                        AS codigo,
            nombre,
            SUM(stock)                         AS stock,
            SUM(stock * precio_costo)          AS _costo_total,
            SUM(stock * precio_unitario)       AS _venta_total,
            MAX(umbral_verde)                  AS umbral_verde,
            MAX(umbral_amarillo)               AS umbral_amarillo,
            MAX(fecha_ultima_mod)              AS fecha_ultima_mod
        FROM productos
        WHERE local_id IN ({placeholders}){activo_sql}
        GROUP BY nombre COLLATE NOCASE
        ORDER BY codigo COLLATE NOCASE, nombre COLLATE NOCASE
    """
    with get_conn() as conn:
        filas = conn.execute(sql, tuple(locales_ids)).fetchall()

    result = []
    for f in filas:
        d = dict(f)
        s = float(d["stock"] or 0)
        d["precio_costo"] = (d["_costo_total"] / s) if s > 0 else 0.0
        d["precio_unitario"] = (d["_venta_total"] / s) if s > 0 else 0.0
        d["id"] = None
        d["local_id"] = GENERAL_ID
        d["activo"] = 1
        result.append(d)
    return result


def buscar_producto_por_nombre(nombre: str, local_id) -> dict | None:
    if not (nombre or "").strip():
        return None
    if local_id == GENERAL_ID:
        for p in _listar_general(solo_activos=False):
            if p["nombre"].lower() == nombre.lower():
                return p
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM productos WHERE local_id=? "
            "AND nombre=? COLLATE NOCASE",
            (local_id, nombre),
        ).fetchone()
        return dict(row) if row else None


def buscar_producto_por_codigo(codigo: str, local_id) -> dict | None:
    c = normalizar_codigo(codigo)
    if not c:
        return None
    if local_id == GENERAL_ID:
        for p in _listar_general(solo_activos=False):
            if (p.get("codigo") or "").upper() == c:
                return p
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM productos WHERE local_id=? AND codigo=? "
            "COLLATE NOCASE",
            (local_id, c),
        ).fetchone()
        return dict(row) if row else None


def buscar_producto(nombre_o_codigo: str, local_id) -> dict | None:
    if not (nombre_o_codigo or "").strip():
        return None
    por_codigo = buscar_producto_por_codigo(nombre_o_codigo, local_id)
    if por_codigo is not None:
        return por_codigo
    return buscar_producto_por_nombre(nombre_o_codigo, local_id)


# ================= BÚSQUEDA GLOBAL =================

def buscar_producto_global_por_codigo(codigo: str) -> dict | None:
    c = normalizar_codigo(codigo)
    if not c:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT p.*, l.nombre AS local_nombre FROM productos p "
            "JOIN locales l ON l.id=p.local_id "
            "WHERE p.codigo=? COLLATE NOCASE "
            "ORDER BY l.es_almacen DESC LIMIT 1",
            (c,),
        ).fetchone()
        return dict(row) if row else None


def buscar_producto_global_por_nombre(nombre: str) -> dict | None:
    if not (nombre or "").strip():
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT p.*, l.nombre AS local_nombre FROM productos p "
            "JOIN locales l ON l.id=p.local_id "
            "WHERE p.nombre=? COLLATE NOCASE "
            "ORDER BY l.es_almacen DESC LIMIT 1",
            (nombre,),
        ).fetchone()
        return dict(row) if row else None


# ================= CONSULTAS DE MOVIMIENTOS =================

def listar_movimientos(local_id=None, producto_id: int | None = None,
                       limite: int = 500) -> list[dict]:
    sql = ("SELECT m.*, p.nombre AS producto, p.codigo AS codigo, "
           "       l.nombre AS local "
           "FROM movimientos m "
           "JOIN productos p ON p.id=m.producto_id "
           "JOIN locales   l ON l.id=m.local_id")
    condiciones = []
    params: list = []
    if local_id is not None and local_id != GENERAL_ID:
        condiciones.append("m.local_id=?")
        params.append(local_id)
    if producto_id is not None:
        condiciones.append("m.producto_id=?")
        params.append(producto_id)
    if condiciones:
        sql += " WHERE " + " AND ".join(condiciones)
    sql += " ORDER BY m.fecha DESC, m.id DESC LIMIT ?"
    params.append(limite)

    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql, tuple(params)).fetchall()]


# ================= EXCEPCIONES =================

class StockInsuficiente(Exception):
    def __init__(self, disponible, solicitado):
        self.disponible = disponible
        self.solicitado = solicitado
        super().__init__(
            f"Stock insuficiente: disponible="
            f"{fmt_cantidad(disponible)}, solicitado="
            f"{fmt_cantidad(solicitado)}"
        )


class ProductoNoExiste(Exception):
    pass


# ================= ENTRADAS =================

def registrar_entrada(nombre: str, cantidad, usuario, local_id: int,
                      codigo: str | None = None,
                      precio_costo: float | None = None,
                      precio_unitario: float | None = None,
                      fecha: str | None = None) -> dict:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    if local_id == GENERAL_ID:
        raise ValueError("No se puede registrar entrada en 'General'")

    nombre = (nombre or "").strip()
    if not nombre:
        raise ValueError("El nombre del producto no puede estar vacío")

    try:
        cantidad = float(cantidad)
    except (TypeError, ValueError):
        raise ValueError("La cantidad debe ser un número")
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que 0")

    codigo = normalizar_codigo(codigo)
    fecha = fecha or _ahora()
    grupo_id = uuid.uuid4().hex

    with get_conn() as conn:
        prod = conn.execute(
            "SELECT * FROM productos WHERE local_id=? "
            "AND nombre=? COLLATE NOCASE",
            (local_id, nombre),
        ).fetchone()

        if prod is None:
            _validar_codigo_unico(conn, local_id, codigo)
            color_antes = "rojo"
            uv, ua = get_umbrales_default()
            pc = float(precio_costo) if (precio_costo and
                                         precio_costo > 0) else 0.0
            pu = float(precio_unitario) if (precio_unitario and
                                            precio_unitario > 0) else 0.0
            cur = conn.execute(
                "INSERT INTO productos(local_id,codigo,nombre,stock,"
                "umbral_verde,umbral_amarillo,precio_costo,"
                "precio_unitario,fecha_ultima_mod,activo) "
                "VALUES(?,?,?,0,?,?,?,?,?,1)",
                (local_id, codigo, nombre, uv, ua, pc, pu, fecha),
            )
            pid = cur.lastrowid
        else:
            color_antes = color_de_producto(dict(prod))
            pid = prod["id"]

            codigo_actual = (prod["codigo"] or "").strip()
            if codigo and codigo != codigo_actual:
                _validar_codigo_unico(conn, local_id, codigo,
                                       excluir_id=pid)
                conn.execute(
                    "UPDATE productos SET codigo=? WHERE id=?",
                    (codigo, pid),
                )
            elif codigo and not codigo_actual:
                _validar_codigo_unico(conn, local_id, codigo,
                                       excluir_id=pid)
                conn.execute(
                    "UPDATE productos SET codigo=? WHERE id=?",
                    (codigo, pid),
                )

            if precio_costo is not None and float(precio_costo) > 0:
                conn.execute(
                    "UPDATE productos SET precio_costo=?, "
                    "fecha_ultima_mod=? WHERE id=?",
                    (float(precio_costo), fecha, pid),
                )
            if precio_unitario is not None and float(precio_unitario) > 0:
                conn.execute(
                    "UPDATE productos SET precio_unitario=?, "
                    "fecha_ultima_mod=? WHERE id=?",
                    (float(precio_unitario), fecha, pid),
                )

            # Si estaba inactivo, reactivar al recibir entrada
            if not prod["activo"]:
                conn.execute(
                    "UPDATE productos SET activo=1 WHERE id=?", (pid,)
                )

        conn.execute(
            "UPDATE productos SET stock=stock+?, fecha_ultima_mod=? "
            "WHERE id=?",
            (cantidad, fecha, pid),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "grupo_id,fecha,usuario) "
            "VALUES(?,?,'ENTRADA',?,?,?,?)",
            (local_id, pid, cantidad, grupo_id, fecha, username),
        )

        nuevo = dict(conn.execute(
            "SELECT * FROM productos WHERE id=?", (pid,)
        ).fetchone())
        color_despues = color_de_producto(nuevo)

    return {
        "color_antes": color_antes,
        "color_despues": color_despues,
        "stock": nuevo["stock"],
        "nombre": nuevo["nombre"],
    }


# ================= SALIDAS =================

def registrar_salida(nombre_o_codigo: str, cantidad, usuario,
                     local_id: int, motivo: str | None = None,
                     rebaja: float = 0.0,
                     precio_unitario_momento: float | None = None,
                     detalle: str | None = None,
                     fecha: str | None = None) -> dict:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    if local_id == GENERAL_ID:
        raise ValueError("No se puede registrar salida en 'General'")

    try:
        cantidad = float(cantidad)
    except (TypeError, ValueError):
        raise ValueError("La cantidad debe ser un número")
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que 0")

    try:
        rebaja = float(rebaja or 0)
    except (TypeError, ValueError):
        raise ValueError("La rebaja debe ser un número")
    if rebaja < 0:
        raise ValueError("La rebaja no puede ser negativa")

    motivo = (motivo or "").strip() or motivo_default_salida()
    detalle = (detalle or "").strip() or None

    fecha = fecha or _ahora()
    grupo_id = uuid.uuid4().hex

    with get_conn() as conn:
        prod = buscar_producto(nombre_o_codigo, local_id)
        if prod is None or not prod.get("activo", 1):
            raise ProductoNoExiste(
                f"Producto no encontrado o inactivo: {nombre_o_codigo}"
            )
        color_antes = color_de_producto(prod)
        if cantidad > prod["stock"]:
            raise StockInsuficiente(prod["stock"], cantidad)

        if precio_unitario_momento is None:
            pu = float(prod["precio_unitario"] or 0)
        else:
            pu = float(precio_unitario_momento)

        if rebaja > pu:
            raise ValueError(
                f"La rebaja ({fmt_precio(rebaja)}) no puede superar el "
                f"precio unitario ({fmt_precio(pu)})."
            )

        nuevo_stock = prod["stock"] - cantidad
        conn.execute(
            "UPDATE productos SET stock=?, fecha_ultima_mod=? WHERE id=?",
            (nuevo_stock, fecha, prod["id"]),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "motivo,grupo_id,detalle,rebaja,precio_unitario_momento,"
            "fecha,usuario) VALUES(?,?,'SALIDA',?,?,?,?,?,?,?,?)",
            (local_id, prod["id"], cantidad, motivo, grupo_id,
             detalle, rebaja, pu, fecha, username),
        )

        nuevo = dict(conn.execute(
            "SELECT * FROM productos WHERE id=?", (prod["id"],)
        ).fetchone())
        color_despues = color_de_producto(nuevo)

    return {
        "color_antes": color_antes,
        "color_despues": color_despues,
        "stock": nuevo["stock"],
        "nombre": nuevo["nombre"],
    }


# ================= TRASPASO =================

def registrar_traspaso(nombre_o_codigo: str, cantidad, usuario,
                       local_origen_id: int, local_destino_id: int,
                       fecha: str | None = None) -> None:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    if local_origen_id == GENERAL_ID or local_destino_id == GENERAL_ID:
        raise ValueError("No se puede traspasar desde/hacia 'General'")
    if local_origen_id == local_destino_id:
        raise ValueError("El origen y el destino deben ser distintos")

    try:
        cantidad = float(cantidad)
    except (TypeError, ValueError):
        raise ValueError("La cantidad debe ser un número")
    if cantidad <= 0:
        raise ValueError("La cantidad debe ser mayor que 0")

    fecha = fecha or _ahora()
    _traspasar_producto_interno(
        nombre_o_codigo=nombre_o_codigo,
        cantidad=cantidad,
        local_origen_id=local_origen_id,
        local_destino_id=local_destino_id,
        usuario=username,
        fecha=fecha,
    )


def _traspasar_producto_interno(nombre_o_codigo: str, cantidad: float,
                                local_origen_id: int,
                                local_destino_id: int,
                                usuario: str, fecha: str,
                                motivo_cierre: bool = False) -> None:
    grupo_id = uuid.uuid4().hex

    with get_conn() as conn:
        origen = buscar_producto(nombre_o_codigo, local_origen_id)
        if origen is None or not origen.get("activo", 1):
            raise ProductoNoExiste(
                f"Producto no encontrado en el local de origen: "
                f"{nombre_o_codigo}"
            )
        if cantidad > origen["stock"]:
            raise StockInsuficiente(origen["stock"], cantidad)

        nombre = origen["nombre"]

        conn.execute(
            "UPDATE productos SET stock=stock-?, fecha_ultima_mod=? "
            "WHERE id=?",
            (cantidad, fecha, origen["id"]),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "grupo_id,detalle,fecha,usuario) "
            "VALUES(?,?,'TRASPASO_SALIDA',?,?,?,?,?)",
            (local_origen_id, origen["id"], cantidad, grupo_id,
             "cierre de tienda" if motivo_cierre else None,
             fecha, usuario),
        )

        destino = conn.execute(
            "SELECT * FROM productos WHERE local_id=? "
            "AND nombre=? COLLATE NOCASE",
            (local_destino_id, nombre),
        ).fetchone()

        if destino is None:
            uv, ua = get_umbrales_default()
            codigo_origen = (origen["codigo"] or "").strip()
            codigo_destino = None
            if codigo_origen:
                choque = conn.execute(
                    "SELECT 1 FROM productos WHERE local_id=? "
                    "AND codigo=? COLLATE NOCASE",
                    (local_destino_id, codigo_origen),
                ).fetchone()
                if choque is None:
                    codigo_destino = codigo_origen

            cur = conn.execute(
                "INSERT INTO productos(local_id,codigo,nombre,stock,"
                "umbral_verde,umbral_amarillo,precio_costo,"
                "precio_unitario,fecha_ultima_mod,activo) "
                "VALUES(?,?,?,0,?,?,?,?,?,1)",
                (local_destino_id, codigo_destino, nombre, uv, ua,
                 origen["precio_costo"], origen["precio_unitario"], fecha),
            )
            destino_id = cur.lastrowid
        else:
            destino_id = destino["id"]

        conn.execute(
            "UPDATE productos SET stock=stock+?, fecha_ultima_mod=?, "
            "activo=1 WHERE id=?",
            (cantidad, fecha, destino_id),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "grupo_id,detalle,fecha,usuario) "
            "VALUES(?,?,'TRASPASO_ENTRADA',?,?,?,?,?)",
            (local_destino_id, destino_id, cantidad, grupo_id,
             "cierre de tienda" if motivo_cierre else None,
             fecha, usuario),
        )


# ================= UMBRALES / PRECIOS / CÓDIGO / NOMBRE =================

def cambiar_umbrales(producto_id: int, umbral_verde: int,
                     umbral_amarillo: int, usuario) -> None:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    try:
        umbral_verde = int(umbral_verde)
        umbral_amarillo = int(umbral_amarillo)
    except (TypeError, ValueError):
        raise ValueError("Los umbrales deben ser números enteros")
    if umbral_verde <= umbral_amarillo:
        raise ValueError("El umbral verde debe ser mayor que el amarillo")
    if umbral_amarillo < 0:
        raise ValueError("Los umbrales no pueden ser negativos")

    fecha = _ahora()
    detalle = f"verde={umbral_verde}, amarillo={umbral_amarillo}"
    with get_conn() as conn:
        row = conn.execute(
            "SELECT local_id FROM productos WHERE id=?", (producto_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Producto no encontrado")

        conn.execute(
            "UPDATE productos SET umbral_verde=?, umbral_amarillo=?, "
            "fecha_ultima_mod=? WHERE id=?",
            (umbral_verde, umbral_amarillo, fecha, producto_id),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'UMBRAL',0,?,?,?)",
            (row["local_id"], producto_id, detalle, fecha, username),
        )


def set_precio_costo(producto_id: int, precio: float, usuario) -> None:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    try:
        precio = float(precio)
    except (TypeError, ValueError):
        raise ValueError("El precio debe ser un número")
    if precio < 0:
        raise ValueError("El precio no puede ser negativo")

    fecha = _ahora()
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT local_id, nombre FROM productos WHERE id=?",
            (producto_id,),
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")

        conn.execute(
            "UPDATE productos SET precio_costo=?, fecha_ultima_mod=? "
            "WHERE nombre=? COLLATE NOCASE",
            (precio, fecha, prod["nombre"]),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'AJUSTE',0,?,?,?)",
            (prod["local_id"], producto_id,
             f"precio_costo={precio} (propagado)", fecha, username),
        )


def set_precio_unitario(producto_id: int, precio: float, usuario) -> None:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    try:
        precio = float(precio)
    except (TypeError, ValueError):
        raise ValueError("El precio debe ser un número")
    if precio < 0:
        raise ValueError("El precio no puede ser negativo")

    fecha = _ahora()
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT local_id, nombre FROM productos WHERE id=?",
            (producto_id,),
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")

        conn.execute(
            "UPDATE productos SET precio_unitario=?, fecha_ultima_mod=? "
            "WHERE nombre=? COLLATE NOCASE",
            (precio, fecha, prod["nombre"]),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'AJUSTE',0,?,?,?)",
            (prod["local_id"], producto_id,
             f"precio_unitario={precio} (propagado)", fecha, username),
        )


def set_codigo(producto_id: int, nuevo_codigo: str, usuario) -> None:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    with get_conn() as conn:
        prod = conn.execute(
            "SELECT local_id, nombre FROM productos WHERE id=?",
            (producto_id,),
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")

        c = normalizar_codigo(nuevo_codigo)

        if c:
            otro = conn.execute(
                "SELECT p.nombre, l.nombre AS local_nombre "
                "FROM productos p JOIN locales l ON l.id=p.local_id "
                "WHERE p.codigo=? COLLATE NOCASE "
                "AND p.nombre<>? COLLATE NOCASE",
                (c, prod["nombre"]),
            ).fetchone()
            if otro:
                raise ValueError(
                    f"El código «{c}» ya está en uso por "
                    f"«{otro['nombre']}» en «{otro['local_nombre']}»."
                )

        fecha = _ahora()
        conn.execute(
            "UPDATE productos SET codigo=?, fecha_ultima_mod=? "
            "WHERE nombre=? COLLATE NOCASE",
            (c, fecha, prod["nombre"]),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'AJUSTE',0,?,?,?)",
            (prod["local_id"], producto_id,
             f"codigo={c or '(vacío)'} (propagado)", fecha, username),
        )


def renombrar_producto(producto_id: int, nombre_nuevo: str,
                       usuario) -> None:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    nombre_nuevo = (nombre_nuevo or "").strip()
    if not nombre_nuevo:
        raise ValueError("El nuevo nombre no puede estar vacío")

    fecha = _ahora()
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT * FROM productos WHERE id=?", (producto_id,)
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")

        nombre_actual = prod["nombre"]
        if nombre_actual.lower() == nombre_nuevo.lower():
            raise ValueError("El nombre nuevo es igual al actual")

        otro = conn.execute(
            "SELECT p.nombre, l.nombre AS local_nombre "
            "FROM productos p JOIN locales l ON l.id=p.local_id "
            "WHERE p.nombre=? COLLATE NOCASE AND p.nombre<>? COLLATE NOCASE",
            (nombre_nuevo, nombre_actual),
        ).fetchone()
        if otro:
            raise ValueError(
                f"Ya existe un producto «{nombre_nuevo}» en "
                f"«{otro['local_nombre']}». Usa un nombre distinto."
            )

        conn.execute(
            "UPDATE productos SET nombre=?, fecha_ultima_mod=? "
            "WHERE nombre=? COLLATE NOCASE",
            (nombre_nuevo, fecha, nombre_actual),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'AJUSTE',0,?,?,?)",
            (prod["local_id"], producto_id,
             f"nombre: '{nombre_actual}' -> '{nombre_nuevo}' (propagado)",
             fecha, username),
        )


# ================= BAJA / REACTIVAR =================

def dar_baja(producto_id: int, usuario, motivo: str | None = None) -> None:
    username = _autorizar(usuario, _ROLES_OPERATIVOS)

    motivo = (motivo or "").strip() or "Merma"
    fecha = _ahora()
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT * FROM productos WHERE id=?", (producto_id,)
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")
        if not prod["activo"]:
            raise ValueError("El producto ya está dado de baja")

        stock_actual = float(prod["stock"] or 0)
        pu = float(prod["precio_unitario"] or 0)

        conn.execute(
            "UPDATE productos SET activo=0, fecha_ultima_mod=? WHERE id=?",
            (fecha, producto_id),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "motivo,fecha,usuario,precio_unitario_momento) "
            "VALUES(?,?,'BAJA',?,?,?,?,?)",
            (prod["local_id"], producto_id, stock_actual, motivo,
             fecha, username, pu),
        )


def reactivar_producto(producto_id: int, usuario) -> None:
    """Reactiva un producto dado de baja en el local actual."""
    username = _autorizar(usuario, _ROLES_OPERATIVOS)
    fecha = _ahora()
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT * FROM productos WHERE id=?", (producto_id,)
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")
        if prod["activo"]:
            raise ValueError("El producto ya está activo")

        conn.execute(
            "UPDATE productos SET activo=1, fecha_ultima_mod=? WHERE id=?",
            (fecha, producto_id),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'RESTAURACION',0,?,?,?)",
            (prod["local_id"], producto_id,
             "producto reactivado", fecha, username),
        )


# ================= CONSULTAS POR ESTADO =================

def productos_por_color(local_id, color: str) -> list[dict]:
    return [p for p in listar_productos(local_id, solo_activos=True)
            if color_de_producto(p) == color]


def productos_stock_cero(local_id) -> list[dict]:
    return [p for p in listar_productos(local_id, solo_activos=True)
            if float(p["stock"] or 0) == 0]


# ================= TOTALES =================

def totales_local(local_id) -> dict:
    productos = listar_productos(local_id, solo_activos=True)
    invertido = 0.0
    venta_total = 0.0
    for p in productos:
        s = float(p["stock"] or 0)
        invertido += float(p["precio_costo"] or 0) * s
        venta_total += float(p["precio_unitario"] or 0) * s
    return {
        "invertido": invertido,
        "venta_total": venta_total,
        "diferencia": venta_total - invertido,
    }


def totales_por_concepto(local_id) -> dict:
    filtro = ""
    params: list = []
    if local_id != GENERAL_ID:
        filtro = " AND local_id=?"
        params.append(local_id)

    with get_conn() as conn:
        ventas = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(cantidad),0) AS cant, "
            "COALESCE(SUM((precio_unitario_momento - rebaja) * cantidad),0) AS monto "
            "FROM movimientos "
            "WHERE tipo='SALIDA' AND LOWER(TRIM(COALESCE(motivo,'')))='venta'"
            + filtro,
            tuple(params),
        ).fetchone()

        entradas = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(cantidad),0) AS cant "
            "FROM movimientos WHERE tipo='ENTRADA'" + filtro,
            tuple(params),
        ).fetchone()

        otras_salidas = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(cantidad),0) AS cant "
            "FROM movimientos "
            "WHERE tipo='SALIDA' "
            "AND LOWER(TRIM(COALESCE(motivo,'')))<>'venta'" + filtro,
            tuple(params),
        ).fetchone()

        bajas = conn.execute(
            "SELECT COUNT(*) AS n, "
            "COALESCE(SUM(cantidad),0) AS cant "
            "FROM movimientos WHERE tipo='BAJA'" + filtro,
            tuple(params),
        ).fetchone()

    return {
        "ventas": {
            "n": int(ventas["n"] or 0),
            "cantidad": float(ventas["cant"] or 0),
            "monto": float(ventas["monto"] or 0),
        },
        "entradas": {
            "n": int(entradas["n"] or 0),
            "cantidad": float(entradas["cant"] or 0),
        },
        "otras_salidas": {
            "n": int(otras_salidas["n"] or 0),
            "cantidad": float(otras_salidas["cant"] or 0),
        },
        "bajas": {
            "n": int(bajas["n"] or 0),
            "cantidad": float(bajas["cant"] or 0),
        },
    }


# ================= ELIMINAR MOVIMIENTO =================

def _revertir_efecto_stock(conn, producto_id: int, tipo: str,
                           cantidad: float) -> None:
    if tipo == "ENTRADA":
        cambio = -float(cantidad)
    elif tipo == "SALIDA":
        cambio = float(cantidad)
    elif tipo == "TRASPASO_SALIDA":
        cambio = float(cantidad)
    elif tipo == "TRASPASO_ENTRADA":
        cambio = -float(cantidad)
    elif tipo == "BAJA":
        raise ValueError(
            "No se puede eliminar una BAJA directamente. "
            "Reactiva el producto manualmente si es necesario."
        )
    else:
        raise ValueError(f"Tipo no soportado para eliminación: {tipo}")

    prod = conn.execute(
        "SELECT stock FROM productos WHERE id=?", (producto_id,)
    ).fetchone()
    if prod is None:
        raise ValueError("Producto no encontrado para revertir stock")

    nuevo = float(prod["stock"]) + cambio
    if nuevo < 0:
        raise ValueError(
            f"El stock quedaría negativo ({nuevo:.2f}) al revertir "
            f"el movimiento. Revisa las operaciones previas."
        )
    conn.execute(
        "UPDATE productos SET stock=? WHERE id=?",
        (nuevo, producto_id),
    )


def eliminar_movimiento(mov_id: int, usuario) -> None:
    _autorizar(usuario, _ROLES_OPERATIVOS)

    with get_conn() as conn:
        mov = conn.execute(
            "SELECT * FROM movimientos WHERE id=?", (mov_id,)
        ).fetchone()
        if mov is None:
            raise ValueError("Movimiento no encontrado")

        _revertir_efecto_stock(
            conn, mov["producto_id"], mov["tipo"], float(mov["cantidad"])
        )

        if (mov["tipo"] in ("TRASPASO_SALIDA", "TRASPASO_ENTRADA")
                and mov["grupo_id"]):
            par = conn.execute(
                "SELECT * FROM movimientos WHERE grupo_id=? AND id<>?",
                (mov["grupo_id"], mov_id),
            ).fetchone()
            if par:
                _revertir_efecto_stock(
                    conn, par["producto_id"], par["tipo"],
                    float(par["cantidad"])
                )
                conn.execute(
                    "DELETE FROM movimientos WHERE id=?", (par["id"],)
                )

        conn.execute("DELETE FROM movimientos WHERE id=?", (mov_id,))

        row = conn.execute(
            "SELECT MAX(fecha) AS ultima FROM movimientos "
            "WHERE producto_id=?",
            (mov["producto_id"],),
        ).fetchone()
        if row and row["ultima"]:
            conn.execute(
                "UPDATE productos SET fecha_ultima_mod=? WHERE id=?",
                (row["ultima"], mov["producto_id"]),
            )