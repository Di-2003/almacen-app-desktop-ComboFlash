"""
Lógica de negocio del almacén. Multi-local + multimoneda + categorías.

CONSISTENCIA DE CÓDIGOS: un nombre → un código global.
GANANCIA REAL: cada movimiento ENTRADA/SALIDA guarda precio_costo_momento.

CACHÉ EN MEMORIA:
  Las lecturas frecuentes se cachean. Cualquier escritura limpia la
  caché. Esto hace que listar_productos/totales_local sean instantáneos
  al cambiar de pestaña o local.
"""
import re
import uuid
import functools
from datetime import datetime
from db import get_conn, GENERAL_ID, MONEDAS_VALIDAS
from locales import listar_locales


# ============================================================
# CACHÉ
# ============================================================
_CACHE: dict = {}


def invalidar_cache() -> None:
    _CACHE.clear()


def _write(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        finally:
            _CACHE.clear()
    return wrapper


def _cached(key, producer):
    if key in _CACHE:
        return _CACHE[key]
    val = producer()
    _CACHE[key] = val
    return val


# ================= ROLES =================

ROL_ADMIN   = "admin"
ROL_ALMACEN = "almacen"
ROL_COMUN   = "comun"
_ROLES_OPERATIVOS = (ROL_ADMIN, ROL_ALMACEN)


def _extraer_usuario(usuario) -> tuple[str, str]:
    if isinstance(usuario, dict):
        return str(usuario.get("username", "")), str(usuario.get("rol", ""))
    return str(usuario), ""


def _autorizar(usuario, roles_permitidos) -> str:
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


def fmt_precio_moneda(p, moneda: str = "CUP") -> str:
    v = float(p or 0)
    m = (moneda or "CUP").upper()
    if m == "USD":
        return f"USD$ {v:,.2f}"
    if m == "EUR":
        return f"€ {v:,.2f}"
    return f"$ {v:,.2f}"


# ================= CÓDIGOS =================

LONGITUD_MAX_CODIGO = 20
_PATRON_CODIGO = re.compile(r"^F([A-Z])(\d{4})$")


def normalizar_codigo(codigo) -> str | None:
    if codigo is None:
        return None
    c = (codigo or "").strip().replace(" ", "").upper()
    if not c:
        return None
    return c[:LONGITUD_MAX_CODIGO]


def siguiente_codigo(local_id: int) -> str:
    with get_conn() as conn:
        filas = conn.execute(
            "SELECT codigo FROM productos WHERE codigo IS NOT NULL"
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
    return f"F{chr(ord(max_letra) + 1)}0001"


def _validar_codigo_unico(conn, local_id, codigo, excluir_id=None) -> None:
    c = normalizar_codigo(codigo)
    if not c:
        return
    sql = ("SELECT nombre FROM productos WHERE local_id=? AND codigo=? "
           "COLLATE NOCASE")
    params = [local_id, c]
    if excluir_id is not None:
        sql += " AND id<>?"
        params.append(excluir_id)
    row = conn.execute(sql, tuple(params)).fetchone()
    if row:
        raise ValueError(
            f"El código «{c}» ya está en uso por «{row['nombre']}» "
            f"en este local."
        )


def _validar_codigo_global(conn, nombre, codigo, excluir_id=None) -> None:
    c = normalizar_codigo(codigo)
    if not c:
        return
    sql = ("SELECT p.nombre, l.nombre AS local_nombre "
           "FROM productos p JOIN locales l ON l.id=p.local_id "
           "WHERE p.codigo=? COLLATE NOCASE "
           "AND p.nombre<>? COLLATE NOCASE")
    params = [c, nombre]
    if excluir_id is not None:
        sql += " AND p.id<>?"
        params.append(excluir_id)
    sql += " LIMIT 1"
    row = conn.execute(sql, tuple(params)).fetchone()
    if row:
        raise ValueError(
            f"El código «{c}» ya está en uso por «{row['nombre']}» "
            f"en «{row['local_nombre']}»."
        )


def _codigo_global_para_nombre(conn, nombre, excluir_local_id=None):
    sql = ("SELECT codigo FROM productos WHERE nombre=? COLLATE NOCASE "
           "AND codigo IS NOT NULL AND codigo<>''")
    params = [nombre]
    if excluir_local_id is not None:
        sql += " AND local_id<>?"
        params.append(excluir_local_id)
    sql += " LIMIT 1"
    row = conn.execute(sql, tuple(params)).fetchone()
    return row["codigo"] if row else None


# ================= CONFIG =================

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


def get_tasa(moneda: str) -> float:
    m = (moneda or "CUP").upper()
    if m == "USD":
        return get_tasa_usd()
    if m == "EUR":
        return get_tasa_eur()
    return 1.0


# ================= MONEDA DE VISUALIZACIÓN =================

def get_moneda_visualizacion() -> str:
    m = (get_config("moneda_visualizacion") or "CUP").upper()
    if m not in MONEDAS_VALIDAS:
        return "CUP"
    return m


def set_moneda_visualizacion(moneda: str) -> None:
    m = (moneda or "CUP").upper()
    if m not in MONEDAS_VALIDAS:
        m = "CUP"
    set_config("moneda_visualizacion", m)


# ================= CONVERSIÓN =================

def a_cup(valor: float, moneda: str) -> float:
    return float(valor or 0) * get_tasa(moneda)


def de_cup(valor_cup: float, moneda: str) -> float:
    t = get_tasa(moneda)
    if t <= 0:
        return float(valor_cup or 0)
    return float(valor_cup or 0) / t


def convertir(valor: float, de_moneda: str, a_moneda: str) -> float:
    dm = (de_moneda or "CUP").upper()
    am = (a_moneda or "CUP").upper()
    if dm == am:
        return float(valor or 0)
    return de_cup(a_cup(valor, dm), am)


def mostrar_precio(precio_cup: float, moneda_destino: str = None) -> str:
    if moneda_destino is None:
        moneda_destino = get_moneda_visualizacion()
    valor = de_cup(precio_cup, moneda_destino)
    return fmt_precio_moneda(valor, moneda_destino)


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


# ================= CONSULTAS (cacheadas) =================

def listar_productos(local_id, solo_activos: bool = True) -> list[dict]:
    key = ("listar_productos", local_id, solo_activos)

    def _producer():
        if local_id == GENERAL_ID:
            return _listar_general(solo_activos)
        sql = "SELECT * FROM productos WHERE local_id=?"
        if solo_activos:
            sql += " AND activo=1"
        sql += (" ORDER BY "
                "CASE WHEN codigo IS NULL OR codigo='' THEN 1 ELSE 0 END, "
                "codigo COLLATE NOCASE, nombre COLLATE NOCASE")
        with get_conn() as conn:
            return [dict(r) for r in
                    conn.execute(sql, (local_id,)).fetchall()]

    return _cached(key, _producer)


def listar_productos_inactivos(local_id) -> list[dict]:
    key = ("listar_inactivos", local_id)

    def _producer():
        if local_id == GENERAL_ID:
            return []
        with get_conn() as conn:
            filas = conn.execute(
                "SELECT * FROM productos WHERE local_id=? AND activo=0 "
                "ORDER BY nombre COLLATE NOCASE",
                (local_id,),
            ).fetchall()
        return [dict(r) for r in filas]

    return _cached(key, _producer)


def _listar_general(solo_activos: bool) -> list[dict]:
    locales_ids = [l["id"] for l in listar_locales(solo_activos=True)]
    if not locales_ids:
        return []
    placeholders = ",".join("?" * len(locales_ids))
    activo_sql = " AND activo=1" if solo_activos else ""
    sql = f"""
        SELECT
            MIN(codigo) AS codigo,
            nombre,
            SUM(stock) AS stock,
            SUM(stock * precio_costo) AS _costo_total,
            SUM(stock * precio_unitario) AS _venta_total,
            MAX(umbral_verde) AS umbral_verde,
            MAX(umbral_amarillo) AS umbral_amarillo,
            MAX(fecha_ultima_mod) AS fecha_ultima_mod,
            MAX(moneda_costo) AS moneda_costo,
            MAX(moneda_venta) AS moneda_venta,
            MAX(categoria_id) AS categoria_id
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
        d["precio_costo_orig"] = d["precio_costo"]
        d["precio_unitario_orig"] = d["precio_unitario"]
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
    p = buscar_producto_por_codigo(nombre_o_codigo, local_id)
    if p is not None:
        return p
    return buscar_producto_por_nombre(nombre_o_codigo, local_id)


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


def listar_movimientos(local_id=None, producto_id=None,
                       limite: int = 100) -> list[dict]:
    sql = ("SELECT m.*, p.nombre AS producto, p.codigo AS codigo, "
           "l.nombre AS local FROM movimientos m "
           "JOIN productos p ON p.id=m.producto_id "
           "JOIN locales l ON l.id=m.local_id")
    cond = []
    params = []
    if local_id is not None and local_id != GENERAL_ID:
        cond.append("m.local_id=?")
        params.append(local_id)
    if producto_id is not None:
        cond.append("m.producto_id=?")
        params.append(producto_id)
    if cond:
        sql += " WHERE " + " AND ".join(cond)
    sql += " ORDER BY m.fecha DESC, m.id DESC LIMIT ?"
    params.append(limite)
    with get_conn() as conn:
        return [dict(r) for r in
                conn.execute(sql, tuple(params)).fetchall()]


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


# ================= PROMEDIO PONDERADO =================

def _promedio_ponderado(stock_antes, orig_antes, cant_nueva, orig_nueva):
    total = float(stock_antes) + float(cant_nueva)
    if total <= 0:
        return float(orig_nueva or 0)
    return ((float(stock_antes) * float(orig_antes or 0))
            + (float(cant_nueva) * float(orig_nueva or 0))) / total


def conn_check_categoria(cat_id):
    from db import get_conn
    with get_conn() as conn:
        row = conn.execute(
            "SELECT 1 FROM categorias WHERE id=? AND activo=1", (cat_id,)
        ).fetchone()
        return row is not None


# ================= ENTRADAS =================

@_write
def registrar_entrada(nombre: str, cantidad, usuario, local_id: int,
                      codigo=None, precio_costo=None,
                      precio_unitario=None, moneda="CUP",
                      categoria_id=None, fecha=None) -> dict:
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

    moneda = (moneda or "CUP").upper()
    if moneda not in MONEDAS_VALIDAS:
        moneda = "CUP"

    codigo = normalizar_codigo(codigo)
    fecha = fecha or _ahora()
    grupo_id = uuid.uuid4().hex

    pc_in = None
    if precio_costo is not None:
        try:
            v = float(precio_costo)
            if v > 0:
                pc_in = v
        except (TypeError, ValueError):
            pass
    pu_in = None
    if precio_unitario is not None:
        try:
            v = float(precio_unitario)
            if v > 0:
                pu_in = v
        except (TypeError, ValueError):
            pass

    if categoria_id is not None:
        if not conn_check_categoria(categoria_id):
            categoria_id = None

    with get_conn() as conn:
        prod = conn.execute(
            "SELECT * FROM productos WHERE local_id=? "
            "AND nombre=? COLLATE NOCASE",
            (local_id, nombre),
        ).fetchone()

        pc_momento = 0.0

        if prod is None:
            codigo_global = _codigo_global_para_nombre(conn, nombre, local_id)
            if codigo_global:
                codigo = codigo_global

            _validar_codigo_unico(conn, local_id, codigo)
            _validar_codigo_global(conn, nombre, codigo)

            color_antes = "rojo"
            uv, ua = get_umbrales_default()
            mc = moneda
            mv = moneda
            pc_orig = pc_in or 0.0
            pu_orig = pu_in or 0.0
            pc_cup = a_cup(pc_orig, mc)
            pu_cup = a_cup(pu_orig, mv)
            pc_momento = pc_cup
            cur = conn.execute(
                "INSERT INTO productos("
                "local_id, codigo, nombre, stock,"
                "umbral_verde, umbral_amarillo,"
                "precio_costo, precio_unitario,"
                "precio_costo_orig, precio_unitario_orig,"
                "moneda_costo, moneda_venta, categoria_id,"
                "fecha_ultima_mod, activo) "
                "VALUES(?,?,?,0,?,?,?,?,?,?,?,?,?,?,1)",
                (local_id, codigo, nombre, uv, ua,
                 pc_cup, pu_cup, pc_orig, pu_orig,
                 mc, mv, categoria_id, fecha),
            )
            pid = cur.lastrowid
        else:
            color_antes = color_de_producto(dict(prod))
            pid = prod["id"]

            codigo_global = _codigo_global_para_nombre(conn, nombre, local_id)
            if codigo_global:
                codigo = codigo_global
            elif not codigo:
                codigo = (prod["codigo"] or "").strip() or None

            codigo_actual = (prod["codigo"] or "").strip()
            if codigo and codigo != codigo_actual:
                _validar_codigo_unico(conn, local_id, codigo, excluir_id=pid)
                _validar_codigo_global(conn, nombre, codigo, excluir_id=pid)
                conn.execute("UPDATE productos SET codigo=? WHERE id=?",
                             (codigo, pid))

            mc = (prod["moneda_costo"] or "CUP").upper()
            mv = (prod["moneda_venta"] or "CUP").upper()

            if pc_in is not None:
                pc_orig_nuevo = convertir(pc_in, moneda, mc)
                stock_antes = float(prod["stock"] or 0)
                orig_antes = float(prod["precio_costo_orig"] or 0)
                pc_orig = _promedio_ponderado(
                    stock_antes, orig_antes, cantidad, pc_orig_nuevo)
                pc_cup = a_cup(pc_orig, mc)
                conn.execute(
                    "UPDATE productos SET precio_costo=?, "
                    "precio_costo_orig=?, fecha_ultima_mod=? WHERE id=?",
                    (pc_cup, pc_orig, fecha, pid),
                )
                pc_momento = pc_cup
            else:
                pc_momento = float(prod["precio_costo"] or 0)

            if pu_in is not None:
                pu_orig = convertir(pu_in, moneda, mv)
                pu_cup = a_cup(pu_orig, mv)
                conn.execute(
                    "UPDATE productos SET precio_unitario=?, "
                    "precio_unitario_orig=?, fecha_ultima_mod=? WHERE id=?",
                    (pu_cup, pu_orig, fecha, pid),
                )

            if categoria_id is not None:
                conn.execute(
                    "UPDATE productos SET categoria_id=? WHERE id=?",
                    (categoria_id, pid),
                )

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
            "grupo_id,fecha,usuario,precio_costo_momento) "
            "VALUES(?,?,'ENTRADA',?,?,?,?,?)",
            (local_id, pid, cantidad, grupo_id, fecha, username, pc_momento),
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
        "codigo": nuevo["codigo"],
    }


# ================= SALIDAS =================

@_write
def registrar_salida(nombre_o_codigo, cantidad, usuario, local_id,
                     motivo=None, rebaja=0.0,
                     precio_unitario_momento=None,
                     detalle=None, fecha=None) -> dict:
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
                f"Producto no encontrado o inactivo: {nombre_o_codigo}")
        color_antes = color_de_producto(prod)
        if cantidad > prod["stock"]:
            raise StockInsuficiente(prod["stock"], cantidad)

        pu = (float(prod["precio_unitario"] or 0)
              if precio_unitario_momento is None
              else float(precio_unitario_momento))
        pc_momento = float(prod["precio_costo"] or 0)
        if rebaja > pu:
            raise ValueError(
                f"La rebaja ({fmt_precio(rebaja)}) no puede superar el "
                f"precio unitario ({fmt_precio(pu)}).")

        nuevo_stock = prod["stock"] - cantidad
        conn.execute(
            "UPDATE productos SET stock=?, fecha_ultima_mod=? WHERE id=?",
            (nuevo_stock, fecha, prod["id"]),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "motivo,grupo_id,detalle,rebaja,precio_unitario_momento,"
            "precio_costo_momento,fecha,usuario) "
            "VALUES(?,?,'SALIDA',?,?,?,?,?,?,?,?,?)",
            (local_id, prod["id"], cantidad, motivo, grupo_id,
             detalle, rebaja, pu, pc_momento, fecha, username),
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

@_write
def registrar_traspaso(nombre_o_codigo, cantidad, usuario,
                       local_origen_id, local_destino_id, fecha=None):
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
        nombre_o_codigo=nombre_o_codigo, cantidad=cantidad,
        local_origen_id=local_origen_id, local_destino_id=local_destino_id,
        usuario=username, fecha=fecha,
    )


def _traspasar_producto_interno(nombre_o_codigo, cantidad, local_origen_id,
                                local_destino_id, usuario, fecha,
                                motivo_cierre=False):
    grupo_id = uuid.uuid4().hex
    with get_conn() as conn:
        origen = buscar_producto(nombre_o_codigo, local_origen_id)
        if origen is None or not origen.get("activo", 1):
            raise ProductoNoExiste(
                f"Producto no encontrado en el local de origen: "
                f"{nombre_o_codigo}")
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
             "cierre de tienda" if motivo_cierre else None, fecha, usuario),
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
            mc = origen.get("moneda_costo") or "CUP"
            mv = origen.get("moneda_venta") or "CUP"
            pc_orig = float(origen.get("precio_costo_orig") or 0)
            pu_orig = float(origen.get("precio_unitario_orig") or 0)
            pc_cup = float(origen.get("precio_costo") or 0)
            pu_cup = float(origen.get("precio_unitario") or 0)
            cat_id = origen.get("categoria_id")
            cur = conn.execute(
                "INSERT INTO productos("
                "local_id, codigo, nombre, stock,"
                "umbral_verde, umbral_amarillo,"
                "precio_costo, precio_unitario,"
                "precio_costo_orig, precio_unitario_orig,"
                "moneda_costo, moneda_venta, categoria_id,"
                "fecha_ultima_mod, activo) "
                "VALUES(?,?,?,0,?,?,?,?,?,?,?,?,?,?,1)",
                (local_destino_id, codigo_destino, nombre, uv, ua,
                 pc_cup, pu_cup, pc_orig, pu_orig, mc, mv, cat_id, fecha),
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
             "cierre de tienda" if motivo_cierre else None, fecha, usuario),
        )


# ================= UMBRALES =================

@_write
def cambiar_umbrales(producto_id, umbral_verde, umbral_amarillo, usuario):
    username = _autorizar(usuario, _ROLES_OPERATIVOS)
    try:
        uv = int(umbral_verde)
        ua = int(umbral_amarillo)
    except (TypeError, ValueError):
        raise ValueError("Los umbrales deben ser números enteros")
    if uv <= ua:
        raise ValueError("El umbral verde debe ser mayor que el amarillo")
    if ua < 0:
        raise ValueError("Los umbrales no pueden ser negativos")
    fecha = _ahora()
    detalle = f"verde={uv}, amarillo={ua}"
    with get_conn() as conn:
        row = conn.execute(
            "SELECT local_id FROM productos WHERE id=?", (producto_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Producto no encontrado")
        conn.execute(
            "UPDATE productos SET umbral_verde=?, umbral_amarillo=?, "
            "fecha_ultima_mod=? WHERE id=?",
            (uv, ua, fecha, producto_id),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'UMBRAL',0,?,?,?)",
            (row["local_id"], producto_id, detalle, fecha, username),
        )


# ================= CATEGORÍA =================

@_write
def set_categoria(producto_id, categoria_id, usuario):
    _autorizar(usuario, _ROLES_OPERATIVOS)
    if categoria_id is not None and not conn_check_categoria(categoria_id):
        raise ValueError("Categoría inválida o inactiva")
    fecha = _ahora()
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT local_id, nombre FROM productos WHERE id=?",
            (producto_id,),
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")
        conn.execute(
            "UPDATE productos SET categoria_id=?, fecha_ultima_mod=? "
            "WHERE nombre=? COLLATE NOCASE",
            (categoria_id, fecha, prod["nombre"]),
        )


# ================= PRECIOS =================

@_write
def set_precio_costo(producto_id, valor, moneda, usuario, propagar=True):
    username = _autorizar(usuario, _ROLES_OPERATIVOS)
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        raise ValueError("El precio debe ser un número")
    if valor < 0:
        raise ValueError("El precio no puede ser negativo")
    moneda = (moneda or "CUP").upper()
    if moneda not in MONEDAS_VALIDAS:
        moneda = "CUP"
    valor_cup = a_cup(valor, moneda)
    fecha = _ahora()
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT local_id, nombre FROM productos WHERE id=?",
            (producto_id,),
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")
        if propagar:
            conn.execute(
                "UPDATE productos SET precio_costo=?, precio_costo_orig=?, "
                "moneda_costo=?, fecha_ultima_mod=? "
                "WHERE nombre=? COLLATE NOCASE",
                (valor_cup, valor, moneda, fecha, prod["nombre"]),
            )
        else:
            conn.execute(
                "UPDATE productos SET precio_costo=?, precio_costo_orig=?, "
                "moneda_costo=?, fecha_ultima_mod=? WHERE id=?",
                (valor_cup, valor, moneda, fecha, producto_id),
            )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'AJUSTE',0,?,?,?)",
            (prod["local_id"], producto_id,
             f"precio_costo={valor} {moneda}", fecha, username),
        )


@_write
def set_precio_unitario(producto_id, valor, moneda, usuario,
                        propagar=True):
    username = _autorizar(usuario, _ROLES_OPERATIVOS)
    try:
        valor = float(valor)
    except (TypeError, ValueError):
        raise ValueError("El precio debe ser un número")
    if valor < 0:
        raise ValueError("El precio no puede ser negativo")
    moneda = (moneda or "CUP").upper()
    if moneda not in MONEDAS_VALIDAS:
        moneda = "CUP"
    valor_cup = a_cup(valor, moneda)
    fecha = _ahora()
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT local_id, nombre FROM productos WHERE id=?",
            (producto_id,),
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")
        if propagar:
            conn.execute(
                "UPDATE productos SET precio_unitario=?, "
                "precio_unitario_orig=?, moneda_venta=?, "
                "fecha_ultima_mod=? WHERE nombre=? COLLATE NOCASE",
                (valor_cup, valor, moneda, fecha, prod["nombre"]),
            )
        else:
            conn.execute(
                "UPDATE productos SET precio_unitario=?, "
                "precio_unitario_orig=?, moneda_venta=?, "
                "fecha_ultima_mod=? WHERE id=?",
                (valor_cup, valor, moneda, fecha, producto_id),
            )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'AJUSTE',0,?,?,?)",
            (prod["local_id"], producto_id,
             f"precio_unitario={valor} {moneda}", fecha, username),
        )


@_write
def cambiar_moneda_precio(producto_id, campo, nueva_moneda, usuario):
    _autorizar(usuario, _ROLES_OPERATIVOS)
    if campo not in ("costo", "venta"):
        raise ValueError("Campo inválido")
    nm = (nueva_moneda or "CUP").upper()
    if nm not in MONEDAS_VALIDAS:
        raise ValueError("Moneda inválida")
    with get_conn() as conn:
        prod = conn.execute(
            "SELECT * FROM productos WHERE id=?", (producto_id,)
        ).fetchone()
        if prod is None:
            raise ValueError("Producto no encontrado")
        fecha = _ahora()
        if campo == "costo":
            orig_actual = float(prod["precio_costo_orig"] or 0)
            moneda_actual = (prod["moneda_costo"] or "CUP").upper()
            nuevo_orig = convertir(orig_actual, moneda_actual, nm)
            nuevo_cup = a_cup(nuevo_orig, nm)
            conn.execute(
                "UPDATE productos SET precio_costo=?, precio_costo_orig=?, "
                "moneda_costo=?, fecha_ultima_mod=? "
                "WHERE nombre=? COLLATE NOCASE",
                (nuevo_cup, nuevo_orig, nm, fecha, prod["nombre"]),
            )
        else:
            orig_actual = float(prod["precio_unitario_orig"] or 0)
            moneda_actual = (prod["moneda_venta"] or "CUP").upper()
            nuevo_orig = convertir(orig_actual, moneda_actual, nm)
            nuevo_cup = a_cup(nuevo_orig, nm)
            conn.execute(
                "UPDATE productos SET precio_unitario=?, "
                "precio_unitario_orig=?, moneda_venta=?, "
                "fecha_ultima_mod=? WHERE nombre=? COLLATE NOCASE",
                (nuevo_cup, nuevo_orig, nm, fecha, prod["nombre"]),
            )


@_write
def recalcular_todos_los_precios() -> int:
    usd = get_tasa_usd()
    eur = get_tasa_eur()
    fecha = _ahora()
    with get_conn() as conn:
        cur = conn.execute(
            """
            UPDATE productos SET
                precio_costo = CASE moneda_costo
                    WHEN 'USD' THEN precio_costo_orig * ?
                    WHEN 'EUR' THEN precio_costo_orig * ?
                    ELSE precio_costo_orig
                END,
                precio_unitario = CASE moneda_venta
                    WHEN 'USD' THEN precio_unitario_orig * ?
                    WHEN 'EUR' THEN precio_unitario_orig * ?
                    ELSE precio_unitario_orig
                END,
                fecha_ultima_mod = ?
            WHERE moneda_costo <> 'CUP'
               OR moneda_venta <> 'CUP'
            """,
            (usd, eur, usd, eur, fecha),
        )
        return cur.rowcount


# ================= CÓDIGO / NOMBRE =================

@_write
def set_codigo(producto_id, nuevo_codigo, usuario):
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
            _validar_codigo_global(conn, prod["nombre"], c)
            _validar_codigo_unico(conn, prod["local_id"], c,
                                  excluir_id=producto_id)

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


@_write
def renombrar_producto(producto_id, nombre_nuevo, usuario):
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
        if nombre_actual == nombre_nuevo:
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
                f"«{otro['local_nombre']}». Usa un nombre distinto.")
        try:
            conn.execute(
                "UPDATE producto_proveedores SET producto_nombre=? "
                "WHERE producto_nombre=? COLLATE NOCASE",
                (nombre_nuevo, nombre_actual),
            )
        except Exception:
            pass
        conn.execute(
            "UPDATE producto_proveedores SET producto_nombre=? "
            "WHERE producto_nombre=? COLLATE NOCASE",
            (nombre_nuevo, nombre_actual),
        )
        conn.execute(
            "INSERT INTO movimientos(local_id,producto_id,tipo,cantidad,"
            "detalle,fecha,usuario) VALUES(?,?,'AJUSTE',0,?,?,?)",
            (prod["local_id"], producto_id,
             f"nombre: '{nombre_actual}' -> '{nombre_nuevo}' (propagado)",
             fecha, username),
        )


# ================= BAJA / REACTIVAR =================

@_write
def dar_baja(producto_id, usuario, motivo=None):
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


@_write
def reactivar_producto(producto_id, usuario):
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


# ================= FILTROS =================

def productos_por_color(local_id, color):
    return [p for p in listar_productos(local_id, solo_activos=True)
            if color_de_producto(p) == color]


def productos_stock_cero(local_id):
    return [p for p in listar_productos(local_id, solo_activos=True)
            if float(p["stock"] or 0) == 0]


def productos_por_categoria(local_id, categoria_id):
    return [p for p in listar_productos(local_id, solo_activos=True)
            if p.get("categoria_id") == categoria_id]


# ================= TOTALES (cacheados) =================

def totales_local(local_id) -> dict:
    key = ("totales_local", local_id)

    def _producer():
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

    return _cached(key, _producer)


def totales_por_concepto(local_id) -> dict:
    key = ("totales_concepto", local_id)

    def _producer():
        filtro = ""
        params = []
        if local_id != GENERAL_ID:
            filtro = " AND local_id=?"
            params.append(local_id)
        with get_conn() as conn:
            ventas = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(cantidad),0) AS cant, "
                "COALESCE(SUM((precio_unitario_momento - rebaja) * cantidad),0) "
                "AS monto FROM movimientos "
                "WHERE tipo='SALIDA' "
                "AND LOWER(TRIM(COALESCE(motivo,'')))='venta'" + filtro,
                tuple(params),
            ).fetchone()
            entradas = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(cantidad),0) AS cant "
                "FROM movimientos WHERE tipo='ENTRADA'" + filtro,
                tuple(params),
            ).fetchone()
            otras = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(cantidad),0) AS cant "
                "FROM movimientos WHERE tipo='SALIDA' "
                "AND LOWER(TRIM(COALESCE(motivo,'')))<>'venta'" + filtro,
                tuple(params),
            ).fetchone()
            bajas = conn.execute(
                "SELECT COUNT(*) AS n, COALESCE(SUM(cantidad),0) AS cant "
                "FROM movimientos WHERE tipo='BAJA'" + filtro,
                tuple(params),
            ).fetchone()
        return {
            "ventas": {"n": int(ventas["n"] or 0),
                       "cantidad": float(ventas["cant"] or 0),
                       "monto": float(ventas["monto"] or 0)},
            "entradas": {"n": int(entradas["n"] or 0),
                         "cantidad": float(entradas["cant"] or 0)},
            "otras_salidas": {"n": int(otras["n"] or 0),
                              "cantidad": float(otras["cant"] or 0)},
            "bajas": {"n": int(bajas["n"] or 0),
                      "cantidad": float(bajas["cant"] or 0)},
        }

    return _cached(key, _producer)


# ================= ELIMINAR MOVIMIENTO =================

def _revertir_efecto_stock(conn, producto_id, tipo, cantidad):
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
            "Reactiva el producto manualmente si es necesario.")
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
            f"el movimiento. Revisa las operaciones previas.")
    conn.execute("UPDATE productos SET stock=? WHERE id=?",
                 (nuevo, producto_id))


@_write
def eliminar_movimiento(mov_id, usuario):
    _autorizar(usuario, _ROLES_OPERATIVOS)
    with get_conn() as conn:
        mov = conn.execute(
            "SELECT * FROM movimientos WHERE id=?", (mov_id,)
        ).fetchone()
        if mov is None:
            raise ValueError("Movimiento no encontrado")
        _revertir_efecto_stock(
            conn, mov["producto_id"], mov["tipo"], float(mov["cantidad"]))
        if (mov["tipo"] in ("TRASPASO_SALIDA", "TRASPASO_ENTRADA")
                and mov["grupo_id"]):
            par = conn.execute(
                "SELECT * FROM movimientos WHERE grupo_id=? AND id<>?",
                (mov["grupo_id"], mov_id),
            ).fetchone()
            if par:
                _revertir_efecto_stock(
                    conn, par["producto_id"], par["tipo"],
                    float(par["cantidad"]))
                conn.execute("DELETE FROM movimientos WHERE id=?",
                            (par["id"],))
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