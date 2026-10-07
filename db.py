"""
Esquema de la base de datos SQLite v8.

PERFORMANCE:
  - WAL mode: escrituras sin bloquear lecturas.
  - synchronous=NORMAL: mucho más rápido que FULL.
  - cache_size=-20000: 20 MB de caché en memoria.
  - temp_store=MEMORY: tablas temporales en RAM.
  - Índices compuestos para agregaciones por período y local.
"""
import sqlite3
from datetime import datetime
from rutas import DB_PATH

VERSION_ESQUEMA = 8
GENERAL_ID = -1

MONEDAS_VALIDAS = ("CUP", "USD", "EUR")

CATEGORIAS_DEFAULT = (
    "Alimentos", "Bebidas", "Limpieza", "Aseo", "Electrónica",
)


SCHEMA = """
PRAGMA foreign_keys = ON;

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
    FOREIGN KEY(local_id) REFERENCES locales(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_local_codigo
    ON productos(local_id, codigo)
    WHERE codigo IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_local_nombre
    ON productos(local_id, nombre);

CREATE INDEX IF NOT EXISTS idx_prod_categoria ON productos(categoria_id);

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
CREATE INDEX IF NOT EXISTS idx_prod_local   ON productos(local_id);
CREATE INDEX IF NOT EXISTS idx_prod_activo  ON productos(activo);
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
            elif version < 7:
                _dropear_todo(conn)
                conn.executescript(SCHEMA)
                _insertar_categorias_default(conn)
            elif version == 7:
                _migrar_v7_a_v8(conn)

            _asegurar_defaults(conn)
            _asegurar_almacen(conn)
            _asegurar_indices_extra(conn)
            _marcar_version(conn)
    finally:
        conn.close()


def _asegurar_indices_extra(conn) -> None:
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_local_fecha "
        "ON movimientos(local_id, fecha)"
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_mov_tipo_motivo "
        "ON movimientos(tipo, motivo)"
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
    for t in ("movimientos", "productos", "configuracion",
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


def _insertar_categorias_default(conn) -> None:
    for nombre in CATEGORIAS_DEFAULT:
        conn.execute(
            "INSERT OR IGNORE INTO categorias(nombre, activo) "
            "VALUES(?, 1)", (nombre,))


def _asegurar_defaults(conn) -> None:
    for k, v in {
        "umbral_verde_default":    "50",
        "umbral_amarillo_default": "20",
        "motivo_default_salida":   "Venta",
        "tema":                    "oscuro",
        "tasa_usd":                "1.0",
        "tasa_eur":                "1.0",
        "moneda_visualizacion":    "CUP",
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