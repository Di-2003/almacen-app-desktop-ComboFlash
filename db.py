"""
Esquema de la base de datos SQLite v6 (multi-local).

Tablas:
  - meta           → metadatos del sistema (versión del esquema)
  - locales        → Almacén + tiendas
  - usuarios       → quién puede usar la app y con qué rol
  - configuracion  → valores por defecto (umbrales, tema, etc.)
  - productos      → inventario por local (nombre único por local,
                     código único por local)
  - movimientos    → historial completo multi-local

'General' es una vista virtual (GENERAL_ID = -1), no se guarda en
`locales`.

Tipos de movimiento:
  ENTRADA, SALIDA, BAJA, RESTAURACION,
  TRASPASO_SALIDA, TRASPASO_ENTRADA, UMBRAL, AJUSTE

ZONA HORARIA: hora local del dispositivo (sin TZ).
"""
import sqlite3
from datetime import datetime
from rutas import DB_PATH

VERSION_ESQUEMA = 6
GENERAL_ID = -1


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

CREATE TABLE IF NOT EXISTS productos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id         INTEGER NOT NULL,
    codigo           TEXT COLLATE NOCASE,
    nombre           TEXT NOT NULL COLLATE NOCASE,
    stock            REAL NOT NULL DEFAULT 0,
    umbral_verde     INTEGER NOT NULL DEFAULT 50,
    umbral_amarillo  INTEGER NOT NULL DEFAULT 20,
    precio_costo     REAL NOT NULL DEFAULT 0,
    precio_unitario  REAL NOT NULL DEFAULT 0,
    fecha_ultima_mod TEXT NOT NULL,
    activo           INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(local_id) REFERENCES locales(id)
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_local_codigo
    ON productos(local_id, codigo)
    WHERE codigo IS NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS idx_prod_local_nombre
    ON productos(local_id, nombre);

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
    fecha                    TEXT NOT NULL,
    usuario                  TEXT NOT NULL,
    FOREIGN KEY(local_id) REFERENCES locales(id),
    FOREIGN KEY(producto_id) REFERENCES productos(id)
);

CREATE INDEX IF NOT EXISTS idx_mov_local    ON movimientos(local_id);
CREATE INDEX IF NOT EXISTS idx_mov_producto ON movimientos(producto_id);
CREATE INDEX IF NOT EXISTS idx_mov_fecha    ON movimientos(fecha);
CREATE INDEX IF NOT EXISTS idx_mov_grupo    ON movimientos(grupo_id);
CREATE INDEX IF NOT EXISTS idx_prod_local   ON productos(local_id);
CREATE INDEX IF NOT EXISTS idx_prod_activo  ON productos(activo);
"""


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def inicializar_db() -> None:
    """
    Crea el esquema si no existe. Si detecta una versión anterior,
    borra todo y arranca de cero. Asegura que exista 'Almacén'.
    """
    conn = get_conn()
    try:
        with conn:
            if _es_esquema_antiguo(conn):
                _dropear_todo(conn)

            conn.executescript(SCHEMA)
            _asegurar_defaults(conn)
            _asegurar_almacen(conn)
            _marcar_version(conn)
    finally:
        conn.close()


def _es_esquema_antiguo(conn) -> bool:
    try:
        row = conn.execute(
            "SELECT valor FROM meta WHERE clave='version_esquema'"
        ).fetchone()
        if row is None:
            return False
        return int(row["valor"]) < VERSION_ESQUEMA
    except sqlite3.OperationalError:
        try:
            cols = conn.execute("PRAGMA table_info(productos)").fetchall()
            nombres = {c["name"] for c in cols}
            return bool(nombres) and (
                "local_id" not in nombres or "codigo" not in nombres
            )
        except sqlite3.OperationalError:
            return False


def _dropear_todo(conn) -> None:
    for t in ("movimientos", "productos", "configuracion",
              "usuarios", "locales", "meta"):
        conn.execute(f"DROP TABLE IF EXISTS {t}")


def _asegurar_defaults(conn) -> None:
    for k, v in {
        "umbral_verde_default":    "50",
        "umbral_amarillo_default": "20",
        "motivo_default_salida":   "Venta",
        "tema":                    "oscuro",
        "tasa_usd":                "1.0",
        "tasa_eur":                "1.0",   # <-- NUEVO
    }.items():
        conn.execute(
            "INSERT OR IGNORE INTO configuracion(clave,valor) VALUES(?,?)",
            (k, v),
        )


def _asegurar_almacen(conn) -> None:
    row = conn.execute(
        "SELECT 1 FROM locales WHERE es_almacen=1"
    ).fetchone()
    if row is None:
        conn.execute(
            "INSERT INTO locales(nombre,es_almacen,activo,creado) "
            "VALUES('Almacén',1,1,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),),
        )


def _marcar_version(conn) -> None:
    conn.execute(
        "INSERT INTO meta(clave,valor) VALUES('version_esquema',?) "
        "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
        (str(VERSION_ESQUEMA),),
    )


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
            (clave, str(valor)),
        )