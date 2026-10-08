"""
Configuración del negocio (para tickets) + métodos de pago.
"""
from db import get_conn


CAMPOS_NEGOCIO = (
    ("nombre",   "Nombre comercial",             ""),
    ("direccion","Dirección",                    ""),
    ("telefono", "Teléfono",                     ""),
    ("nit",      "NIT / Carné",                  ""),
    ("eslogan",  "Eslogan o pie del ticket",     "¡Gracias por su compra!"),
    ("moneda",   "Moneda del ticket",            "CUP"),
)

CAMPOS_NEGOCIO_DICT = {k: (l, d) for k, l, d in CAMPOS_NEGOCIO}


def get_config_negocio(clave: str, default=None) -> str:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT valor FROM configuracion WHERE clave=?",
            (f"negocio_{clave}",)
        ).fetchone()
    if row:
        return row["valor"]
    if default is not None:
        return default
    return CAMPOS_NEGOCIO_DICT.get(clave, (None, ""))[1]


def set_config_negocio(clave: str, valor) -> None:
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO configuracion(clave,valor) VALUES(?,?) "
            "ON CONFLICT(clave) DO UPDATE SET valor=excluded.valor",
            (f"negocio_{clave}", str(valor or ""))
        )


def get_todos_negocio() -> dict:
    return {k: get_config_negocio(k) for k, _, _ in CAMPOS_NEGOCIO}


# ── Métodos de pago ──

def listar_metodos_pago(solo_activos: bool = False) -> list[dict]:
    sql = "SELECT * FROM metodos_pago"
    if solo_activos:
        sql += " WHERE activo=1"
    sql += " ORDER BY orden, etiqueta"
    with get_conn() as conn:
        return [dict(r) for r in conn.execute(sql).fetchall()]


def obtener_metodo_pago(clave) -> dict | None:
    if not clave:
        return None
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM metodos_pago WHERE clave=?", (clave,)
        ).fetchone()
        return dict(row) if row else None


def actualizar_metodo_pago(clave: str, activo=None, cuenta=None,
                           qr_imagen=None, etiqueta=None,
                           orden=None) -> None:
    campos, vals = [], []
    if activo is not None:
        campos.append("activo=?")
        vals.append(1 if activo else 0)
    if cuenta is not None:
        campos.append("cuenta=?")
        vals.append((cuenta or "").strip() or None)
    if qr_imagen is not None:
        campos.append("qr_imagen=?")
        vals.append((qr_imagen or "").strip() or None)
    if etiqueta is not None:
        campos.append("etiqueta=?")
        vals.append((etiqueta or "").strip())
    if orden is not None:
        campos.append("orden=?")
        vals.append(int(orden))
    if not campos:
        return
    vals.append(clave)
    with get_conn() as conn:
        conn.execute(
            f"UPDATE metodos_pago SET {', '.join(campos)} WHERE clave=?",
            tuple(vals)
        )


def crear_metodo_pago(clave, etiqueta, activo=0, orden=99,
                      requiere_moneda=0, es_credito=0,
                      cuenta=None, qr_imagen=None) -> None:
    clave = (clave or "").strip()
    etiqueta = (etiqueta or "").strip()
    if not clave or not etiqueta:
        raise ValueError("Clave y etiqueta son obligatorias")
    with get_conn() as conn:
        existe = conn.execute(
            "SELECT 1 FROM metodos_pago WHERE clave=?", (clave,)
        ).fetchone()
        if existe:
            raise ValueError(f"Ya existe el método «{clave}»")
        conn.execute(
            "INSERT INTO metodos_pago(clave,etiqueta,activo,orden,"
            "requiere_moneda,es_credito,cuenta,qr_imagen) "
            "VALUES(?,?,?,?,?,?,?,?)",
            (clave, etiqueta, 1 if activo else 0, int(orden),
            1 if requiere_moneda else 0, 1 if es_credito else 0,
            (cuenta or "").strip() or None,
            (qr_imagen or "").strip() or None)
        )


def eliminar_metodo_pago(clave: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM metodos_pago WHERE clave=?", (clave,))