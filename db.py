"""
Esquema BD v10 + migración automática desde P1 (v4).

Cuando abres una BD del P1 viejo (schema v4 sin `local_id`), se
detecta y se migra IN-PLACE preservando usuarios, configuración,
productos y movimientos.

Idempotente: si ya está en v10, no hace nada.
"""
import sqlite3
from datetime import datetime
from rutas import DB_PATH

VERSION_ESQUEMA = 10
GENERAL_ID = -1

MONEDAS_VALIDAS = ("CUP", "USD", "EUR")

CATEGORIAS_DEFAULT = (
    "Alimentos", "Bebidas", "Limpieza", "Aseo", "Electrónica",
)

CATEGORIAS_GASTOS_DEFAULT = (
    "Luz", "Agua", "Alquiler", "Salario", "Transporte", "Otros",
)

METODOS_PAGO_DEFAULT = (
    ("Efectivo CUP",    "Efectivo CUP",    1, 1, 0, 0, None, None),
    ("Efectivo USD",    "Efectivo USD",    0, 2, 1, 0, None, None),
    ("Efectivo EUR",    "Efectivo EUR",    0, 3, 1, 0, None, None),
    ("Efectivo MLC",    "Efectivo MLC",    0, 4, 1, 0, None, None),
    ("Transfermóvil",   "Transfermóvil",   1, 5, 0, 0, None, None),
    ("EnZona",          "EnZona",          1, 6, 0, 0, None, None),
    ("Zelle",           "Zelle",           0, 7, 1, 0, None, None),
    ("Tarjeta",         "Tarjeta",         0, 8, 1, 0, None, None),
    ("Fiado",           "Fiado",           1, 9, 0, 1, None, None),
)


SCHEMA = """
PRAGMA foreign_keys = ON;

-- ══════════════════════════════════════════════════════════════
-- CORE
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS locales (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT UNIQUE NOT NULL COLLATE NOCASE,
    es_almacen  INTEGER NOT NULL DEFAULT 0,
    activo      INTEGER NOT NULL DEFAULT 1,
    creado      TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    rol           TEXT NOT NULL CHECK(rol IN ('admin','almacen','comun')),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado        TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS categorias (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT UNIQUE NOT NULL COLLATE NOCASE,
    activo  INTEGER NOT NULL DEFAULT 1
);

-- ══════════════════════════════════════════════════════════════
-- INVENTARIO
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS productos (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id              INTEGER NOT NULL,
    codigo                TEXT COLLATE NOCASE,
    nombre                TEXT NOT NULL COLLATE NOCASE,
    stock                 REAL NOT NULL DEFAULT 0,
    umbral_verde          INTEGER NOT NULL DEFAULT 50,
    umbral_amarillo       INTEGER NOT NULL DEFAULT 20,
    precio_costo          REAL NOT NULL DEFAULT 0,
    precio_unitario       REAL NOT NULL DEFAULT 0,
    precio_costo_orig     REAL NOT NULL DEFAULT 0,
    precio_unitario_orig  REAL NOT NULL DEFAULT 0,
    moneda_costo          TEXT NOT NULL DEFAULT 'CUP'
                        CHECK(moneda_costo IN ('CUP','USD','EUR')),
    moneda_venta          TEXT NOT NULL DEFAULT 'CUP'
                        CHECK(moneda_venta IN ('CUP','USD','EUR')),
    categoria_id          INTEGER REFERENCES categorias(id),
    fecha_ultima_mod      TEXT NOT NULL,
    activo                INTEGER NOT NULL DEFAULT 1,
    es_granel             INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(local_id) REFERENCES locales(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_local_codigo
    ON productos(local_id, codigo) WHERE codigo IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_local_nombre
    ON productos(local_id, nombre);
CREATE INDEX IF NOT EXISTS idx_prod_categoria ON productos(categoria_id);
CREATE INDEX IF NOT EXISTS idx_prod_local ON productos(local_id);
CREATE INDEX IF NOT EXISTS idx_prod_activo ON productos(activo);

CREATE TABLE IF NOT EXISTS movimientos (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id                 INTEGER NOT NULL,
    producto_id              INTEGER NOT NULL,
    tipo                     TEXT NOT NULL CHECK(tipo IN
        ('ENTRADA','SALIDA','BAJA','RESTAURACION',
        'TRASPASO_SALIDA','TRASPASO_ENTRADA',
        'UMBRAL','AJUSTE')),
    cantidad                 REAL NOT NULL DEFAULT 0,
    motivo                   TEXT,
    grupo_id                 TEXT,
    detalle                  TEXT,
    rebaja                   REAL NOT NULL DEFAULT 0,
    precio_unitario_momento  REAL NOT NULL DEFAULT 0,
    precio_costo_momento     REAL NOT NULL DEFAULT 0,
    fecha                    TEXT NOT NULL,
    usuario                  TEXT NOT NULL,
    proveedor_id             INTEGER,
    FOREIGN KEY(local_id) REFERENCES locales(id),
    FOREIGN KEY(producto_id) REFERENCES productos(id)
);

CREATE INDEX IF NOT EXISTS idx_mov_local    ON movimientos(local_id);
CREATE INDEX IF NOT EXISTS idx_mov_producto ON movimientos(producto_id);
CREATE INDEX IF NOT EXISTS idx_mov_fecha    ON movimientos(fecha);
CREATE INDEX IF NOT EXISTS idx_mov_grupo    ON movimientos(grupo_id);
CREATE INDEX IF NOT EXISTS idx_mov_local_fecha
    ON movimientos(local_id, fecha);
CREATE INDEX IF NOT EXISTS idx_mov_tipo_motivo
    ON movimientos(tipo, motivo);

-- ══════════════════════════════════════════════════════════════
-- POS + CLIENTES + CAJA + MÉTODOS
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS clientes (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre         TEXT NOT NULL COLLATE NOCASE,
    telefono       TEXT,
    direccion      TEXT,
    email          TEXT,
    limite_credito REAL NOT NULL DEFAULT 0,
    activo         INTEGER NOT NULL DEFAULT 1,
    creado         TEXT NOT NULL,
    notas          TEXT
);
CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON clientes(nombre);
CREATE INDEX IF NOT EXISTS idx_clientes_activo ON clientes(activo);

CREATE TABLE IF NOT EXISTS ordenes_venta (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id         INTEGER NOT NULL,
    cliente_id       INTEGER,
    numero_ticket    TEXT UNIQUE,
    fecha            TEXT NOT NULL,
    subtotal         REAL NOT NULL DEFAULT 0,
    descuento_global REAL NOT NULL DEFAULT 0,
    total            REAL NOT NULL DEFAULT 0,
    vuelto_cup       REAL NOT NULL DEFAULT 0,
    estado           TEXT NOT NULL DEFAULT 'pagada'
        CHECK(estado IN ('pendiente','parcial','pagada',
                        'anulada','devuelta')),
    saldo_pendiente  REAL NOT NULL DEFAULT 0,
    usuario          TEXT NOT NULL,
    notas            TEXT,
    FOREIGN KEY(local_id) REFERENCES locales(id),
    FOREIGN KEY(cliente_id) REFERENCES clientes(id)
);
CREATE INDEX IF NOT EXISTS idx_ordenes_local_fecha
    ON ordenes_venta(local_id, fecha);
CREATE INDEX IF NOT EXISTS idx_ordenes_cliente
    ON ordenes_venta(cliente_id);
CREATE INDEX IF NOT EXISTS idx_ordenes_estado
    ON ordenes_venta(estado);
CREATE INDEX IF NOT EXISTS idx_ordenes_ticket
    ON ordenes_venta(numero_ticket);

CREATE TABLE IF NOT EXISTS orden_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_id        INTEGER NOT NULL,
    producto_id     INTEGER,
    nombre          TEXT NOT NULL,
    codigo          TEXT,
    cantidad        REAL NOT NULL,
    precio_unitario REAL NOT NULL,
    rebaja          REAL NOT NULL DEFAULT 0,
    importe         REAL NOT NULL,
    FOREIGN KEY(orden_id) REFERENCES ordenes_venta(id) ON DELETE CASCADE,
    FOREIGN KEY(producto_id) REFERENCES productos(id)
);
CREATE INDEX IF NOT EXISTS idx_items_orden ON orden_items(orden_id);
CREATE INDEX IF NOT EXISTS idx_items_producto
    ON orden_items(producto_id);

CREATE TABLE IF NOT EXISTS pagos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_id  INTEGER NOT NULL,
    metodo    TEXT NOT NULL,
    moneda    TEXT NOT NULL DEFAULT 'CUP',
    monto     REAL NOT NULL,
    tasa      REAL NOT NULL DEFAULT 1.0,
    monto_cup REAL NOT NULL,
    fecha     TEXT NOT NULL,
    usuario   TEXT NOT NULL,
    FOREIGN KEY(orden_id) REFERENCES ordenes_venta(id) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_pagos_orden ON pagos(orden_id);
CREATE INDEX IF NOT EXISTS idx_pagos_metodo ON pagos(metodo);

CREATE TABLE IF NOT EXISTS abonos (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_id  INTEGER NOT NULL,
    monto     REAL NOT NULL,
    moneda    TEXT NOT NULL DEFAULT 'CUP',
    tasa      REAL NOT NULL DEFAULT 1.0,
    monto_cup REAL NOT NULL,
    metodo    TEXT NOT NULL DEFAULT 'Efectivo CUP',
    fecha     TEXT NOT NULL,
    usuario   TEXT NOT NULL,
    notas     TEXT,
    FOREIGN KEY(orden_id) REFERENCES ordenes_venta(id)
);
CREATE INDEX IF NOT EXISTS idx_abonos_orden ON abonos(orden_id);

CREATE TABLE IF NOT EXISTS devoluciones (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    orden_id       INTEGER NOT NULL,
    item_id        INTEGER,
    producto_id    INTEGER,
    cantidad       REAL NOT NULL,
    monto_devuelto REAL NOT NULL,
    motivo         TEXT,
    fecha          TEXT NOT NULL,
    usuario        TEXT NOT NULL,
    FOREIGN KEY(orden_id) REFERENCES ordenes_venta(id),
    FOREIGN KEY(item_id) REFERENCES orden_items(id),
    FOREIGN KEY(producto_id) REFERENCES productos(id)
);
CREATE INDEX IF NOT EXISTS idx_devoluciones_orden
    ON devoluciones(orden_id);

CREATE TABLE IF NOT EXISTS caja_sesiones (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id        INTEGER NOT NULL,
    usuario         TEXT NOT NULL,
    abierta         TEXT NOT NULL,
    cerrada         TEXT,
    saldo_inicial   REAL NOT NULL DEFAULT 0,
    saldo_final     REAL,
    saldo_sistema   REAL,
    diferencia      REAL,
    notas_apertura  TEXT,
    notas_cierre    TEXT,
    FOREIGN KEY(local_id) REFERENCES locales(id)
);
CREATE INDEX IF NOT EXISTS idx_caja_local_abierta
    ON caja_sesiones(local_id, cerrada);

CREATE TABLE IF NOT EXISTS metodos_pago (
    clave           TEXT PRIMARY KEY,
    etiqueta        TEXT NOT NULL,
    activo          INTEGER NOT NULL DEFAULT 0,
    orden           INTEGER NOT NULL DEFAULT 0,
    requiere_moneda INTEGER NOT NULL DEFAULT 0,
    es_credito      INTEGER NOT NULL DEFAULT 0,
    cuenta          TEXT,
    qr_imagen       TEXT
);

-- ══════════════════════════════════════════════════════════════
-- GASTOS + PROVEEDORES (v10)
-- ══════════════════════════════════════════════════════════════
CREATE TABLE IF NOT EXISTS categorias_gastos (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre  TEXT UNIQUE NOT NULL COLLATE NOCASE,
    activo  INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS gastos (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id        INTEGER,
    categoria_id    INTEGER,
    monto           REAL NOT NULL,
    moneda          TEXT NOT NULL DEFAULT 'CUP'
                    CHECK(moneda IN ('CUP','USD','EUR')),
    tasa            REAL NOT NULL DEFAULT 1.0,
    monto_cup       REAL NOT NULL,
    metodo          TEXT,
    descripcion     TEXT,
    fecha           TEXT NOT NULL,
    usuario         TEXT NOT NULL,
    caja_sesion_id  INTEGER,
    FOREIGN KEY(local_id) REFERENCES locales(id),
    FOREIGN KEY(categoria_id) REFERENCES categorias_gastos(id),
    FOREIGN KEY(caja_sesion_id) REFERENCES caja_sesiones(id)
);
CREATE INDEX IF NOT EXISTS idx_gastos_fecha ON gastos(fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_local_fecha
    ON gastos(local_id, fecha);
CREATE INDEX IF NOT EXISTS idx_gastos_categoria
    ON gastos(categoria_id);
CREATE INDEX IF NOT EXISTS idx_gastos_caja
    ON gastos(caja_sesion_id);

CREATE TABLE IF NOT EXISTS proveedores (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre    TEXT UNIQUE NOT NULL COLLATE NOCASE,
    telefono  TEXT,
    activo    INTEGER NOT NULL DEFAULT 1,
    creado    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_prov_nombre ON proveedores(nombre);
CREATE INDEX IF NOT EXISTS idx_prov_activo ON proveedores(activo);

CREATE TABLE IF NOT EXISTS producto_proveedores (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    producto_nombre  TEXT NOT NULL COLLATE NOCASE,
    proveedor_id     INTEGER NOT NULL,
    es_principal     INTEGER NOT NULL DEFAULT 0,
    FOREIGN KEY(proveedor_id) REFERENCES proveedores(id)
        ON DELETE CASCADE,
    UNIQUE(producto_nombre, proveedor_id)
);
CREATE INDEX IF NOT EXISTS idx_pp_nombre
    ON producto_proveedores(producto_nombre);
CREATE INDEX IF NOT EXISTS idx_pp_proveedor
    ON producto_proveedores(proveedor_id);
CREATE INDEX IF NOT EXISTS idx_pp_principal
    ON producto_proveedores(producto_nombre, es_principal);

CREATE TABLE IF NOT EXISTS pagos_proveedor (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    proveedor_id  INTEGER NOT NULL,
    monto         REAL NOT NULL,
    moneda        TEXT NOT NULL DEFAULT 'CUP'
                CHECK(moneda IN ('CUP','USD','EUR')),
    tasa          REAL NOT NULL DEFAULT 1.0,
    monto_cup     REAL NOT NULL,
    metodo        TEXT,
    fecha         TEXT NOT NULL,
    usuario       TEXT NOT NULL,
    notas         TEXT,
    FOREIGN KEY(proveedor_id) REFERENCES proveedores(id)
);
CREATE INDEX IF NOT EXISTS idx_pagos_prov_proveedor
    ON pagos_proveedor(proveedor_id);
CREATE INDEX IF NOT EXISTS idx_pagos_prov_fecha
    ON pagos_proveedor(fecha);
"""


# ============================================================
# CONEXIÓN
# ============================================================

from contextlib import contextmanager

@contextmanager
def get_conn():
    """
    Conexión SQLite que se CIERRA AUTOMÁTICAMENTE al salir del with.
    Antes era una función normal y la conexión quedaba abierta,
    bloqueando el archivo en Windows.
    """
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -20000")
    conn.execute("PRAGMA mmap_size = 134217728")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

# ============================================================
# INICIALIZACIÓN
# ============================================================

def inicializar_db() -> None:
    with get_conn() as conn:
        # 1) ¿Viene del P1 viejo (v4)? → migrar y salir.
        if _detectar_schema_p1(conn):
            _migrar_v4_a_v10(conn)
            return

        # 2) Ya en formato P2: ¿virgen o ya migrada?
        version = _leer_version(conn)

        if version is None:
            conn.executescript(SCHEMA)
            _insertar_categorias_default(conn)
            _insertar_categorias_gastos_default(conn)
        elif version != VERSION_ESQUEMA:
            raise RuntimeError(
                f"Versión de esquema inesperada: {version}. "
                f"Esta versión solo soporta v{VERSION_ESQUEMA}. "
                f"Restaura un backup compatible.")

        _asegurar_defaults(conn)
        _asegurar_almacen(conn)
        _asegurar_columnas_extra(conn)
        _asegurar_indices_extra(conn)
        _asegurar_metodos_pago(conn)
        _marcar_version(conn)

# ============================================================
# MIGRACIÓN P1 (v4) → P2 (v10)
# ============================================================

def _detectar_schema_p1(conn) -> bool:
    """True si `productos` existe pero NO tiene `local_id` (P1 v4)."""
    try:
        rows = conn.execute("PRAGMA table_info(productos)").fetchall()
    except sqlite3.OperationalError:
        return False
    if not rows:
        return False
    return "local_id" not in {r["name"] for r in rows}


def _migrar_v4_a_v10(conn) -> None:
    """
    Migración P1 (v4) -> P2 (v10) preservando datos.

    Estrategia:
      1. Renombrar productos/movimientos viejos.
      2. Ejecutar SCHEMA (crea las nuevas).
      3. Insertar Almacén + categorías + métodos de pago.
      4. Copiar productos viejos con código secuencial.
      5. Copiar movimientos viejos.
      6. Borrar tablas temporales.
      7. Marcar versión = 10.
    """
    print("[migración] Detectado esquema P1 (v4). Migrando a v10...")

    # 1) Renombrar
    conn.execute("ALTER TABLE productos RENAME TO _productos_v4")
    conn.execute("ALTER TABLE movimientos RENAME TO _movimientos_v4")

    # 2) Crear schema v10
    conn.executescript(SCHEMA)

    # 3) Almacén + defaults
    _asegurar_almacen(conn)
    _insertar_categorias_default(conn)
    _insertar_categorias_gastos_default(conn)
    _asegurar_metodos_pago(conn)

    almacen_id = conn.execute(
        "SELECT id FROM locales WHERE es_almacen=1"
    ).fetchone()["id"]

    # 4) Copiar productos
    cols_movs = {r["name"] for r in conn.execute(
        "PRAGMA table_info(_movimientos_v4)").fetchall()}
    tiene_precio_momento = "precio_unitario_mov" in cols_movs

    productos_viejos = conn.execute(
        "SELECT * FROM _productos_v4 ORDER BY id ASC"
    ).fetchall()

    codigos_usados = set()
    ultimo_codigo = None
    for i, p in enumerate(productos_viejos):
        codigo = _generar_codigo_secuencial(i + 1)
        while codigo in codigos_usados:
            i += 1
            codigo = _generar_codigo_secuencial(i + 1)
        codigos_usados.add(codigo)
        ultimo_codigo = codigo

        precio_unit = float(p["precio_unitario"] or 0)
        fecha_mod = p["fecha_ultima_mod"] or datetime.now().strftime(
            "%Y-%m-%d %H:%M:%S")

        conn.execute(
            "INSERT INTO productos(id, local_id, codigo, nombre, stock,"
            " umbral_verde, umbral_amarillo,"
            " precio_costo, precio_unitario,"
            " precio_costo_orig, precio_unitario_orig,"
            " moneda_costo, moneda_venta, categoria_id,"
            " fecha_ultima_mod, activo, es_granel)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (p["id"], almacen_id, codigo, p["nombre"],
             float(p["stock"] or 0),
             int(p["umbral_verde"] or 50),
             int(p["umbral_amarillo"] or 20),
             0.0, precio_unit, 0.0, precio_unit,
             "CUP", "CUP", None, fecha_mod,
             int(p["activo"] or 1), 0)
        )

    n_prods = len(productos_viejos)

    # 5) Copiar movimientos
    movs_viejos = conn.execute(
        "SELECT * FROM _movimientos_v4 ORDER BY id ASC"
    ).fetchall()

    for m in movs_viejos:
        precio_momento = 0.0
        if tiene_precio_momento:
            try:
                precio_momento = float(m["precio_unitario_mov"] or 0)
            except (TypeError, ValueError):
                pass

        conn.execute(
            "INSERT INTO movimientos(id, local_id, producto_id, tipo,"
            " cantidad, motivo, grupo_id, detalle, rebaja,"
            " precio_unitario_momento, precio_costo_momento,"
            " fecha, usuario, proveedor_id)"
            " VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (m["id"], almacen_id, m["producto_id"], m["tipo"],
             float(m["cantidad"] or 0),
             m["motivo"], m["grupo_id"], m["detalle"],
             0.0, precio_momento, 0.0,
             m["fecha"], m["usuario"], None)
        )

    n_movs = len(movs_viejos)

    # 6) Borrar temporales (hijo primero por FK)
    conn.execute("DROP TABLE _movimientos_v4")
    conn.execute("DROP TABLE _productos_v4")

    # 7) Marcar versión
    _marcar_version(conn)

    print(f"[migración] OK: {n_prods} productos, {n_movs} movimientos "
          f"migrados al Almacén (id={almacen_id}).")
    if ultimo_codigo:
        print(f"[migración] Códigos auto-asignados: FA0001 … {ultimo_codigo}")


def _generar_codigo_secuencial(indice: int) -> str:
    """1 → FA0001, 2 → FA0002, …, 10000 → FB0001, …"""
    letra = chr(65 + ((indice - 1) // 9999))
    num = ((indice - 1) % 9999) + 1
    return f"F{letra}{num:04d}"


# ============================================================
# HELPERS DE VERSIÓN
# ============================================================

def _leer_version(conn):
    try:
        row = conn.execute(
            "SELECT valor FROM meta WHERE clave='version_esquema'"
        ).fetchone()
        return int(row["valor"]) if row else None
    except sqlite3.OperationalError:
        return None


def _marcar_version(conn) -> None:
    conn.execute(
        "INSERT INTO meta(clave,valor) VALUES('version_esquema',?) "
        "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
        (str(VERSION_ESQUEMA),))


# ============================================================
# DEFAULTS
# ============================================================

def _insertar_categorias_default(conn) -> None:
    for nombre in CATEGORIAS_DEFAULT:
        conn.execute(
            "INSERT OR IGNORE INTO categorias(nombre, activo) "
            "VALUES(?, 1)", (nombre,))


def _insertar_categorias_gastos_default(conn) -> None:
    for nombre in CATEGORIAS_GASTOS_DEFAULT:
        conn.execute(
            "INSERT OR IGNORE INTO categorias_gastos(nombre, activo) "
            "VALUES(?, 1)", (nombre,))


def _asegurar_defaults(conn) -> None:
    for k, v in {
        "umbral_verde_default":    "50",
        "umbral_amarillo_default": "20",
        "motivo_default_salida":   "Combos",
        "tema":                    "claro",
        "tasa_usd":                "1.0",
        "tasa_eur":                "1.0",
        "moneda_visualizacion":    "CUP",
        "pos_modo":                "opcional",
        "caja_obligatoria":        "0",
    }.items():
        conn.execute(
            "INSERT OR IGNORE INTO configuracion(clave,valor) VALUES(?,?)",
            (k, v))

    # Migración: si quedó "Venta" del P2 original → "Combos"
    row = conn.execute(
        "SELECT valor FROM configuracion "
        "WHERE clave='motivo_default_salida'"
    ).fetchone()
    if row and row["valor"] == "Venta":
        conn.execute(
            "UPDATE configuracion SET valor='Combos' "
            "WHERE clave='motivo_default_salida'"
        )


def _asegurar_almacen(conn) -> None:
    row = conn.execute(
        "SELECT 1 FROM locales WHERE es_almacen=1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO locales(nombre,es_almacen,activo,creado) "
            "VALUES('Almacén',1,1,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))


def _asegurar_columnas_extra(conn) -> None:
    """Añade columnas que pudieran faltar en BDs migradas."""
    for tabla, col, defn in (
        ("productos", "es_granel", "INTEGER NOT NULL DEFAULT 0"),
        ("movimientos", "proveedor_id", "INTEGER"),
    ):
        try:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass


def _asegurar_indices_extra(conn) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_local_fecha "
        "ON movimientos(local_id, fecha)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_tipo_motivo "
        "ON movimientos(tipo, motivo)")
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_proveedor "
        "ON movimientos(proveedor_id)")


def _asegurar_metodos_pago(conn) -> None:
    for (clave, etiqueta, activo, orden, req_mon, es_cred,
         cuenta, qr) in METODOS_PAGO_DEFAULT:
        conn.execute(
            "INSERT OR IGNORE INTO metodos_pago"
            "(clave,etiqueta,activo,orden,requiere_moneda,"
            "es_credito,cuenta,qr_imagen) VALUES(?,?,?,?,?,?,?,?)",
            (clave, etiqueta, activo, orden, req_mon, es_cred,
             cuenta, qr))


# ============================================================
# Preferencias
# ============================================================

def get_pref(clave: str) -> str | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT valor FROM configuracion WHERE clave=?", (clave,)
        ).fetchone()
        return row["valor"] if row else None


def set_pref(clave: str, valor: str) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO configuracion(clave,valor) VALUES(?,?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
            (clave, str(valor)))