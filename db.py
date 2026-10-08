"""
Esquema de la base de datos SQLite v10.

NOVEDADES v10 (NO destructivas, conviven con v9):
  - categorias_gastos  → categorías de gastos operativos
  - gastos             → gastos operativos (con moneda + caja opcional)
  - proveedores        → CRUD proveedores (globales)
  - producto_proveedores → N:M producto↔proveedor (por nombre)
  - pagos_proveedor    → pagos / abonos a proveedores
  - movimientos.proveedor_id → de qué proveedor vino la ENTRADA

PERFORMANCE (sin cambios):
  WAL, synchronous=NORMAL, cache_size=-20000, temp_store=MEMORY,
  mmap_size=134217728, índices compuestos.
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
-- TABLAS v8 (sin cambios)
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
    ON productos(local_id, codigo)
    WHERE codigo IS NOT NULL;
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
-- TABLAS v9 (POS + clientes + caja + métodos de pago)
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
-- TABLAS v10 (Gastos + Proveedores)
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


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -20000")
    conn.execute("PRAGMA mmap_size = 134217728")
    return conn


# ============================================================
# Inicialización + migración
# ============================================================

def inicializar_db() -> None:
    conn = get_conn()
    try:
        with conn:
            version = _leer_version(conn)
            if version is None:
                conn.executescript(SCHEMA)
                _insertar_categorias_default(conn)
                _insertar_categorias_gastos_default(conn)
            elif version < 7:
                _dropear_todo(conn)
                conn.executescript(SCHEMA)
                _insertar_categorias_default(conn)
                _insertar_categorias_gastos_default(conn)
            elif version == 7:
                _migrar_v7_a_v8(conn)
                _migrar_v8_a_v9(conn)
                _migrar_v9_a_v10(conn)
            elif version == 8:
                _migrar_v8_a_v9(conn)
                _migrar_v9_a_v10(conn)
            elif version == 9:
                _migrar_v9_a_v10(conn)

            _asegurar_defaults(conn)
            _asegurar_almacen(conn)
            # IMPORTANTE: las columnas primero, luego los índices
            _asegurar_columnas_v9(conn)
            _asegurar_columnas_v10(conn)
            _asegurar_indices_extra(conn)
            _asegurar_metodos_pago(conn)
            _marcar_version(conn)
    finally:
        conn.close()

def _asegurar_columnas_v9(conn) -> None:
    for tabla, col, defn in (
        ("productos", "es_granel", "INTEGER NOT NULL DEFAULT 0"),
    ):
        try:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass


def _asegurar_columnas_v10(conn) -> None:
    """Añade columnas nuevas v10 a tablas existentes."""
    for tabla, col, defn in (
        ("movimientos", "proveedor_id", "INTEGER"),
    ):
        try:
            conn.execute(f"ALTER TABLE {tabla} ADD COLUMN {col} {defn}")
        except sqlite3.OperationalError:
            pass


def _asegurar_metodos_pago(conn) -> None:
    for (clave, etiqueta, activo, orden, req_mon, es_cred,
         cuenta, qr) in METODOS_PAGO_DEFAULT:
        conn.execute(
            "INSERT OR IGNORE INTO metodos_pago"
            "(clave,etiqueta,activo,orden,requiere_moneda,"
            "es_credito,cuenta,qr_imagen) VALUES(?,?,?,?,?,?,?,?)",
            (clave, etiqueta, activo, orden, req_mon, es_cred, cuenta, qr)
        )


def _asegurar_indices_extra(conn) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_local_fecha "
        "ON movimientos(local_id, fecha)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_tipo_motivo "
        "ON movimientos(tipo, motivo)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_proveedor "
        "ON movimientos(proveedor_id)"
    )


def _leer_version(conn):
    try:
        row = conn.execute(
            "SELECT valor FROM meta WHERE clave='version_esquema'"
        ).fetchone()
        if row is None:
            return None
        return int(row["valor"])
    except sqlite3.OperationalError:
        return None


def _dropear_todo(conn) -> None:
    for t in ("pagos_proveedor", "producto_proveedores",
              "proveedores",
              "gastos", "categorias_gastos",
              "devoluciones", "abonos", "pagos", "orden_items",
              "ordenes_venta", "clientes", "caja_sesiones",
              "metodos_pago",
              "movimientos", "productos", "configuracion",
              "usuarios", "locales", "categorias", "meta"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")


def _migrar_v7_a_v8(conn) -> None:
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS categorias (
            id      INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre  TEXT UNIQUE NOT NULL COLLATE NOCASE,
            activo  INTEGER NOT NULL DEFAULT 1
        );
    """)
    for sql in (
        "ALTER TABLE productos ADD COLUMN categoria_id INTEGER "
        "REFERENCES categorias(id)",
        "ALTER TABLE movimientos ADD COLUMN "
        "precio_costo_momento REAL NOT NULL DEFAULT 0",
    ):
        try:
            conn.execute(sql)
        except sqlite3.OperationalError:
            pass
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_prod_categoria "
        "ON productos(categoria_id)"
    )
    _insertar_categorias_default(conn)


def _migrar_v8_a_v9(conn) -> None:
    conn.executescript(SCHEMA)
    _insertar_categorias_default(conn)
    _asegurar_metodos_pago(conn)


def _migrar_v9_a_v10(conn) -> None:
    """Añade tablas v10 sin tocar datos de v9."""
    conn.executescript(SCHEMA)
    _insertar_categorias_gastos_default(conn)


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
        "motivo_default_salida":   "Venta",
        "tema":                    "oscuro",
        "paleta":                  "dorado",
        "tasa_usd":                "1.0",
        "tasa_eur":                "1.0",
        "moneda_visualizacion":    "CUP",
        "pos_modo":                "opcional",
        "caja_obligatoria":        "0",
    }.items():
        conn.execute(
            "INSERT OR IGNORE INTO configuracion(clave,valor) VALUES(?,?)",
            (k, v))


def _asegurar_almacen(conn) -> None:
    row = conn.execute(
        "SELECT 1 FROM locales WHERE es_almacen=1").fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO locales(nombre,es_almacen,activo,creado) "
            "VALUES('Almacén',1,1,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))


def _marcar_version(conn) -> None:
    conn.execute(
        "INSERT INTO meta(clave,valor) VALUES('version_esquema',?) "
        "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
        (str(VERSION_ESQUEMA),))


# ============ Helpers de configuración ============

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
        
