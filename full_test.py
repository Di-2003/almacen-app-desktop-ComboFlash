"""
Test exhaustivo del sistema Almacén v10 (Combos Flash).

Ejecuta: python full_test.py
Usa una BD temporal para no tocar tu base de datos real.

Cobertura:
  - Seguridad (PBKDF2)
  - Esquema BD + migración
  - Categorías de producto y de gastos
  - Usuarios y roles
  - Locales (multi-local, cierre con traspaso)
  - Inventario (entrada, salida, traspaso, umbrales, códigos)
  - Multimoneda (CUP/USD/EUR, promedio ponderado)
  - Métricas y rangos de calendario
  - Clientes + cuentas por cobrar + abonos
  - POS (carrito, cobro, mixto, fiado, anulación, edición)
  - Editar pago (método, moneda, add/remove, preservar monto_cup)
  - Métodos simplificados con moneda_fija (Transfermóvil/EnZona → CUP,
    Zelle → USD, Efectivo/Tarjeta → libres)
  - Bloqueo de métodos duplicados en la misma orden
  - CAJA (apertura, cierre, gastos asociados)
  - Devoluciones (parcial, total, fuera de plazo)
  - Tickets (PDF/PNG/texto)
  - Gastos operativos (CRUD, multimoneda, filtros)
  - Proveedores (CRUD, N:M, pagos, saldo)
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime, timedelta

# ═══════════════════════════════════════════════════════════
# CONFIGURAR BD TEMPORAL ANTES DE IMPORTAR NADA
# ═══════════════════════════════════════════════════════════
_TEMP_DIR = tempfile.mkdtemp(prefix="almacen_test_")
os.environ["ALMACEN_DATA_DIR"] = _TEMP_DIR

import seguridad as seg
import categorias as cats
import locales as loc
import usuarios as um
import inventario as inv
import metricas as met
import clientes as cli
import ventas as ven
import caja as cj
import devoluciones as dev
import configuracion_negocio as cfg
import ticket as tk
import gastos as gs
import proveedores as pv

from db import (
    inicializar_db, get_conn, get_pref,
    VERSION_ESQUEMA, GENERAL_ID, MONEDAS_VALIDAS,
    METODOS_PAGO_DEFAULT,
)


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════
USR_ADMIN = {"id": 1, "username": "admin",       "rol": "admin"}
USR_ALM   = {"id": 2, "username": "almacenero",  "rol": "almacen"}
USR_COM   = {"id": 3, "username": "comun",       "rol": "comun"}


def _limpiar_todo():
    """Borra TODAS las tablas excepto meta (que guarda version_esquema)."""
    with get_conn() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for t in (
            "devoluciones", "abonos", "pagos", "orden_items",
            "ordenes_venta", "clientes", "caja_sesiones",
            "movimientos", "productos",
            "producto_proveedores", "pagos_proveedor", "proveedores",
            "gastos", "categorias_gastos",
            "configuracion", "metodos_pago",
            "usuarios", "locales", "categorias",
        ):
            try:
                conn.execute(f"DELETE FROM {t}")
            except Exception:
                pass
        conn.execute("PRAGMA foreign_keys = ON")


def _sembrar_basico():
    """Deja la BD con almacén + admin + categorías + métodos default."""
    with get_conn() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO usuarios(username,password_hash,"
            "salt,rol,activo,creado) VALUES('admin','x','x','admin',1,?)",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
        row = conn.execute(
            "SELECT 1 FROM locales WHERE es_almacen=1").fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO locales(nombre,es_almacen,activo,creado) "
                "VALUES('Almacén',1,1,?)",
                (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),))
        for nombre in ("Alimentos", "Bebidas", "Limpieza", "Aseo",
                       "Electrónica"):
            conn.execute(
                "INSERT OR IGNORE INTO categorias(nombre,activo) "
                "VALUES(?, 1)", (nombre,))
        for nombre in ("Luz", "Agua", "Alquiler", "Salario",
                       "Transporte", "Otros"):
            conn.execute(
                "INSERT OR IGNORE INTO categorias_gastos(nombre,activo) "
                "VALUES(?, 1)", (nombre,))
        for k, v in {
            "umbral_verde_default":    "50",
            "umbral_amarillo_default": "20",
            "motivo_default_salida":   "Combos",
            "tema":                    "oscuro",
            "paleta":                  "rojo",
            "tasa_usd":                "1.0",
            "tasa_eur":                "1.0",
            "moneda_visualizacion":    "CUP",
        }.items():
            conn.execute(
                "INSERT OR IGNORE INTO configuracion(clave,valor) "
                "VALUES(?,?)", (k, v))
        for (clave, etiqueta, activo, orden, req_mon, es_cred,
             cuenta, qr, moneda_fija) in METODOS_PAGO_DEFAULT:
            conn.execute(
                "INSERT OR IGNORE INTO metodos_pago"
                "(clave,etiqueta,activo,orden,requiere_moneda,"
                "es_credito,cuenta,qr_imagen,moneda_fija) "
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (clave, etiqueta, activo, orden, req_mon, es_cred,
                 cuenta, qr, moneda_fija))
        conn.execute("UPDATE metodos_pago SET activo=1")

def _crear_entrada(nombre, cantidad, codigo=None,
                   precio_costo=None, precio_unitario=None,
                   moneda="CUP", local_id=None):
    """Helper: crea entrada al almacén o local indicado."""
    if local_id is None:
        local_id = loc.obtener_almacen()["id"]
    return inv.registrar_entrada(
        nombre=nombre, cantidad=cantidad, usuario=USR_ADMIN,
        local_id=local_id, codigo=codigo,
        precio_costo=precio_costo, precio_unitario=precio_unitario,
        moneda=moneda,
    )


def _crear_venta_con_pago(moneda_pago="CUP", monto_pago=None,
                          tasa_pago=1.0, precio=1000.0,
                          metodo="Efectivo"):
    """Helper: crea un producto y una venta con un solo pago."""
    a = loc.obtener_almacen()
    codigo = f"FAE{abs(hash((moneda_pago, monto_pago, precio, metodo))) % 100000:05d}"
    nombre = f"Prod EditarPago {codigo}"
    _crear_entrada(nombre, 10, codigo=codigo, precio_unitario=precio)
    p = inv.buscar_producto_por_nombre(nombre, a["id"])

    if monto_pago is None:
        monto_pago = (precio / tasa_pago) if tasa_pago else precio

    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": metodo,
                "moneda": moneda_pago,
                "monto": monto_pago,
                "tasa": tasa_pago}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    return r["orden_id"], o["pagos"][0]


# ═══════════════════════════════════════════════════════════
# SEGURIDAD
# ═══════════════════════════════════════════════════════════

def test_hash_password():
    h, s = seg.crear_hash("mi_password_123")
    assert len(h) == 64
    assert len(s) == 32
    assert seg.verificar_password("mi_password_123", s, h)
    assert not seg.verificar_password("otra", s, h)


def test_hash_distintos():
    h1, s1 = seg.crear_hash("abc")
    h2, s2 = seg.crear_hash("abc")
    assert h1 != h2
    assert s1 != s2


def test_hash_password_vacio():
    h, s = seg.crear_hash("")
    assert seg.verificar_password("", s, h)
    assert not seg.verificar_password("x", s, h)


def test_hash_unicode():
    pw = "contraseña_con_ñ_y_áéíóú_日本語"
    h, s = seg.crear_hash(pw)
    assert seg.verificar_password(pw, s, h)


def test_hash_case_sensitive():
    h, s = seg.crear_hash("Password")
    assert seg.verificar_password("Password", s, h)
    assert not seg.verificar_password("password", s, h)


# ═══════════════════════════════════════════════════════════
# ESQUEMA BD
# ═══════════════════════════════════════════════════════════

def test_version_esquema():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT valor FROM meta WHERE clave='version_esquema'"
        ).fetchone()
    assert row is not None
    assert int(row["valor"]) == VERSION_ESQUEMA == 10


def test_almacen_creado():
    a = loc.obtener_almacen()
    assert a is not None
    assert a["es_almacen"] == 1
    assert a["nombre"] == "Almacén"


def test_categorias_default():
    cs = cats.listar_categorias(solo_activas=True)
    nombres = [c["nombre"] for c in cs]
    for esperado in ("Alimentos", "Bebidas", "Limpieza"):
        assert esperado in nombres


def test_config_defaults():
    assert get_pref("tasa_usd") is not None
    assert get_pref("moneda_visualizacion") == "CUP"


def test_get_conn_cierra_conexion():
    import sqlite3
    conn_ref = None
    with get_conn() as conn:
        conn_ref = conn
        conn.execute("SELECT 1")
    try:
        conn_ref.execute("SELECT 1")
    except sqlite3.ProgrammingError:
        return
    raise AssertionError(
        "BUG: get_conn() no cerró la conexión.")


# ═══════════════════════════════════════════════════════════
# CATEGORÍAS DE PRODUCTO
# ═══════════════════════════════════════════════════════════

def test_crear_categoria():
    cid = cats.crear_categoria("Juguetes")
    assert cid > 0
    c = cats.obtener_categoria(cid)
    assert c["nombre"] == "Juguetes"
    assert c["activo"] == 1


def test_normalizar_categoria():
    c = cats.buscar_por_nombre("ELECTRÓNICA")
    assert c is not None
    assert c["nombre"] == "Electrónica"


def test_categoria_duplicada():
    cats.crear_categoria("Ropa")
    try:
        cats.crear_categoria("ropa")
        assert False
    except ValueError:
        pass


def test_renombrar_categoria():
    cid = cats.crear_categoria("Muebles")
    cats.renombrar_categoria(cid, "mobiliario")
    c = cats.obtener_categoria(cid)
    assert c["nombre"] == "Mobiliario"


def test_desactivar_categoria():
    cid = cats.crear_categoria("Zapatos")
    cats.eliminar_categoria(cid)
    c = cats.obtener_categoria(cid)
    assert c["activo"] == 0
    activas = [x["id"] for x in cats.listar_categorias(solo_activas=True)]
    assert cid not in activas


def test_categoria_muy_corta():
    try:
        cats.crear_categoria("X")
        assert False
    except ValueError:
        pass


def test_categoria_vacia():
    try:
        cats.crear_categoria("")
        assert False
    except ValueError:
        pass


def test_categoria_solo_espacios():
    try:
        cats.crear_categoria("   ")
        assert False
    except ValueError:
        pass


# ═══════════════════════════════════════════════════════════
# USUARIOS
# ═══════════════════════════════════════════════════════════

def test_crear_usuario():
    uid = um.crear_usuario("test1", "pass1234", "comun",
                           solicitante=USR_ADMIN)
    assert uid > 0


def test_usuario_duplicado():
    um.crear_usuario("test2", "pass1234", "comun",
                     solicitante=USR_ADMIN)
    try:
        um.crear_usuario("test2", "otro1234", "comun",
                         solicitante=USR_ADMIN)
        assert False
    except um.UsuarioYaExiste:
        pass


def test_usuario_duplicado_case_insensitive():
    um.crear_usuario("TestCase", "pass1234", "comun",
                     solicitante=USR_ADMIN)
    try:
        um.crear_usuario("testcase", "pass1234", "comun",
                         solicitante=USR_ADMIN)
        assert False
    except um.UsuarioYaExiste:
        pass


def test_usuario_no_admin_falla():
    try:
        um.crear_usuario("test3", "pass1234", "comun",
                         solicitante=USR_ALM)
        assert False
    except PermissionError:
        pass


def test_comun_no_crea_usuarios():
    try:
        um.crear_usuario("test4", "pass1234", "comun",
                         solicitante=USR_COM)
        assert False
    except PermissionError:
        pass


def test_cambiar_rol():
    uid = um.crear_usuario("cambiar", "pass1234", "comun",
                           solicitante=USR_ADMIN)
    um.cambiar_rol(uid, "almacen", solicitante=USR_ADMIN)
    u = um.obtener_usuario(uid)
    assert u["rol"] == "almacen"


def test_password_corta():
    try:
        um.crear_usuario("corto", "12", "comun",
                         solicitante=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_rol_invalido():
    try:
        um.crear_usuario("rolmalo", "pass1234", "superadmin",
                         solicitante=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_resetear_password():
    uid = um.crear_usuario("resetuser", "vieja123", "comun",
                           solicitante=USR_ADMIN)
    um.resetear_password(uid, "nueva123", solicitante=USR_ADMIN)
    u = um.obtener_usuario(uid)
    assert seg.verificar_password("nueva123", u["salt"],
                                  u["password_hash"])


def test_no_eliminar_ultimo_admin():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM usuarios WHERE rol='admin' LIMIT 1"
        ).fetchone()
    if row:
        try:
            um.eliminar_usuario(row["id"], 9999, solicitante=USR_ADMIN)
            assert False
        except ValueError:
            pass


def test_no_eliminar_a_si_mismo():
    u = um.obtener_usuario(1)
    if u:
        try:
            um.eliminar_usuario(u["id"], u["id"], solicitante=USR_ADMIN)
            assert False
        except ValueError:
            pass


# ═══════════════════════════════════════════════════════════
# LOCALES
# ═══════════════════════════════════════════════════════════

def test_abrir_tienda():
    tid = loc.abrir_tienda("Tienda Centro")
    assert tid > 0
    t = loc.obtener_local(tid)
    assert t["nombre"] == "Tienda Centro"
    assert t["es_almacen"] == 0


def test_tienda_nombre_reservado():
    try:
        loc.abrir_tienda("General")
        assert False
    except ValueError:
        pass
    try:
        loc.abrir_tienda("Almacén")
        assert False
    except ValueError:
        pass


def test_tienda_duplicada():
    loc.abrir_tienda("Tienda Vedado")
    try:
        loc.abrir_tienda("Tienda Vedado")
        assert False
    except ValueError:
        pass


def test_listar_tiendas():
    ts = loc.listar_tiendas()
    assert len(ts) >= 2


def test_renombrar_local():
    tid = loc.abrir_tienda("Tienda Vieja")
    loc.renombrar_local(tid, "Tienda Nueva")
    t = loc.obtener_local(tid)
    assert t["nombre"] == "Tienda Nueva"


def test_no_cerrar_almacen():
    a = loc.obtener_almacen()
    try:
        loc.cerrar_tienda(a["id"], "admin")
        assert False
    except ValueError:
        pass


def test_cerrar_tienda_traspasa_stock():
    a = loc.obtener_almacen()
    tid = loc.abrir_tienda("Tienda Para Cerrar")
    _crear_entrada("Producto Cierre Test", 25, codigo="FA0700",
                   local_id=tid)
    stock_t = inv.buscar_producto_por_nombre(
        "Producto Cierre Test", tid)["stock"]
    assert stock_t == 25

    loc.cerrar_tienda(tid, "admin")

    t = loc.obtener_local(tid)
    assert t["activo"] == 0

    p_a = inv.buscar_producto_por_nombre("Producto Cierre Test",
                                          a["id"])
    assert p_a is not None
    assert p_a["stock"] == 25


def test_nombre_local():
    a = loc.obtener_almacen()
    assert loc.nombre_local(a["id"]) == "Almacén"
    assert loc.nombre_local(GENERAL_ID) == "General"


# ═══════════════════════════════════════════════════════════
# INVENTARIO
# ═══════════════════════════════════════════════════════════

def test_registrar_entrada_nuevo():
    a = loc.obtener_almacen()
    info = inv.registrar_entrada(
        nombre="Arroz", cantidad=100, usuario=USR_ADMIN,
        local_id=a["id"], codigo="FA0001",
        precio_costo=10, precio_unitario=20)
    assert info["stock"] == 100
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p is not None
    assert p["precio_costo"] == 10
    assert p["precio_unitario"] == 20


def test_entrada_suma_stock():
    a = loc.obtener_almacen()
    inv.registrar_entrada("Arroz", 50, USR_ADMIN, a["id"])
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p["stock"] == 150


def test_salida_resta_stock():
    a = loc.obtener_almacen()
    inv.registrar_salida("Arroz", 30, USR_ADMIN, a["id"],
                         motivo="Venta")
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p["stock"] == 120


def test_salida_stock_insuficiente():
    a = loc.obtener_almacen()
    try:
        inv.registrar_salida("Arroz", 99999, USR_ADMIN, a["id"])
        assert False
    except inv.StockInsuficiente:
        pass


def test_salida_producto_inexistente():
    a = loc.obtener_almacen()
    try:
        inv.registrar_salida("NoExiste", 1, USR_ADMIN, a["id"])
        assert False
    except inv.ProductoNoExiste:
        pass


def test_cantidad_negativa():
    a = loc.obtener_almacen()
    try:
        inv.registrar_entrada("X", -5, USR_ADMIN, a["id"])
        assert False
    except ValueError:
        pass


def test_cantidad_cero():
    a = loc.obtener_almacen()
    try:
        inv.registrar_entrada("X", 0, USR_ADMIN, a["id"])
        assert False
    except ValueError:
        pass


def test_comun_no_opera():
    a = loc.obtener_almacen()
    try:
        inv.registrar_entrada("X", 5, USR_COM, a["id"])
        assert False
    except PermissionError:
        pass


def test_general_no_operable():
    try:
        inv.registrar_entrada("X", 5, USR_ADMIN, GENERAL_ID)
        assert False
    except ValueError:
        pass


def test_codigo_auto_sugerido():
    a = loc.obtener_almacen()
    c = inv.siguiente_codigo(a["id"])
    assert c is not None
    assert c.startswith("F")


def test_codigo_global_propagado():
    a = loc.obtener_almacen()
    tid = loc.abrir_tienda("Tienda Código")
    inv.registrar_entrada("Arroz", 10, USR_ADMIN, tid,
                          codigo="FZ9999")
    p = inv.buscar_producto_por_nombre("Arroz", tid)
    assert p is not None
    assert p["codigo"] == "FA0001"


def test_codigo_duplicado_local():
    a = loc.obtener_almacen()
    _crear_entrada("Producto Código A", 10, codigo="FA5000")
    try:
        _crear_entrada("Producto Código B", 10, codigo="FA5000")
        assert False
    except ValueError:
        pass


def test_codigo_duplicado_global():
    a = loc.obtener_almacen()
    _crear_entrada("Producto Global A", 10, codigo="FA6000")
    try:
        _crear_entrada("Producto Global B", 10, codigo="FA6000")
        assert False
    except ValueError:
        pass


def test_traspaso():
    a = loc.obtener_almacen()
    tid = loc.abrir_tienda("Tienda Traspaso")
    inv.registrar_entrada("Azúcar", 100, USR_ADMIN, a["id"],
                          codigo="FA0050")
    stock_a = inv.buscar_producto_por_nombre("Azúcar", a["id"])["stock"]
    inv.registrar_traspaso("Azúcar", 30, USR_ADMIN, a["id"], tid)
    sa = inv.buscar_producto_por_nombre("Azúcar", a["id"])["stock"]
    st = inv.buscar_producto_por_nombre("Azúcar", tid)["stock"]
    assert sa == stock_a - 30
    assert st == 30


def test_traspaso_stock_insuficiente():
    a = loc.obtener_almacen()
    tid = loc.abrir_tienda("Tienda Traspaso 2")
    inv.registrar_entrada("Poco Stock", 5, USR_ADMIN, a["id"])
    try:
        inv.registrar_traspaso("Poco Stock", 100, USR_ADMIN,
                               a["id"], tid)
        assert False
    except inv.StockInsuficiente:
        pass


def test_traspaso_mismo_local():
    a = loc.obtener_almacen()
    try:
        inv.registrar_traspaso("Arroz", 5, USR_ADMIN, a["id"], a["id"])
        assert False
    except ValueError:
        pass


def test_traspaso_general():
    a = loc.obtener_almacen()
    try:
        inv.registrar_traspaso("Arroz", 5, USR_ADMIN, GENERAL_ID,
                               a["id"])
        assert False
    except ValueError:
        pass


def test_cambiar_umbrales():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    inv.cambiar_umbrales(p["id"], 80, 40, USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p2["umbral_verde"] == 80
    assert p2["umbral_amarillo"] == 40


def test_umbrales_invalidos():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    try:
        inv.cambiar_umbrales(p["id"], 10, 50, USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_umbrales_negativos():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    try:
        inv.cambiar_umbrales(p["id"], 50, -10, USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_dar_baja():
    a = loc.obtener_almacen()
    inv.registrar_entrada("Producto Baja", 20, USR_ADMIN, a["id"])
    p = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    inv.dar_baja(p["id"], USR_ADMIN, "Merma")
    p2 = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    assert p2["activo"] == 0


def test_dar_baja_dos_veces():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    try:
        inv.dar_baja(p["id"], USR_ADMIN, "Merma")
        assert False
    except ValueError:
        pass


def test_reactivar():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    inv.reactivar_producto(p["id"], USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    assert p2["activo"] == 1


def test_reactivar_ya_activo():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    try:
        inv.reactivar_producto(p["id"], USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_set_precio_costo():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    inv.set_precio_costo(p["id"], 15, "CUP", USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p2["precio_costo"] == 15


def test_set_precio_unitario():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    inv.set_precio_unitario(p["id"], 25, "CUP", USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p2["precio_unitario"] == 25


def test_color_stock():
    assert inv.color_stock(100, 50, 20) == "verde"
    assert inv.color_stock(30, 50, 20) == "amarillo"
    assert inv.color_stock(10, 50, 20) == "rojo"


def test_totales_local():
    a = loc.obtener_almacen()
    t = inv.totales_local(a["id"])
    assert "invertido" in t
    assert "venta_total" in t
    assert t["invertido"] >= 0


def test_renombrar_producto_propaga():
    a = loc.obtener_almacen()
    tid = loc.abrir_tienda("Tienda Renombrar")
    _crear_entrada("Producto Renombrar X", 10, codigo="FA7100")
    inv.registrar_traspaso("Producto Renombrar X", 5, USR_ADMIN,
                           a["id"], tid)
    p = inv.buscar_producto_por_nombre("Producto Renombrar X", a["id"])
    inv.renombrar_producto(p["id"], "Producto Renombrado Y", USR_ADMIN)
    p_a = inv.buscar_producto_por_nombre("Producto Renombrado Y",
                                          a["id"])
    p_t = inv.buscar_producto_por_nombre("Producto Renombrado Y", tid)
    assert p_a is not None
    assert p_t is not None


def test_renombrar_producto_duplicado():
    a = loc.obtener_almacen()
    _crear_entrada("Prod A Ren", 5, codigo="FA7200")
    _crear_entrada("Prod B Ren", 5, codigo="FA7201")
    p = inv.buscar_producto_por_nombre("Prod B Ren", a["id"])
    try:
        inv.renombrar_producto(p["id"], "Prod A Ren", USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_eliminar_movimiento_entrada():
    a = loc.obtener_almacen()
    _crear_entrada("Prod Eliminar Mov", 10, codigo="FA7300")
    p = inv.buscar_producto_por_nombre("Prod Eliminar Mov", a["id"])
    movs = inv.listar_movimientos(
        local_id=a["id"], producto_id=p["id"], limite=10)
    assert len(movs) >= 1
    mov_id = movs[0]["id"]
    stock_antes = float(p["stock"])
    inv.eliminar_movimiento(mov_id, USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Prod Eliminar Mov", a["id"])
    assert float(p2["stock"]) == stock_antes - 10


def test_editar_movimiento():
    a = loc.obtener_almacen()
    _crear_entrada("Prod Editar Mov", 20, codigo="FA7400")
    p = inv.buscar_producto_por_nombre("Prod Editar Mov", a["id"])
    movs = inv.listar_movimientos(
        local_id=a["id"], producto_id=p["id"], limite=10)
    mov_id = movs[0]["id"]
    inv.editar_movimiento(
        mov_id=mov_id, producto_id=p["id"], tipo="ENTRADA",
        cantidad=15, motivo=None,
        fecha=movs[0]["fecha"], usuario=USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Prod Editar Mov", a["id"])
    assert float(p2["stock"]) == 15


def test_buscar_productos_like():
    a = loc.obtener_almacen()
    _crear_entrada("Paleta Vainilla", 10, codigo="FA7500")
    _crear_entrada("Paleta Chocolate", 10, codigo="FA7501")
    _crear_entrada("Helado Vainilla", 10, codigo="FA7502")
    res = inv.buscar_productos_like("vaini", a["id"])
    nombres = [r["nombre"] for r in res]
    assert any("Vainilla" in n for n in nombres)


# ═══════════════════════════════════════════════════════════
# MULTIMONEDA + PROMEDIO PONDERADO
# ═══════════════════════════════════════════════════════════

def test_convertir_cup_a_usd():
    inv.set_config("tasa_usd", "100")
    r = inv.convertir(1000, "CUP", "USD")
    assert abs(r - 10) < 0.01


def test_convertir_usd_a_cup():
    inv.set_config("tasa_usd", "100")
    r = inv.convertir(5, "USD", "CUP")
    assert abs(r - 500) < 0.01


def test_convertir_misma_moneda():
    r = inv.convertir(100, "CUP", "CUP")
    assert r == 100


def test_convertir_tasa_cero_no_divide():
    inv.set_config("tasa_usd", "0")
    r = inv.de_cup(100, "USD")
    assert r == 100
    inv.set_config("tasa_usd", "1.0")


def test_promedio_ponderado_en_entrada():
    a = loc.obtener_almacen()
    _crear_entrada("Prod Promedio", 100, codigo="FA8000",
                   precio_costo=10)
    p = inv.buscar_producto_por_nombre("Prod Promedio", a["id"])
    assert p["precio_costo"] == 10

    _crear_entrada("Prod Promedio", 50, codigo="FA8000",
                   precio_costo=13)
    p2 = inv.buscar_producto_por_nombre("Prod Promedio", a["id"])
    esperado = (100 * 10 + 50 * 13) / 150
    assert abs(p2["precio_costo"] - esperado) < 0.01


def test_recalcular_precios():
    inv.set_config("tasa_usd", "150")
    n = inv.recalcular_todos_los_precios()
    assert n >= 0
    inv.set_config("tasa_usd", "1.0")


# ═══════════════════════════════════════════════════════════
# MÉTRICAS
# ═══════════════════════════════════════════════════════════

def test_rango_hoy():
    d, h = met.rango_calendario("hoy")
    assert d < h
    assert d.endswith("00:00:00")


def test_rango_semana():
    d, h = met.rango_calendario("semana")
    assert d < h


def test_rango_mes():
    d, h = met.rango_calendario("mes")
    assert d < h


def test_rango_anio():
    d, h = met.rango_calendario("anio")
    assert d < h


def test_rango_total():
    d, h = met.rango_calendario("total")
    assert d.startswith("0000")


def test_resumen_periodo():
    a = loc.obtener_almacen()
    r = met.resumen_periodo(a["id"], "total")
    assert "vendido" in r
    assert "ganancia" in r
    assert "n_ventas" in r

def test_estancados_no_solapa_con_vendidos():
    """
    INVARIANTE: ningún producto con venta reciente (motivo 'Venta'
    o 'Combos', orden no anulada) debe aparecer como estancado.
    """
    a = loc.obtener_almacen()
    estancados = met.productos_estancados(a["id"], dias=30,
                                            limite=9999)
    estancados_ids = {p["id"] for p in estancados}

    fecha_limite = (
        datetime.now() - timedelta(days=30)
    ).strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        vendidos = conn.execute(f"""
            SELECT DISTINCT m.producto_id
            FROM movimientos m
            WHERE m.tipo='SALIDA'
              AND {met.SQL_ES_VENTA}
              AND m.fecha >= ?
              AND {met.SQL_NO_ANULADA}
        """, (fecha_limite,)).fetchall()
    vendidos_ids = {r["producto_id"] for r in vendidos}

    solap = estancados_ids & vendidos_ids
    assert not solap, (
        f"Solapamiento estancados↔vendidos: {solap}")


def test_todos_los_activos_clasificados():
    """
    Todo producto activo con stock > 0 debe estar o en la lista
    de vendidos recientes o en la de estancados. Si no está en
    ninguna, hay un bug.
    """
    a = loc.obtener_almacen()
    estancados = met.productos_estancados(a["id"], dias=30,
                                            limite=9999)
    estancados_ids = {p["id"] for p in estancados}

    fecha_limite = (
        datetime.now() - timedelta(days=30)
    ).strftime("%Y-%m-%d %H:%M:%S")

    with get_conn() as conn:
        todos = conn.execute("""
            SELECT id FROM productos
            WHERE activo=1 AND stock > 0 AND local_id=?
        """, (a["id"],)).fetchall()
        todos_ids = {r["id"] for r in todos}

        vendidos = conn.execute(f"""
            SELECT DISTINCT m.producto_id
            FROM movimientos m
            WHERE m.tipo='SALIDA'
              AND {met.SQL_ES_VENTA}
              AND m.fecha >= ?
              AND {met.SQL_NO_ANULADA}
        """, (fecha_limite,)).fetchall()
    vendidos_ids = {r["producto_id"] for r in vendidos}

    sin_clasificar = todos_ids - estancados_ids - vendidos_ids
    assert not sin_clasificar, (
        f"Productos sin clasificar: {sin_clasificar}")


# ═══════════════════════════════════════════════════════════
# CLIENTES
# ═══════════════════════════════════════════════════════════

def test_crear_cliente():
    cid = cli.crear_cliente("María Pérez", telefono="5551234")
    assert cid > 0
    c = cli.obtener_cliente(cid)
    assert c["nombre"] == "María Pérez"


def test_cliente_duplicado():
    try:
        cli.crear_cliente("María Pérez")
        assert False
    except ValueError:
        pass


def test_editar_cliente():
    c = cli.listar_clientes()[0]
    cli.editar_cliente(c["id"], telefono="5559999")
    assert cli.obtener_cliente(c["id"])["telefono"] == "5559999"


def test_buscar_cliente():
    r = cli.listar_clientes(texto="maría")
    assert len(r) >= 1


def test_cliente_sin_deuda():
    c = cli.listar_clientes()[0]
    assert cli.saldo_pendiente(c["id"]) == 0


def test_cliente_nombre_corto():
    try:
        cli.crear_cliente("X")
        assert False
    except ValueError:
        pass


def test_cliente_nombre_vacio():
    try:
        cli.crear_cliente("")
        assert False
    except ValueError:
        pass


# ═══════════════════════════════════════════════════════════
# MÉTODOS DE PAGO
# ═══════════════════════════════════════════════════════════

def test_metodos_default():
    ms = cfg.listar_metodos_pago(solo_activos=False)
    assert len(ms) >= 6
    claves = [m["clave"] for m in ms]
    assert "Efectivo" in claves
    assert "Transfermóvil" in claves
    assert "Fiado" in claves


def test_metodos_nuevos_default():
    """Solo 6 métodos base con moneda_fija."""
    ms = {m["clave"]: m for m in
          cfg.listar_metodos_pago(solo_activos=False)}
    for clave in ("Efectivo", "Transfermóvil", "EnZona",
                  "Zelle", "Tarjeta", "Fiado"):
        assert clave in ms, f"Falta {clave}"
    for viejo in ("Efectivo CUP", "Efectivo USD",
                  "Efectivo EUR", "Efectivo MLC"):
        assert viejo not in ms, f"Debería haberse migrado: {viejo}"


def test_moneda_fija_por_metodo():
    from configuracion_negocio import moneda_efectiva_metodo
    m = cfg.obtener_metodo_pago("Transfermóvil")
    assert moneda_efectiva_metodo(m) == "CUP"
    m = cfg.obtener_metodo_pago("EnZona")
    assert moneda_efectiva_metodo(m) == "CUP"
    m = cfg.obtener_metodo_pago("Zelle")
    assert moneda_efectiva_metodo(m) == "USD"
    m = cfg.obtener_metodo_pago("Efectivo")
    assert moneda_efectiva_metodo(m) is None
    m = cfg.obtener_metodo_pago("Tarjeta")
    assert moneda_efectiva_metodo(m) is None
    m = cfg.obtener_metodo_pago("Fiado")
    assert moneda_efectiva_metodo(m) is None


def test_toggle_metodo():
    """Toggle: activa y desactiva, pero deja el método en su
    estado original al terminar."""
    m_antes = cfg.obtener_metodo_pago("Tarjeta")
    activo_antes = bool(m_antes["activo"])

    # Toggle 1
    cfg.actualizar_metodo_pago("Tarjeta",
                               activo=not activo_antes)
    m = cfg.obtener_metodo_pago("Tarjeta")
    assert bool(m["activo"]) != activo_antes

    # Toggle 2 (volver al estado original)
    cfg.actualizar_metodo_pago("Tarjeta", activo=activo_antes)
    m = cfg.obtener_metodo_pago("Tarjeta")
    assert bool(m["activo"]) == activo_antes


def test_actualizar_cuenta_metodo():
    cfg.actualizar_metodo_pago("Transfermóvil",
                               cuenta="+53 5555 0000")
    m = cfg.obtener_metodo_pago("Transfermóvil")
    assert m["cuenta"] == "+53 5555 0000"


# ═══════════════════════════════════════════════════════════
# POS — CARRITO
# ═══════════════════════════════════════════════════════════

def test_carrito_vacio():
    c = ven.nuevo_carrito()
    assert c["items"] == []
    assert c["cliente_id"] is None


def test_agregar_item():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    assert len(c["items"]) == 1
    assert c["items"][0]["cantidad"] == 5


def test_agregar_mismo_producto_suma():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    ven.agregar_item(c, p, 3)
    assert len(c["items"]) == 1
    assert c["items"][0]["cantidad"] == 8


def test_agregar_cantidad_cero():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    try:
        ven.agregar_item(c, p, 0)
        assert False
    except ValueError:
        pass


def test_agregar_cantidad_negativa():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    try:
        ven.agregar_item(c, p, -1)
        assert False
    except ValueError:
        pass


def test_agregar_mas_que_stock():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    try:
        ven.agregar_item(c, p, p["stock"] + 1)
        assert False
    except ValueError:
        pass


def test_calcular_totales():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 2)
    t = ven.calcular_totales(c)
    assert abs(t["total"] - p["precio_unitario"] * 2) < 0.01


def test_descuento_global():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 10)
    c["descuento_global_pct"] = 10
    t = ven.calcular_totales(c)
    esperado = p["precio_unitario"] * 10 * 0.9
    assert abs(t["total"] - esperado) < 0.01


def test_editar_item_carrito():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    ven.editar_item(c, 0, cantidad=5)
    assert c["items"][0]["cantidad"] == 5


def test_editar_item_rebaja_mayor_precio():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    try:
        ven.editar_item(c, 0, rebaja=p["precio_unitario"] + 100)
        assert False
    except ValueError:
        pass


def test_eliminar_item_carrito():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    ven.eliminar_item(c, 0)
    assert len(c["items"]) == 0


# ═══════════════════════════════════════════════════════════
# POS — VENTAS
# ═══════════════════════════════════════════════════════════

def test_venta_simple():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    assert r["total"] == t["total"]
    assert r["estado"] == "pagada"
    assert r["saldo_pendiente"] == 0


def test_venta_pago_mixto():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 4)
    t = ven.calcular_totales(c)
    mitad = t["total"] / 2
    r = ven.registrar_venta(
        carrito=c,
        pagos=[
            {"metodo": "Efectivo", "moneda": "CUP",
             "monto": mitad, "tasa": 1.0},
            {"metodo": "Transfermóvil", "moneda": "CUP",
             "monto": t["total"] - mitad, "tasa": 1.0},
        ],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    assert len(o["pagos"]) == 2


def test_venta_pago_insuficiente():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 10)
    try:
        ven.registrar_venta(
            carrito=c,
            pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                    "monto": 0.01, "tasa": 1.0}],
            usuario=USR_ADMIN, local_id=a["id"])
        assert False
    except ValueError:
        pass


def test_venta_max_3_pagos():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 10)
    t = ven.calcular_totales(c)
    try:
        ven.registrar_venta(
            carrito=c,
            pagos=[
                {"metodo": "Efectivo", "moneda": "CUP",
                 "monto": t["total"] / 4, "tasa": 1.0},
                {"metodo": "Transfermóvil", "moneda": "CUP",
                 "monto": t["total"] / 4, "tasa": 1.0},
                {"metodo": "EnZona", "moneda": "CUP",
                 "monto": t["total"] / 4, "tasa": 1.0},
                {"metodo": "Tarjeta", "moneda": "CUP",
                 "monto": t["total"] / 4, "tasa": 1.0},
            ],
            usuario=USR_ADMIN, local_id=a["id"])
        assert False
    except ValueError:
        pass


def test_venta_carrito_vacio():
    a = loc.obtener_almacen()
    c = ven.nuevo_carrito()
    try:
        ven.registrar_venta(
            carrito=c,
            pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                    "monto": 100, "tasa": 1.0}],
            usuario=USR_ADMIN, local_id=a["id"])
        assert False
    except ValueError:
        pass


def test_venta_fiado_requiere_cliente():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    t = ven.calcular_totales(c)
    try:
        ven.registrar_venta(
            carrito=c,
            pagos=[{"metodo": "Fiado", "moneda": "CUP",
                    "monto": t["total"], "tasa": 1.0}],
            usuario=USR_ADMIN, local_id=a["id"])
        assert False
    except ValueError as ex:
        assert "cliente" in str(ex).lower()


def test_venta_fiado_y_abonos():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    cid = cli.crear_cliente("Fiado Test 2")
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    c["cliente_id"] = cid
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Fiado", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    assert r["estado"] == "pendiente"
    assert abs(cli.saldo_pendiente(cid) - t["total"]) < 0.01
    cli.registrar_abono(
        orden_id=r["orden_id"], monto=t["total"] / 2, moneda="CUP",
        metodo="Efectivo", usuario=USR_ADMIN)
    o = ven.obtener_orden(r["orden_id"])
    assert o["estado"] == "parcial"
    cli.registrar_abono(
        orden_id=r["orden_id"], monto=t["total"] / 2, moneda="CUP",
        metodo="Efectivo", usuario=USR_ADMIN)
    assert cli.saldo_pendiente(cid) == 0


def test_abono_mayor_con_vuelto_cero_es_propina():
    """Abono > saldo con vuelto=0 → guarda el sobrante como propina."""
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    cid = cli.crear_cliente("Cliente Propina")
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 2)
    c["cliente_id"] = cid
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Fiado", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])

    # Abono el doble del saldo, vuelto = 0 → propina
    cli.registrar_abono(
        orden_id=r["orden_id"],
        monto=t["total"] * 2,
        moneda="CUP",
        metodo="Efectivo",
        usuario=USR_ADMIN,
        vuelto=0.0)

    o = ven.obtener_orden(r["orden_id"])
    assert o["estado"] == "pagada"
    assert abs(o["saldo_pendiente"]) < 0.01
    assert cli.saldo_pendiente(cid) == 0


def test_abono_con_vuelto_no_aplica_el_sobrante():
    """Abono con vuelto: solo la parte sin vuelto reduce el saldo."""
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    cid = cli.crear_cliente("Cliente Vuelto")
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 2)
    c["cliente_id"] = cid
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Fiado", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])

    # Abono el doble, la mitad como vuelto → el abono efectivo
    # iguala el saldo
    cli.registrar_abono(
        orden_id=r["orden_id"],
        monto=t["total"] * 2,
        moneda="CUP",
        metodo="Efectivo",
        usuario=USR_ADMIN,
        vuelto=t["total"])

    o = ven.obtener_orden(r["orden_id"])
    assert o["estado"] == "pagada"
    assert abs(o["saldo_pendiente"]) < 0.01

def test_venta_anular_restaura_stock():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    stock_antes = p["stock"]
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    ven.anular_orden(r["orden_id"], USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p2["stock"] == stock_antes
    o = ven.obtener_orden(r["orden_id"])
    assert o["estado"] == "anulada"


def test_anular_orden_dos_veces():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    ven.anular_orden(r["orden_id"], USR_ADMIN)
    try:
        ven.anular_orden(r["orden_id"], USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_venta_stock_insuficiente():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])

    c = ven.nuevo_carrito()
    try:
        ven.agregar_item(c, p, p["stock"] + 99999)
        assert False
    except ValueError:
        pass

    c2 = ven.nuevo_carrito()
    ven.agregar_item(c2, p, 1)
    c2["items"][0]["cantidad"] = p["stock"] + 99999
    t = ven.calcular_totales(c2)
    try:
        ven.registrar_venta(
            carrito=c2,
            pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                    "monto": t["total"], "tasa": 1.0}],
            usuario=USR_ADMIN, local_id=a["id"])
        assert False
    except ValueError:
        pass


def test_venta_metodo_invalido():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    try:
        ven.registrar_venta(
            carrito=c,
            pagos=[{"metodo": "Pago Inexistente", "moneda": "CUP",
                    "monto": t["total"], "tasa": 1.0}],
            usuario=USR_ADMIN, local_id=a["id"])
        assert False
    except ValueError:
        pass


def test_vuelto_calculado():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"] + 100, "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    assert r["vuelto"] >= 100 - 0.01


def test_venta_zelle_fuerza_usd():
    """Zelle tiene moneda_fija='USD'. Debe forzarse aunque se pase CUP."""
    inv.set_config("tasa_usd", "100")
    try:
        a = loc.obtener_almacen()
        _crear_entrada("Prod Zelle Forzado", 5, codigo="FAE810",
                       precio_unitario=2000)
        p = inv.buscar_producto_por_nombre("Prod Zelle Forzado", a["id"])
        c = ven.nuevo_carrito()
        ven.agregar_item(c, p, 1)
        t = ven.calcular_totales(c)
        r = ven.registrar_venta(
            carrito=c,
            pagos=[{"metodo": "Zelle", "moneda": "CUP",  # ← se ignora
                    "monto": t["total"] / 100, "tasa": 100.0}],
            usuario=USR_ADMIN, local_id=a["id"])
        o = ven.obtener_orden(r["orden_id"])
        assert o["pagos"][0]["moneda"] == "USD"
    finally:
        inv.set_config("tasa_usd", "1.0")


def test_venta_transfermovil_fuerza_cup():
    """Transfermóvil tiene moneda_fija='CUP'."""
    a = loc.obtener_almacen()
    _crear_entrada("Prod Transfer Forzado", 5, codigo="FAE811",
                   precio_unitario=1000)
    p = inv.buscar_producto_por_nombre("Prod Transfer Forzado", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Transfermóvil", "moneda": "USD",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    assert o["pagos"][0]["moneda"] == "CUP"


# ═══════════════════════════════════════════════════════════
# POS — EDICIÓN DE ÓRDENES
# ═══════════════════════════════════════════════════════════

def test_editar_items_orden_cambiar_cantidad():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    item = o["items"][0]
    nuevos = [{
        "producto_id": item["producto_id"],
        "nombre": item["nombre"],
        "codigo": item["codigo"],
        "cantidad": 3,
        "precio_unitario": item["precio_unitario"],
        "rebaja": 0,
    }]
    ven.editar_items_orden(r["orden_id"], nuevos, USR_ADMIN)
    o2 = ven.obtener_orden(r["orden_id"])
    assert o2["items"][0]["cantidad"] == 3


def test_editar_items_orden_quitar_todo():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    try:
        ven.editar_items_orden(r["orden_id"], [], USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_editar_orden_anulada():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 2)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    ven.anular_orden(r["orden_id"], USR_ADMIN)
    nuevos = [{
        "producto_id": p["id"],
        "nombre": p["nombre"],
        "codigo": p["codigo"],
        "cantidad": 1,
        "precio_unitario": p["precio_unitario"],
        "rebaja": 0,
    }]
    try:
        ven.editar_items_orden(r["orden_id"], nuevos, USR_ADMIN)
        assert False
    except ValueError:
        pass


# ═══════════════════════════════════════════════════════════
# EDITAR PAGO — método, moneda, add/remove
# ═══════════════════════════════════════════════════════════

def test_regresion_editar_metodo_pago():
    """Regresión: cambiar método NO debe fallar."""
    a = loc.obtener_almacen()
    _crear_entrada("Test pago individual", 5, codigo="FA9500",
                   precio_unitario=100)
    p = inv.buscar_producto_por_nombre("Test pago individual", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    pago_id = o["pagos"][0]["id"]

    ven.editar_pago(pago_id=pago_id,
                    nuevo_metodo="Transfermóvil",
                    usuario=USR_ADMIN)
    o2 = ven.obtener_orden(r["orden_id"])
    assert o2["pagos"][0]["metodo"] == "Transfermóvil"


def test_editar_pago_solo_metodo():
    _, pago = _crear_venta_con_pago("CUP", monto_pago=1000.0,
                                    tasa_pago=1.0, precio=1000.0)
    ven.editar_pago(pago_id=pago["id"],
                    nuevo_metodo="Transfermóvil",
                    usuario=USR_ADMIN)
    with get_conn() as conn:
        p2 = dict(conn.execute(
            "SELECT * FROM pagos WHERE id=?", (pago["id"],)
        ).fetchone())
    assert p2["metodo"] == "Transfermóvil"
    assert p2["moneda"] == "CUP"
    assert abs(float(p2["monto_cup"]) - float(pago["monto_cup"])) < 0.01


def test_editar_pago_usd_a_cup_preserva_monto_cup():
    inv.set_config("tasa_usd", "100")
    try:
        _, pago = _crear_venta_con_pago(
            "USD", monto_pago=10.0, tasa_pago=100.0, precio=1000.0)
        monto_cup_antes = float(pago["monto_cup"])
        ven.editar_pago(pago_id=pago["id"],
                        nuevo_metodo="Efectivo",
                        nueva_moneda="CUP",
                        usuario=USR_ADMIN)
        with get_conn() as conn:
            p2 = dict(conn.execute(
                "SELECT * FROM pagos WHERE id=?", (pago["id"],)
            ).fetchone())
        assert p2["moneda"] == "CUP"
        assert abs(float(p2["monto"]) - 1000.0) < 0.01
        assert abs(float(p2["monto_cup"]) - monto_cup_antes) < 0.01
    finally:
        inv.set_config("tasa_usd", "1.0")


def test_editar_pago_cup_a_usd_preserva_monto_cup():
    inv.set_config("tasa_usd", "100")
    try:
        _, pago = _crear_venta_con_pago(
            "CUP", monto_pago=1000.0, tasa_pago=1.0, precio=1000.0)
        ven.editar_pago(pago_id=pago["id"],
                        nuevo_metodo="Efectivo",
                        nueva_moneda="USD",
                        usuario=USR_ADMIN)
        with get_conn() as conn:
            p2 = dict(conn.execute(
                "SELECT * FROM pagos WHERE id=?", (pago["id"],)
            ).fetchone())
        assert p2["moneda"] == "USD"
        assert abs(float(p2["monto"]) - 10.0) < 0.01
        assert abs(float(p2["monto_cup"]) - 1000.0) < 0.01
    finally:
        inv.set_config("tasa_usd", "1.0")


def test_editar_pago_usd_a_eur_preserva_monto_cup():
    inv.set_config("tasa_usd", "100")
    inv.set_config("tasa_eur", "130")
    try:
        _, pago = _crear_venta_con_pago(
            "USD", monto_pago=20.0, tasa_pago=100.0, precio=2000.0)
        monto_cup_antes = float(pago["monto_cup"])
        ven.editar_pago(pago_id=pago["id"],
                        nuevo_metodo="Efectivo",
                        nueva_moneda="EUR",
                        usuario=USR_ADMIN)
        with get_conn() as conn:
            p2 = dict(conn.execute(
                "SELECT * FROM pagos WHERE id=?", (pago["id"],)
            ).fetchone())
        assert p2["moneda"] == "EUR"
        # 2000 CUP / 130 = 15.38... -> redondeo al alza -> 16.00 EUR
        assert abs(float(p2["monto"]) - 16.0) < 0.01
        # 16.00 * 130 = 2080. Como el total de la orden es 2000, 
        # monto_cup se topa a 2000 y se generan 80 CUP de vuelto.
        assert abs(float(p2["monto_cup"]) - 2000.0) < 0.01
        assert abs(float(p2["vuelto_cup"]) - 80.0) < 0.01
    finally:
        inv.set_config("tasa_usd", "1.0")
        inv.set_config("tasa_eur", "1.0")

def test_editar_pago_preserva_monto_cup_siempre():
    inv.set_config("tasa_usd", "100")
    inv.set_config("tasa_eur", "130")
    try:
        _, pago = _crear_venta_con_pago(
            "CUP", monto_pago=1000.0, tasa_pago=1.0, precio=1000.0)
        # Al cambiar de moneda, ahora se redondea al alza.
        for met, mon in (
            ("Efectivo", "USD"),
            ("Efectivo", "EUR"),
            ("Tarjeta", "USD"),
            ("Transfermóvil", None),
            ("Zelle", None),
            ("Efectivo", "CUP"),
        ):
            ven.editar_pago(pago_id=pago["id"],
                            nuevo_metodo=met,
                            nueva_moneda=mon,
                            usuario=USR_ADMIN)
            with get_conn() as conn:
                p2 = dict(conn.execute(
                    "SELECT * FROM pagos WHERE id=?", (pago["id"],)
                ).fetchone())
            # El monto_cup se mantiene igual o mayor por el redondeo
            assert float(p2["monto_cup"]) >= 1000.0
    finally:
        inv.set_config("tasa_usd", "1.0")
        inv.set_config("tasa_eur", "1.0")

def test_editar_pago_transfermovil_fuerza_cup():
    """Transfermóvil fuerza moneda a CUP aunque se pase USD."""
    inv.set_config("tasa_usd", "100")
    try:
        _, pago = _crear_venta_con_pago(
            "USD", monto_pago=10.0, tasa_pago=100.0, precio=1000.0)
        ven.editar_pago(pago_id=pago["id"],
                        nuevo_metodo="Transfermóvil",
                        nueva_moneda="USD",  # ← se ignora
                        usuario=USR_ADMIN)
        with get_conn() as conn:
            p2 = dict(conn.execute(
                "SELECT * FROM pagos WHERE id=?", (pago["id"],)
            ).fetchone())
        assert p2["moneda"] == "CUP"
        assert abs(float(p2["monto"]) - 1000.0) < 0.01
        assert abs(float(p2["monto_cup"]) - 1000.0) < 0.01
    finally:
        inv.set_config("tasa_usd", "1.0")


def test_editar_pago_zelle_fuerza_usd():
    """Zelle fuerza moneda a USD aunque se pase CUP."""
    inv.set_config("tasa_usd", "100")
    try:
        _, pago = _crear_venta_con_pago(
            "CUP", monto_pago=1000.0, tasa_pago=1.0, precio=1000.0)
        ven.editar_pago(pago_id=pago["id"],
                        nuevo_metodo="Zelle",
                        nueva_moneda="CUP",  # ← se ignora
                        usuario=USR_ADMIN)
        with get_conn() as conn:
            p2 = dict(conn.execute(
                "SELECT * FROM pagos WHERE id=?", (pago["id"],)
            ).fetchone())
        assert p2["moneda"] == "USD"
        assert abs(float(p2["monto"]) - 10.0) < 0.01
        assert abs(float(p2["monto_cup"]) - 1000.0) < 0.01
    finally:
        inv.set_config("tasa_usd", "1.0")


def test_regresion_editar_pago_no_descuadra_caja():
    """
    REGRESIÓN: al editar un pago y cambiar su moneda, el `monto_cup`
    DEBE permanecer idéntico. Aunque la tasa USD cambie entre la
    venta y la edición.
    """
    inv.set_config("tasa_usd", "100")
    try:
        _, pago = _crear_venta_con_pago(
            "USD", monto_pago=50.0, tasa_pago=100.0, precio=5000.0)
        monto_cup_antes = float(pago["monto_cup"])
        # El dólar sube (inflación)
        inv.set_config("tasa_usd", "120")

        ven.editar_pago(pago_id=pago["id"],
                        nuevo_metodo="Efectivo",
                        nueva_moneda="CUP",
                        usuario=USR_ADMIN)
        with get_conn() as conn:
            p2 = dict(conn.execute(
                "SELECT * FROM pagos WHERE id=?", (pago["id"],)
            ).fetchone())
        monto_cup_despues = float(p2["monto_cup"])
        assert abs(monto_cup_despues - monto_cup_antes) < 0.01, (
            f"BUG: caja descuadrada. Antes: {monto_cup_antes}, "
            f"después: {monto_cup_despues}")
    finally:
        inv.set_config("tasa_usd", "1.0")


def test_regresion_editar_pago_idempotente():
    """Ciclos de cambio de moneda no acumulan distorsión."""
    inv.set_config("tasa_usd", "100")
    try:
        _, pago = _crear_venta_con_pago(
            "CUP", monto_pago=1000.0, tasa_pago=1.0, precio=1000.0)
        monto_cup_inicial = float(pago["monto_cup"])
        for moneda in ("USD", "CUP", "USD", "CUP"):
            ven.editar_pago(pago_id=pago["id"],
                            nuevo_metodo="Efectivo",
                            nueva_moneda=moneda,
                            usuario=USR_ADMIN)
        with get_conn() as conn:
            p2 = dict(conn.execute(
                "SELECT * FROM pagos WHERE id=?", (pago["id"],)
            ).fetchone())
        monto_cup_final = float(p2["monto_cup"])
        assert abs(monto_cup_final - monto_cup_inicial) < 0.01
    finally:
        inv.set_config("tasa_usd", "1.0")


def test_cambiar_metodo_pago_wrapper():
    _, pago = _crear_venta_con_pago(
        "CUP", monto_pago=100.0, tasa_pago=1.0, precio=100.0)
    ven.cambiar_metodo_pago(pago["id"], "Transfermóvil", USR_ADMIN)
    with get_conn() as conn:
        p2 = dict(conn.execute(
            "SELECT * FROM pagos WHERE id=?", (pago["id"],)
        ).fetchone())
    assert p2["metodo"] == "Transfermóvil"
    assert abs(float(p2["monto_cup"]) - 100.0) < 0.01


def test_editar_pago_inexistente():
    try:
        ven.editar_pago(pago_id=9999999,
                        nuevo_metodo="Efectivo",
                        usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_editar_pago_metodo_invalido():
    _, pago = _crear_venta_con_pago(
        "CUP", monto_pago=100.0, tasa_pago=1.0, precio=100.0)
    try:
        ven.editar_pago(pago_id=pago["id"],
                        nuevo_metodo="MetodoQueNoExiste",
                        usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_editar_pago_orden_anulada():
    a = loc.obtener_almacen()
    _crear_entrada("Prod EditarPago Anul", 10, codigo="FAE900",
                   precio_unitario=100)
    p = inv.buscar_producto_por_nombre("Prod EditarPago Anul", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    ven.anular_orden(r["orden_id"], USR_ADMIN)
    try:
        ven.editar_pago(pago_id=o["pagos"][0]["id"],
                        nuevo_metodo="Transfermóvil",
                        usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


# ═══════════════════════════════════════════════════════════
# AGREGAR / ELIMINAR PAGOS
# ═══════════════════════════════════════════════════════════

def test_agregar_pago_a_orden():
    a = loc.obtener_almacen()
    _crear_entrada("Prod AgregarPago", 5, codigo="FAE800",
                   precio_unitario=100)
    p = inv.buscar_producto_por_nombre("Prod AgregarPago", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 2)
    t = ven.calcular_totales(c)

    # Venta completa con Efectivo
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    assert o["estado"] == "pagada"

    # Quitamos el pago → la orden queda pendiente
    ven.eliminar_pago(o["pagos"][0]["id"], USR_ADMIN)
    o1 = ven.obtener_orden(r["orden_id"])
    assert o1["estado"] == "pendiente"

    # Agregamos Transfermóvil por la mitad → parcial
    ven.agregar_pago_a_orden(
        orden_id=r["orden_id"],
        metodo="Transfermóvil",
        moneda="CUP",
        monto=t["total"] / 2,
        usuario=USR_ADMIN)
    o2 = ven.obtener_orden(r["orden_id"])
    assert o2["estado"] == "parcial"

    # Agregamos el resto con Efectivo → pagada
    ven.agregar_pago_a_orden(
        orden_id=r["orden_id"],
        metodo="Efectivo",
        moneda="CUP",
        monto=t["total"] / 2,
        usuario=USR_ADMIN)
    o3 = ven.obtener_orden(r["orden_id"])
    assert o3["estado"] == "pagada"
    assert abs(o3["saldo_pendiente"]) < 0.01


def test_agregar_pago_metodo_duplicado():
    """No se puede agregar el mismo método dos veces."""
    a = loc.obtener_almacen()
    _crear_entrada("Prod DupMetodo", 5, codigo="FAE820",
                   precio_unitario=100)
    p = inv.buscar_producto_por_nombre("Prod DupMetodo", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 2)
    t = ven.calcular_totales(c)

    # Venta con Efectivo + Fiado
    cid = cli.crear_cliente("Cliente DupMetodo")
    c["cliente_id"] = cid
    r = ven.registrar_venta(
        carrito=c,
        pagos=[
            {"metodo": "Efectivo", "moneda": "CUP",
             "monto": t["total"] / 2, "tasa": 1.0},
            {"metodo": "Fiado", "moneda": "CUP",
             "monto": t["total"] / 2, "tasa": 1.0},
        ],
        usuario=USR_ADMIN, local_id=a["id"])

    # Intentar agregar Efectivo → ya existe → error
    try:
        ven.agregar_pago_a_orden(
            orden_id=r["orden_id"],
            metodo="Efectivo",
            moneda="CUP",
            monto=100,
            usuario=USR_ADMIN)
        assert False
    except ValueError as ex:
        assert "ya existe" in str(ex).lower()


def test_agregar_pago_forzar_moneda():
    """Zelle fuerza USD al agregar."""
    inv.set_config("tasa_usd", "100")
    try:
        a = loc.obtener_almacen()
        _crear_entrada("Prod AgregarZelle", 5, codigo="FAE821",
                       precio_unitario=1000)
        p = inv.buscar_producto_por_nombre("Prod AgregarZelle", a["id"])
        c = ven.nuevo_carrito()
        ven.agregar_item(c, p, 2)
        t = ven.calcular_totales(c)

        # Venta completa con Efectivo
        r = ven.registrar_venta(
            carrito=c,
            pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                    "monto": t["total"], "tasa": 1.0}],
            usuario=USR_ADMIN, local_id=a["id"])
        o = ven.obtener_orden(r["orden_id"])

        # Quitamos el Efectivo
        ven.eliminar_pago(o["pagos"][0]["id"], USR_ADMIN)

        # Agregamos Zelle (debe forzar USD aunque pasemos CUP)
        ven.agregar_pago_a_orden(
            orden_id=r["orden_id"],
            metodo="Zelle",
            moneda="CUP",  # ← se ignora
            monto=t["total"] / 100,  # 2000/100 = 20 USD
            usuario=USR_ADMIN)
        o2 = ven.obtener_orden(r["orden_id"])
        zelle = next(p for p in o2["pagos"]
                     if p["metodo"] == "Zelle")
        assert zelle["moneda"] == "USD"
    finally:
        inv.set_config("tasa_usd", "1.0")


def test_eliminar_pago_cambia_estado():
    a = loc.obtener_almacen()
    _crear_entrada("Prod ElimPago", 5, codigo="FAE801",
                   precio_unitario=200)
    p = inv.buscar_producto_por_nombre("Prod ElimPago", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    assert o["estado"] == "pagada"

    ven.eliminar_pago(o["pagos"][0]["id"], USR_ADMIN)
    o2 = ven.obtener_orden(r["orden_id"])
    assert o2["estado"] == "pendiente"
    assert abs(o2["saldo_pendiente"] - t["total"]) < 0.01


def test_eliminar_pago_inexistente():
    try:
        ven.eliminar_pago(9999999, USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_agregar_pago_orden_anulada():
    a = loc.obtener_almacen()
    _crear_entrada("Prod AgregAnul", 5, codigo="FAE802",
                   precio_unitario=100)
    p = inv.buscar_producto_por_nombre("Prod AgregAnul", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    ven.anular_orden(r["orden_id"], USR_ADMIN)
    try:
        ven.agregar_pago_a_orden(
            orden_id=r["orden_id"],
            metodo="Transfermóvil", moneda="CUP", monto=100,
            usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_eliminar_pago_orden_anulada():
    a = loc.obtener_almacen()
    _crear_entrada("Prod ElimAnul", 5, codigo="FAE822",
                   precio_unitario=100)
    p = inv.buscar_producto_por_nombre("Prod ElimAnul", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    ven.anular_orden(r["orden_id"], USR_ADMIN)
    try:
        ven.eliminar_pago(o["pagos"][0]["id"], USR_ADMIN)
        assert False
    except ValueError:
        pass


# ═══════════════════════════════════════════════════════════
# CAJA
# ═══════════════════════════════════════════════════════════

def test_abrir_caja():
    a = loc.obtener_almacen()
    with get_conn() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        try:
            conn.execute("DELETE FROM caja_sesiones")
        except Exception:
            pass
        conn.execute("PRAGMA foreign_keys = ON")
    sid = cj.abrir_sesion(a["id"], "admin", 500.0)
    assert sid > 0


def test_no_doble_apertura():
    a = loc.obtener_almacen()
    try:
        cj.abrir_sesion(a["id"], "admin", 100.0)
        assert False
    except ValueError:
        pass


def test_cerrar_caja():
    a = loc.obtener_almacen()
    s = cj.sesion_abierta(a["id"], "admin")
    r = cj.cerrar_sesion(s["id"], 500.0, notas="test")
    assert "saldo_sistema" in r
    assert "diferencia" in r


def test_no_doble_cierre():
    a = loc.obtener_almacen()
    sesiones = cj.listar_sesiones(a["id"], limite=1)
    if sesiones and sesiones[0]["cerrada"]:
        try:
            cj.cerrar_sesion(sesiones[0]["id"], 0)
            assert False
        except ValueError:
            pass


def test_caja_descuenta_gastos():
    with get_conn() as conn:
        conn.execute("PRAGMA foreign_keys = OFF")
        for tabla in ("devoluciones", "gastos", "abonos", "pagos",
                      "orden_items", "ordenes_venta", "caja_sesiones"):
            try:
                conn.execute(f"DELETE FROM {tabla}")
            except Exception:
                pass
        conn.execute("PRAGMA foreign_keys = ON")

    a = loc.obtener_almacen()
    sid = cj.abrir_sesion(a["id"], "test_caja_gasto", 1000.0)
    s1 = cj.calcular_saldo_sistema(sid)
    assert abs(s1 - 1000) < 0.01

    gid = gs.registrar_gasto(
        monto=200, moneda="CUP",
        usuario={"username": "test_caja_gasto", "rol": "admin"},
        caja_sesion_id=sid)

    with get_conn() as conn:
        row = conn.execute(
            "SELECT caja_sesion_id FROM gastos WHERE id=?", (gid,)
        ).fetchone()
    assert row["caja_sesion_id"] == sid

    s2 = cj.calcular_saldo_sistema(sid)
    assert abs(s2 - 800) < 0.01
    cj.cerrar_sesion(sid, 800.0)


# ═══════════════════════════════════════════════════════════
# DEVOLUCIONES
# ═══════════════════════════════════════════════════════════

def test_devolucion_parcial():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    stock_antes = p["stock"]
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 4)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    item_id = o["items"][0]["id"]
    dev.registrar_devolucion(
        orden_id=r["orden_id"],
        items_devueltos=[{"item_id": item_id, "cantidad": 2}],
        motivo="Test", usuario=USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p2["stock"] == stock_antes - 2


def test_devolucion_total():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    stock_antes = p["stock"]
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    dev.registrar_devolucion(
        orden_id=r["orden_id"],
        items_devueltos=[{"item_id": o["items"][0]["id"],
                          "cantidad": 3}],
        motivo="Total", usuario=USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p2["stock"] == stock_antes


def test_devolucion_mas_de_lo_vendido():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 2)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    try:
        dev.registrar_devolucion(
            orden_id=r["orden_id"],
            items_devueltos=[{"item_id": o["items"][0]["id"],
                              "cantidad": 10}],
            motivo="Exceso", usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_devolucion_dos_veces_mismo_item():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    o = ven.obtener_orden(r["orden_id"])
    item_id = o["items"][0]["id"]
    dev.registrar_devolucion(
        orden_id=r["orden_id"],
        items_devueltos=[{"item_id": item_id, "cantidad": 2}],
        motivo="Parcial 1", usuario=USR_ADMIN)
    dev.registrar_devolucion(
        orden_id=r["orden_id"],
        items_devueltos=[{"item_id": item_id, "cantidad": 1}],
        motivo="Parcial 2", usuario=USR_ADMIN)
    try:
        dev.registrar_devolucion(
            orden_id=r["orden_id"],
            items_devueltos=[{"item_id": item_id, "cantidad": 1}],
            motivo="Exceso", usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_devolucion_fuera_de_plazo():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    fecha_vieja = (datetime.now() - timedelta(days=10)).strftime(
        "%Y-%m-%d %H:%M:%S")
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"],
        fecha=fecha_vieja)
    o = ven.obtener_orden(r["orden_id"])
    try:
        dev.registrar_devolucion(
            orden_id=r["orden_id"],
            items_devueltos=[{"item_id": o["items"][0]["id"],
                              "cantidad": 1}],
            motivo="Tarde", usuario=USR_ALM)
        assert False
    except ValueError as ex:
        assert "días" in str(ex).lower()


def test_devolucion_sin_items():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 1)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    try:
        dev.registrar_devolucion(
            orden_id=r["orden_id"],
            items_devueltos=[],
            motivo="Vacío", usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


# ═══════════════════════════════════════════════════════════
# REGRESIÓN: DEVOLUCIÓN + ANULACIÓN
# ═══════════════════════════════════════════════════════════

def test_regresion_devolucion_luego_anular():
    a = loc.obtener_almacen()
    _crear_entrada("Helado Test Regresion", 10, codigo="FA9990",
                   precio_unitario=50)
    p = inv.buscar_producto_por_nombre("Helado Test Regresion", a["id"])
    stock_inicial = float(p["stock"])
    assert stock_inicial == 10

    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])

    stock_post_venta = float(inv.buscar_producto_por_nombre(
        "Helado Test Regresion", a["id"])["stock"])
    assert stock_post_venta == 5

    o = ven.obtener_orden(r["orden_id"])
    item_id = o["items"][0]["id"]
    dev.registrar_devolucion(
        orden_id=r["orden_id"],
        items_devueltos=[{"item_id": item_id, "cantidad": 2}],
        motivo="Test bug devolución", usuario=USR_ADMIN)

    stock_post_dev = float(inv.buscar_producto_por_nombre(
        "Helado Test Regresion", a["id"])["stock"])
    assert stock_post_dev == 7

    ven.anular_orden(r["orden_id"], USR_ADMIN)

    stock_final = float(inv.buscar_producto_por_nombre(
        "Helado Test Regresion", a["id"])["stock"])
    assert stock_final == 10, (
        f"BUG REGRESIÓN: anulación duplicó stock. "
        f"Esperado 10, obtenido {stock_final}.")


def test_regresion_devolucion_total_luego_anular():
    a = loc.obtener_almacen()
    _crear_entrada("Producto Regresion 2", 20, codigo="FA9991",
                   precio_unitario=30)
    p = inv.buscar_producto_por_nombre("Producto Regresion 2", a["id"])
    stock_inicial = float(p["stock"])

    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])

    o = ven.obtener_orden(r["orden_id"])
    dev.registrar_devolucion(
        orden_id=r["orden_id"],
        items_devueltos=[{"item_id": o["items"][0]["id"],
                          "cantidad": 5}],
        motivo="Total antes de anular", usuario=USR_ADMIN)

    stock_post_dev = float(inv.buscar_producto_por_nombre(
        "Producto Regresion 2", a["id"])["stock"])
    assert stock_post_dev == stock_inicial

    ven.anular_orden(r["orden_id"], USR_ADMIN)
    stock_final = float(inv.buscar_producto_por_nombre(
        "Producto Regresion 2", a["id"])["stock"])
    assert stock_final == stock_inicial


def test_regresion_anular_orden_sin_devoluciones():
    a = loc.obtener_almacen()
    _crear_entrada("Producto Sanity", 15, codigo="FA9992",
                   precio_unitario=10)
    p = inv.buscar_producto_por_nombre("Producto Sanity", a["id"])
    stock_inicial = float(p["stock"])

    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 5)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])

    ven.anular_orden(r["orden_id"], USR_ADMIN)
    stock_final = float(inv.buscar_producto_por_nombre(
        "Producto Sanity", a["id"])["stock"])
    assert stock_final == stock_inicial


def test_regresion_devolucion_parcial_multiples_items():
    a = loc.obtener_almacen()
    _crear_entrada("Producto Multi A", 10, codigo="FA9993",
                   precio_unitario=50)
    _crear_entrada("Producto Multi B", 10, codigo="FA9994",
                   precio_unitario=30)
    pA = inv.buscar_producto_por_nombre("Producto Multi A", a["id"])
    pB = inv.buscar_producto_por_nombre("Producto Multi B", a["id"])

    c = ven.nuevo_carrito()
    ven.agregar_item(c, pA, 2)
    ven.agregar_item(c, pB, 3)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])

    o = ven.obtener_orden(r["orden_id"])
    item_a = next(it for it in o["items"]
                  if it["nombre"] == "Producto Multi A")

    dev.registrar_devolucion(
        orden_id=r["orden_id"],
        items_devueltos=[{"item_id": item_a["id"], "cantidad": 1}],
        motivo="Parcial", usuario=USR_ADMIN)

    ven.anular_orden(r["orden_id"], USR_ADMIN)

    pA2 = inv.buscar_producto_por_nombre("Producto Multi A", a["id"])
    pB2 = inv.buscar_producto_por_nombre("Producto Multi B", a["id"])
    assert float(pA2["stock"]) == 10
    assert float(pB2["stock"]) == 10


# ═══════════════════════════════════════════════════════════
# TICKETS
# ═══════════════════════════════════════════════════════════

def test_ticket_pdf():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM ordenes_venta ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return
    try:
        data = tk.generar_ticket_pdf(row["id"])
        assert len(data) > 200
    except Exception as ex:
        print(f"  [INFO] PDF no generado: {ex}")


def test_ticket_png():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM ordenes_venta ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return
    try:
        data = tk.generar_ticket_png(row["id"])
        assert len(data) > 200
    except Exception as ex:
        print(f"  [INFO] PNG no generado: {ex}")


def test_ticket_texto_plano():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM ordenes_venta ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return
    txt = tk.texto_plano_ticket(row["id"])
    assert "TICKET" in txt.upper() or "Total" in txt


def test_ticket_orden_inexistente():
    try:
        tk.generar_ticket_pdf(9999999)
        assert False
    except ValueError:
        pass


# ═══════════════════════════════════════════════════════════
# CONFIGURACIÓN DEL NEGOCIO
# ═══════════════════════════════════════════════════════════

def test_config_negocio():
    cfg.set_config_negocio("nombre", "Mi Negocio")
    cfg.set_config_negocio("direccion", "Calle 1")
    assert cfg.get_config_negocio("nombre") == "Mi Negocio"
    todos = cfg.get_todos_negocio()
    assert todos["nombre"] == "Mi Negocio"


def test_config_negocio_default():
    val = cfg.get_config_negocio("no_existe", "DEFAULT")
    assert val == "DEFAULT"


# ═══════════════════════════════════════════════════════════
# GRANEL
# ═══════════════════════════════════════════════════════════

def test_flag_granel():
    a = loc.obtener_almacen()
    inv.registrar_entrada("Granel Test", 100, USR_ADMIN, a["id"])
    p = inv.buscar_producto_por_nombre("Granel Test", a["id"])
    with get_conn() as conn:
        conn.execute(
            "UPDATE productos SET es_granel=1 WHERE id=?", (p["id"],))
    p2 = inv.buscar_producto_por_nombre("Granel Test", a["id"])
    assert p2["es_granel"] == 1


# ═══════════════════════════════════════════════════════════
# GASTOS
# ═══════════════════════════════════════════════════════════

def test_categorias_gastos_default():
    cats_gs = gs.listar_categorias_gastos(solo_activas=True)
    nombres = [c["nombre"] for c in cats_gs]
    for esperado in ("Luz", "Agua", "Alquiler", "Salario"):
        assert esperado in nombres


def test_crear_categoria_gasto():
    cid = gs.crear_categoria_gasto("Internet")
    assert cid > 0
    c = gs.obtener_categoria_gasto(cid)
    assert c["nombre"] == "Internet"
    assert c["activo"] == 1


def test_categoria_gasto_duplicada():
    gs.crear_categoria_gasto("Mantenimiento")
    try:
        gs.crear_categoria_gasto("mantenimiento")
        assert False
    except ValueError:
        pass


def test_normalizar_categoria_gasto():
    c = gs.obtener_categoria_gasto(
        gs.crear_categoria_gasto("electricidad"))
    assert c["nombre"] == "Electricidad"


def test_renombrar_categoria_gasto():
    cid = gs.crear_categoria_gasto("TestRenombrar")
    gs.renombrar_categoria_gasto(cid, "renombrada")
    c = gs.obtener_categoria_gasto(cid)
    assert c["nombre"] == "Renombrada"


def test_desactivar_categoria_gasto():
    cid = gs.crear_categoria_gasto("ParaDesactivar")
    gs.desactivar_categoria_gasto(cid)
    c = gs.obtener_categoria_gasto(cid)
    assert c["activo"] == 0


def test_categoria_gasto_muy_corta():
    try:
        gs.crear_categoria_gasto("X")
        assert False
    except ValueError:
        pass


def test_crear_gasto_simple_cup():
    gid = gs.registrar_gasto(
        monto=500, moneda="CUP", usuario=USR_ADMIN,
        metodo="Efectivo", descripcion="Prueba luz")
    assert gid > 0
    g = gs.obtener_gasto(gid)
    assert g["monto"] == 500
    assert g["moneda"] == "CUP"
    assert g["monto_cup"] == 500


def test_crear_gasto_en_usd():
    inv.set_config("tasa_usd", "100")
    gid = gs.registrar_gasto(monto=10, moneda="USD",
                             usuario=USR_ADMIN)
    g = gs.obtener_gasto(gid)
    assert abs(g["monto_cup"] - 1000) < 0.01
    inv.set_config("tasa_usd", "1.0")


def test_crear_gasto_en_eur():
    inv.set_config("tasa_eur", "120")
    gid = gs.registrar_gasto(monto=5, moneda="EUR",
                             usuario=USR_ADMIN)
    g = gs.obtener_gasto(gid)
    assert abs(g["monto_cup"] - 600) < 0.01
    inv.set_config("tasa_eur", "1.0")


def test_gasto_global():
    gid = gs.registrar_gasto(monto=100, moneda="CUP",
                             usuario=USR_ADMIN, local_id=None)
    g = gs.obtener_gasto(gid)
    assert g["local_id"] is None


def test_gasto_por_local():
    a = loc.obtener_almacen()
    gid = gs.registrar_gasto(monto=100, moneda="CUP",
                             usuario=USR_ADMIN, local_id=a["id"])
    g = gs.obtener_gasto(gid)
    assert g["local_id"] == a["id"]


def test_gasto_con_categoria():
    cid = gs.crear_categoria_gasto("OtraCatGasto")
    gid = gs.registrar_gasto(monto=200, moneda="CUP",
                             usuario=USR_ADMIN, categoria_id=cid)
    g = gs.obtener_gasto(gid)
    assert g["categoria_id"] == cid


def test_gasto_con_metodo():
    gid = gs.registrar_gasto(monto=100, moneda="CUP",
                             usuario=USR_ADMIN,
                             metodo="Transfermóvil")
    g = gs.obtener_gasto(gid)
    assert g["metodo"] == "Transfermóvil"


def test_gasto_monto_cero():
    try:
        gs.registrar_gasto(monto=0, moneda="CUP",
                           usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_gasto_monto_negativo():
    try:
        gs.registrar_gasto(monto=-100, moneda="CUP",
                           usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_gasto_categoria_invalida():
    try:
        gs.registrar_gasto(monto=100, moneda="CUP",
                           usuario=USR_ADMIN, categoria_id=99999)
        assert False
    except ValueError:
        pass


def test_editar_gasto_monto():
    gid = gs.registrar_gasto(monto=100, moneda="CUP",
                             usuario=USR_ADMIN)
    gs.editar_gasto(gid, monto=250)
    g = gs.obtener_gasto(gid)
    assert g["monto"] == 250


def test_editar_gasto_cambia_moneda():
    inv.set_config("tasa_usd", "50")
    gid = gs.registrar_gasto(monto=100, moneda="CUP",
                             usuario=USR_ADMIN)
    gs.editar_gasto(gid, monto=10, moneda="USD")
    g = gs.obtener_gasto(gid)
    assert g["moneda"] == "USD"
    assert abs(g["monto_cup"] - 500) < 0.01
    inv.set_config("tasa_usd", "1.0")


def test_eliminar_gasto():
    gid = gs.registrar_gasto(monto=100, moneda="CUP",
                             usuario=USR_ADMIN)
    gs.eliminar_gasto(gid)
    assert gs.obtener_gasto(gid) is None


def test_eliminar_gasto_inexistente():
    try:
        gs.eliminar_gasto(999999)
        assert False
    except ValueError:
        pass


def test_listar_gastos_por_rango():
    with get_conn() as conn:
        conn.execute("DELETE FROM gastos")
    gs.registrar_gasto(monto=100, moneda="CUP", usuario=USR_ADMIN,
                       fecha="2026-01-15 10:00:00")
    gs.registrar_gasto(monto=200, moneda="CUP", usuario=USR_ADMIN,
                       fecha="2026-06-15 10:00:00")
    r = gs.listar_gastos(desde="2026-01-01 00:00:00",
                         hasta="2026-02-01 00:00:00")
    assert len(r) == 1
    assert r[0]["monto"] == 100


def test_listar_gastos_por_categoria():
    with get_conn() as conn:
        conn.execute("DELETE FROM gastos")
    cid = gs.crear_categoria_gasto("CatFiltro")
    gs.registrar_gasto(monto=100, moneda="CUP", usuario=USR_ADMIN,
                       categoria_id=cid)
    gs.registrar_gasto(monto=200, moneda="CUP", usuario=USR_ADMIN)
    r = gs.listar_gastos(categoria_id=cid)
    assert len(r) == 1
    assert r[0]["categoria_id"] == cid


def test_total_gastos_periodo():
    with get_conn() as conn:
        conn.execute("DELETE FROM gastos")
    gs.registrar_gasto(monto=100, moneda="CUP", usuario=USR_ADMIN,
                       fecha="2026-03-10 10:00:00")
    gs.registrar_gasto(monto=250, moneda="CUP", usuario=USR_ADMIN,
                       fecha="2026-03-20 10:00:00")
    total = gs.total_gastos_periodo(
        desde="2026-03-01 00:00:00",
        hasta="2026-04-01 00:00:00")
    assert abs(total - 350) < 0.01


def test_gastos_por_categoria():
    with get_conn() as conn:
        conn.execute("DELETE FROM gastos")
    cid = gs.crear_categoria_gasto("CatAgrup")
    gs.registrar_gasto(monto=100, moneda="CUP", usuario=USR_ADMIN,
                       categoria_id=cid)
    gs.registrar_gasto(monto=150, moneda="CUP", usuario=USR_ADMIN,
                       categoria_id=cid)
    r = gs.gastos_por_categoria()
    encontrado = next((x for x in r if x["categoria_id"] == cid), None)
    assert encontrado is not None
    assert abs(encontrado["total"] - 250) < 0.01


# ═══════════════════════════════════════════════════════════
# PROVEEDORES
# ═══════════════════════════════════════════════════════════

def test_crear_proveedor():
    pid = pv.crear_proveedor("Distribuidora El Sol",
                             telefono="5551234")
    assert pid > 0
    p = pv.obtener_proveedor(pid)
    assert p["nombre"] == "Distribuidora El Sol"
    assert p["telefono"] == "5551234"


def test_capitalizar_proveedor():
    pid = pv.crear_proveedor("panadería central")
    p = pv.obtener_proveedor(pid)
    assert p["nombre"] == "Panadería Central"


def test_proveedor_duplicado():
    pv.crear_proveedor("Proveedor Dup")
    try:
        pv.crear_proveedor("proveedor dup")
        assert False
    except ValueError:
        pass


def test_proveedor_nombre_corto():
    try:
        pv.crear_proveedor("X")
        assert False
    except ValueError:
        pass


def test_editar_proveedor():
    pid = pv.crear_proveedor("Proveedor Editable")
    pv.editar_proveedor(pid, telefono="5559999")
    p = pv.obtener_proveedor(pid)
    assert p["telefono"] == "5559999"


def test_desactivar_proveedor():
    pid = pv.crear_proveedor("Proveedor Desactivable")
    pv.activar_proveedor(pid, False)
    p = pv.obtener_proveedor(pid)
    assert p["activo"] == 0


def test_asociar_proveedor_a_producto():
    pid = pv.crear_proveedor("Prov Asociar")
    pv.asociar_proveedor("Pan Test", pid)
    provs = pv.proveedores_de_producto("Pan Test")
    assert any(p["id"] == pid for p in provs)


def test_asociar_idempotente():
    pid = pv.crear_proveedor("Prov Idempotente")
    pv.asociar_proveedor("Arroz Test", pid)
    pv.asociar_proveedor("Arroz Test", pid)
    provs = pv.proveedores_de_producto("Arroz Test")
    assert sum(1 for p in provs if p["id"] == pid) == 1


def test_marcar_principal():
    pid1 = pv.crear_proveedor("Prov Ppal 1")
    pid2 = pv.crear_proveedor("Prov Ppal 2")
    pv.asociar_proveedor("Café Test", pid1, es_principal=1)
    pv.asociar_proveedor("Café Test", pid2)
    principal = pv.proveedor_principal("Café Test")
    assert principal is not None
    assert principal["id"] == pid1
    pv.set_proveedor_principal("Café Test", pid2)
    principal = pv.proveedor_principal("Café Test")
    assert principal["id"] == pid2
    pv.set_proveedor_principal("Café Test", 0)
    assert pv.proveedor_principal("Café Test") is None


def test_desasociar_proveedor():
    pid = pv.crear_proveedor("Prov Desasociar")
    pv.asociar_proveedor("Azúcar Test", pid)
    pv.desasociar_proveedor("Azúcar Test", pid)
    provs = pv.proveedores_de_producto("Azúcar Test")
    assert not any(p["id"] == pid for p in provs)


def test_productos_de_proveedor():
    pid = pv.crear_proveedor("Prov Productos")
    pv.asociar_proveedor("Prod A", pid)
    pv.asociar_proveedor("Prod B", pid)
    productos = pv.productos_de_proveedor(pid)
    assert "Prod A" in productos
    assert "Prod B" in productos


def test_registrar_pago_proveedor():
    pid = pv.crear_proveedor("Prov Pago")
    pid_pago = pv.registrar_pago(
        proveedor_id=pid, monto=500, moneda="CUP",
        usuario=USR_ADMIN, metodo="Efectivo")
    assert pid_pago > 0
    total = pv.total_pagado_proveedor(pid)
    assert abs(total - 500) < 0.01


def test_pago_proveedor_usd():
    inv.set_config("tasa_usd", "100")
    pid = pv.crear_proveedor("Prov Pago USD")
    pv.registrar_pago(proveedor_id=pid, monto=10, moneda="USD",
                      usuario=USR_ADMIN)
    total = pv.total_pagado_proveedor(pid)
    assert abs(total - 1000) < 0.01
    inv.set_config("tasa_usd", "1.0")


def test_pago_monto_cero():
    pid = pv.crear_proveedor("Prov Pago Cero")
    try:
        pv.registrar_pago(proveedor_id=pid, monto=0, moneda="CUP",
                          usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_pago_proveedor_inexistente():
    try:
        pv.registrar_pago(proveedor_id=999999, monto=100,
                          moneda="CUP", usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_saldo_proveedor():
    pid = pv.crear_proveedor("Prov Saldo")
    a = loc.obtener_almacen()
    inv.registrar_entrada(
        nombre="Prod Saldo Test", cantidad=10,
        usuario=USR_ADMIN, local_id=a["id"],
        codigo="ZZ9998", precio_costo=100)
    prod = inv.buscar_producto_por_nombre("Prod Saldo Test", a["id"])
    with get_conn() as conn:
        conn.execute(
            "UPDATE movimientos SET proveedor_id=? "
            "WHERE producto_id=? AND tipo='ENTRADA'",
            (pid, prod["id"]))
    saldo = pv.saldo_proveedor(pid)
    assert abs(saldo - 1000) < 0.01
    pv.registrar_pago(proveedor_id=pid, monto=400, moneda="CUP",
                      usuario=USR_ADMIN)
    saldo = pv.saldo_proveedor(pid)
    assert abs(saldo - 600) < 0.01


def test_listar_proveedores():
    provs = pv.listar_proveedores(solo_activos=False)
    assert len(provs) >= 5


def test_listar_proveedores_con_texto():
    pv.crear_proveedor("Unique Name Test")
    r = pv.listar_proveedores(texto="Unique Name")
    assert len(r) >= 1


def test_listar_con_saldo():
    pid = pv.crear_proveedor("Prov Con Saldo Lista")
    a = loc.obtener_almacen()
    inv.registrar_entrada(
        nombre="Prod Con Saldo Lista", cantidad=5,
        usuario=USR_ADMIN, local_id=a["id"],
        codigo="ZZ9997", precio_costo=200)
    prod = inv.buscar_producto_por_nombre(
        "Prod Con Saldo Lista", a["id"])
    with get_conn() as conn:
        conn.execute(
            "UPDATE movimientos SET proveedor_id=? "
            "WHERE producto_id=? AND tipo='ENTRADA'",
            (pid, prod["id"]))
    lista = pv.listar_con_saldo()
    encontrado = next((x for x in lista if x["id"] == pid), None)
    assert encontrado is not None
    assert encontrado["saldo"] > 0


# ═══════════════════════════════════════════════════════════
# CASOS EXTREMOS GLOBALES
# ═══════════════════════════════════════════════════════════

def test_nombres_unicode_productos():
    a = loc.obtener_almacen()
    info = inv.registrar_entrada(
        nombre="Café Ñandú 日本語", cantidad=10, usuario=USR_ADMIN,
        local_id=a["id"], codigo="FA8800")
    assert info["stock"] == 10
    p = inv.buscar_producto_por_nombre("Café Ñandú 日本語", a["id"])
    assert p is not None


def test_cantidad_gigante():
    a = loc.obtener_almacen()
    info = inv.registrar_entrada(
        "Prod Gigante", 1_000_000, USR_ADMIN, a["id"])
    assert info["stock"] == 1_000_000


def test_cantidad_decimal():
    a = loc.obtener_almacen()
    info = inv.registrar_entrada(
        "Prod Decimal", 0.5, USR_ADMIN, a["id"])
    assert info["stock"] == 0.5


def test_simbolo_moneda():
    from ui import estilos as es
    assert es.simbolo_moneda("CUP") == "$"
    assert es.simbolo_moneda("USD") == "USD$"
    assert es.simbolo_moneda("EUR") == "€"
    assert es.simbolo_moneda("XXX") == "$"


# ═══════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════

TESTS = [
    # Seguridad
    ("Hash PBKDF2",                     test_hash_password),
    ("Hash determinista por salt",      test_hash_distintos),
    ("Hash password vacío",             test_hash_password_vacio),
    ("Hash unicode",                    test_hash_unicode),
    ("Hash case sensitive",             test_hash_case_sensitive),
    # DB
    ("Versión esquema = 10",             test_version_esquema),
    ("Almacén creado",                  test_almacen_creado),
    ("Categorías default",              test_categorias_default),
    ("Config defaults",                 test_config_defaults),
    ("get_conn cierra conexión",        test_get_conn_cierra_conexion),
    # Categorías producto
    ("Crear categoría",                 test_crear_categoria),
    ("Normalizar categoría",            test_normalizar_categoria),
    ("Categoría duplicada",             test_categoria_duplicada),
    ("Renombrar categoría",             test_renombrar_categoria),
    ("Desactivar categoría",            test_desactivar_categoria),
    ("Categoría muy corta",             test_categoria_muy_corta),
    ("Categoría vacía",                 test_categoria_vacia),
    ("Categoría solo espacios",         test_categoria_solo_espacios),
    # Usuarios
    ("Crear usuario",                   test_crear_usuario),
    ("Usuario duplicado",               test_usuario_duplicado),
    ("Usuario dup case-insens.",        test_usuario_duplicado_case_insensitive),
    ("Usuario no-admin falla",          test_usuario_no_admin_falla),
    ("Común no crea usuarios",          test_comun_no_crea_usuarios),
    ("Cambiar rol",                     test_cambiar_rol),
    ("Password corta",                  test_password_corta),
    ("Rol inválido",                    test_rol_invalido),
    ("Resetear contraseña",             test_resetear_password),
    ("No eliminar último admin",        test_no_eliminar_ultimo_admin),
    ("No eliminar a sí mismo",          test_no_eliminar_a_si_mismo),
    # Locales
    ("Abrir tienda",                    test_abrir_tienda),
    ("Nombre reservado",                test_tienda_nombre_reservado),
    ("Tienda duplicada",                test_tienda_duplicada),
    ("Listar tiendas",                  test_listar_tiendas),
    ("Renombrar local",                 test_renombrar_local),
    ("No cerrar Almacén",               test_no_cerrar_almacen),
    ("Cerrar tienda traspasa stock",    test_cerrar_tienda_traspasa_stock),
    ("Nombre local",                    test_nombre_local),
    # Inventario
    ("Registrar entrada nuevo",         test_registrar_entrada_nuevo),
    ("Entrada suma stock",              test_entrada_suma_stock),
    ("Salida resta stock",              test_salida_resta_stock),
    ("Salida stock insuficiente",       test_salida_stock_insuficiente),
    ("Salida producto inexistente",     test_salida_producto_inexistente),
    ("Cantidad negativa",               test_cantidad_negativa),
    ("Cantidad cero",                   test_cantidad_cero),
    ("Común no opera",                  test_comun_no_opera),
    ("General no operable",             test_general_no_operable),
    ("Código auto-sugerido",            test_codigo_auto_sugerido),
    ("Código global propagado",         test_codigo_global_propagado),
    ("Código duplicado local",          test_codigo_duplicado_local),
    ("Código duplicado global",         test_codigo_duplicado_global),
    ("Traspaso",                        test_traspaso),
    ("Traspaso stock insuficiente",     test_traspaso_stock_insuficiente),
    ("Traspaso mismo local",            test_traspaso_mismo_local),
    ("Traspaso a/desde General",        test_traspaso_general),
    ("Cambiar umbrales",                test_cambiar_umbrales),
    ("Umbrales inválidos",              test_umbrales_invalidos),
    ("Umbrales negativos",              test_umbrales_negativos),
    ("Dar de baja",                     test_dar_baja),
    ("Dar de baja dos veces",           test_dar_baja_dos_veces),
    ("Reactivar producto",              test_reactivar),
    ("Reactivar ya activo",             test_reactivar_ya_activo),
    ("Set precio costo",                test_set_precio_costo),
    ("Set precio unitario",             test_set_precio_unitario),
    ("Color stock",                     test_color_stock),
    ("Totales local",                   test_totales_local),
    ("Renombrar producto propaga",      test_renombrar_producto_propaga),
    ("Renombrar producto duplicado",    test_renombrar_producto_duplicado),
    ("Eliminar movimiento entrada",     test_eliminar_movimiento_entrada),
    ("Editar movimiento",               test_editar_movimiento),
    ("Buscar productos like",           test_buscar_productos_like),
    # Multimoneda
    ("Convertir CUP→USD",               test_convertir_cup_a_usd),
    ("Convertir USD→CUP",               test_convertir_usd_a_cup),
    ("Convertir misma moneda",          test_convertir_misma_moneda),
    ("Convertir tasa cero",             test_convertir_tasa_cero_no_divide),
    ("Promedio ponderado entrada",      test_promedio_ponderado_en_entrada),
    ("Recalcular precios",              test_recalcular_precios),
    # Métricas
    ("Rango hoy",                       test_rango_hoy),
    ("Rango semana",                    test_rango_semana),
    ("Rango mes",                       test_rango_mes),
    ("Rango año",                       test_rango_anio),
    ("Rango total",                     test_rango_total),
    ("Resumen período",                 test_resumen_periodo),
    ("Estancados no solapa con vendidos", test_estancados_no_solapa_con_vendidos),
    ("Todos los activos clasificados",    test_todos_los_activos_clasificados),
    # Clientes
    ("Crear cliente",                   test_crear_cliente),
    ("Cliente duplicado",               test_cliente_duplicado),
    ("Editar cliente",                  test_editar_cliente),
    ("Buscar cliente",                  test_buscar_cliente),
    ("Cliente sin deuda",               test_cliente_sin_deuda),
    ("Cliente nombre corto",            test_cliente_nombre_corto),
    ("Cliente nombre vacío",            test_cliente_nombre_vacio),
    # Métodos de pago
    ("Métodos default",                 test_metodos_default),
    ("Métodos nuevos default",          test_metodos_nuevos_default),
    ("Moneda fija por método",          test_moneda_fija_por_metodo),
    ("Toggle método",                   test_toggle_metodo),
    ("Actualizar cuenta método",        test_actualizar_cuenta_metodo),
    # POS — carrito
    ("Carrito vacío",                   test_carrito_vacio),
    ("Agregar ítem",                    test_agregar_item),
    ("Agregar mismo suma",              test_agregar_mismo_producto_suma),
    ("Agregar cantidad cero",           test_agregar_cantidad_cero),
    ("Agregar cantidad negativa",       test_agregar_cantidad_negativa),
    ("Agregar > stock",                 test_agregar_mas_que_stock),
    ("Calcular totales",                test_calcular_totales),
    ("Descuento global",                test_descuento_global),
    ("Editar ítem carrito",             test_editar_item_carrito),
    ("Rebaja > precio",                 test_editar_item_rebaja_mayor_precio),
    ("Eliminar ítem carrito",           test_eliminar_item_carrito),
    # POS — ventas
    ("Venta simple",                    test_venta_simple),
    ("Venta pago mixto",                test_venta_pago_mixto),
    ("Venta pago insuficiente",         test_venta_pago_insuficiente),
    ("Venta máximo 3 pagos",            test_venta_max_3_pagos),
    ("Venta carrito vacío",             test_venta_carrito_vacio),
    ("Fiado requiere cliente",          test_venta_fiado_requiere_cliente),
    ("Fiado + abonos",                  test_venta_fiado_y_abonos),
    ("Abono > saldo con vuelto 0",      test_abono_mayor_con_vuelto_cero_es_propina),
    ("Abono con vuelto parcial",        test_abono_con_vuelto_no_aplica_el_sobrante),
    ("Anular restaura stock",           test_venta_anular_restaura_stock),
    ("Anular dos veces",                test_anular_orden_dos_veces),
    ("Venta stock insuficiente",        test_venta_stock_insuficiente),
    ("Venta método inválido",           test_venta_metodo_invalido),
    ("Vuelto calculado",                test_vuelto_calculado),
    ("Venta Zelle fuerza USD",          test_venta_zelle_fuerza_usd),
    ("Venta Transfermóvil fuerza CUP",  test_venta_transfermovil_fuerza_cup),
    # POS — edición de órdenes
    ("Editar items orden",              test_editar_items_orden_cambiar_cantidad),
    ("Editar orden sin items",          test_editar_items_orden_quitar_todo),
    ("Editar orden anulada",            test_editar_orden_anulada),
    # Editar pago
    ("Regresión editar método pago",    test_regresion_editar_metodo_pago),
    ("Editar pago solo método",         test_editar_pago_solo_metodo),
    ("Editar pago USD→CUP preserva",    test_editar_pago_usd_a_cup_preserva_monto_cup),
    ("Editar pago CUP→USD preserva",    test_editar_pago_cup_a_usd_preserva_monto_cup),
    ("Editar pago USD→EUR preserva",    test_editar_pago_usd_a_eur_preserva_monto_cup),
    ("Editar pago preserva monto_cup",  test_editar_pago_preserva_monto_cup_siempre),
    ("Editar pago Transfer → CUP",      test_editar_pago_transfermovil_fuerza_cup),
    ("Editar pago Zelle → USD",         test_editar_pago_zelle_fuerza_usd),
    ("REGRESIÓN pago no descuadra caja",test_regresion_editar_pago_no_descuadra_caja),
    ("REGRESIÓN pago idempotente",      test_regresion_editar_pago_idempotente),
    ("Wrapper cambiar_metodo_pago",     test_cambiar_metodo_pago_wrapper),
    ("Editar pago inexistente",         test_editar_pago_inexistente),
    ("Editar pago método inválido",     test_editar_pago_metodo_invalido),
    ("Editar pago orden anulada",       test_editar_pago_orden_anulada),
    # Agregar / eliminar pago
    ("Agregar pago a orden",            test_agregar_pago_a_orden),
    ("Agregar pago método duplicado",   test_agregar_pago_metodo_duplicado),
    ("Agregar pago fuerza moneda",      test_agregar_pago_forzar_moneda),
    ("Eliminar pago cambia estado",     test_eliminar_pago_cambia_estado),
    ("Eliminar pago inexistente",       test_eliminar_pago_inexistente),
    ("Agregar pago a orden anulada",    test_agregar_pago_orden_anulada),
    ("Eliminar pago de orden anulada",  test_eliminar_pago_orden_anulada),
    # Caja
    ("Abrir caja",                      test_abrir_caja),
    ("No doble apertura",               test_no_doble_apertura),
    ("Cerrar caja",                     test_cerrar_caja),
    ("No doble cierre",                 test_no_doble_cierre),
    ("Caja descuenta gastos",           test_caja_descuenta_gastos),
    # Devoluciones
    ("Devolución parcial",              test_devolucion_parcial),
    ("Devolución total",                test_devolucion_total),
    ("Devolución > vendido",            test_devolucion_mas_de_lo_vendido),
    ("Devolución dos veces",            test_devolucion_dos_veces_mismo_item),
    ("Devolución fuera de plazo",       test_devolucion_fuera_de_plazo),
    ("Devolución sin items",            test_devolucion_sin_items),
    # REGRESIÓN CRÍTICA
    ("REGRESIÓN devolución + anular",   test_regresion_devolucion_luego_anular),
    ("REGRESIÓN dev total + anular",    test_regresion_devolucion_total_luego_anular),
    ("REGRESIÓN anular sin dev",        test_regresion_anular_orden_sin_devoluciones),
    ("REGRESIÓN dev multi-item",        test_regresion_devolucion_parcial_multiples_items),
    # Tickets
    ("Ticket PDF",                      test_ticket_pdf),
    ("Ticket PNG",                      test_ticket_png),
    ("Ticket texto plano",              test_ticket_texto_plano),
    ("Ticket orden inexistente",        test_ticket_orden_inexistente),
    # Config negocio
    ("Config negocio",                  test_config_negocio),
    ("Config negocio default",          test_config_negocio_default),
    # Granel
    ("Flag granel",                     test_flag_granel),
    # Gastos
    ("Categorías gastos default",       test_categorias_gastos_default),
    ("Crear categoría gasto",           test_crear_categoria_gasto),
    ("Categoría gasto duplicada",       test_categoria_gasto_duplicada),
    ("Normalizar categoría gasto",      test_normalizar_categoria_gasto),
    ("Renombrar categoría gasto",       test_renombrar_categoria_gasto),
    ("Desactivar categoría gasto",      test_desactivar_categoria_gasto),
    ("Categoría gasto muy corta",       test_categoria_gasto_muy_corta),
    ("Crear gasto simple CUP",          test_crear_gasto_simple_cup),
    ("Crear gasto en USD",              test_crear_gasto_en_usd),
    ("Crear gasto en EUR",              test_crear_gasto_en_eur),
    ("Gasto global",                    test_gasto_global),
    ("Gasto por local",                 test_gasto_por_local),
    ("Gasto con categoría",             test_gasto_con_categoria),
    ("Gasto con método",                test_gasto_con_metodo),
    ("Gasto monto cero",                test_gasto_monto_cero),
    ("Gasto monto negativo",            test_gasto_monto_negativo),
    ("Gasto categoría inválida",        test_gasto_categoria_invalida),
    ("Editar gasto monto",              test_editar_gasto_monto),
    ("Editar gasto cambia moneda",      test_editar_gasto_cambia_moneda),
    ("Eliminar gasto",                  test_eliminar_gasto),
    ("Eliminar gasto inexistente",      test_eliminar_gasto_inexistente),
    ("Listar gastos por rango",         test_listar_gastos_por_rango),
    ("Listar gastos por categoría",     test_listar_gastos_por_categoria),
    ("Total gastos período",            test_total_gastos_periodo),
    ("Gastos por categoría",            test_gastos_por_categoria),
    # Proveedores
    ("Crear proveedor",                 test_crear_proveedor),
    ("Capitalizar proveedor",           test_capitalizar_proveedor),
    ("Proveedor duplicado",             test_proveedor_duplicado),
    ("Proveedor nombre corto",          test_proveedor_nombre_corto),
    ("Editar proveedor",                test_editar_proveedor),
    ("Desactivar proveedor",            test_desactivar_proveedor),
    ("Asociar prov a producto",         test_asociar_proveedor_a_producto),
    ("Asociar idempotente",             test_asociar_idempotente),
    ("Marcar principal",                test_marcar_principal),
    ("Desasociar proveedor",            test_desasociar_proveedor),
    ("Productos de proveedor",          test_productos_de_proveedor),
    ("Registrar pago proveedor",        test_registrar_pago_proveedor),
    ("Pago proveedor USD",              test_pago_proveedor_usd),
    ("Pago monto cero",                 test_pago_monto_cero),
    ("Pago proveedor inexistente",      test_pago_proveedor_inexistente),
    ("Saldo proveedor",                 test_saldo_proveedor),
    ("Listar proveedores",              test_listar_proveedores),
    ("Listar prov con texto",           test_listar_proveedores_con_texto),
    ("Listar con saldo",                test_listar_con_saldo),
    # Casos extremos globales
    ("Nombres unicode productos",       test_nombres_unicode_productos),
    ("Cantidad gigante",                test_cantidad_gigante),
    ("Cantidad decimal",                test_cantidad_decimal),
    ("Símbolo moneda",                  test_simbolo_moneda),
]


def main():
    print("=" * 62)
    print(f"  TEST SUITE — Almacén v{VERSION_ESQUEMA} (Combos Flash)")
    print(f"  BD temporal: {_TEMP_DIR}")
    print("=" * 62)
    print()

    from rutas import DB_PATH, DATOS, BACKUPS, LOGS
    for _c in (DATOS, BACKUPS, LOGS):
        _c.mkdir(parents=True, exist_ok=True)

    for p in (DB_PATH,
              Path(str(DB_PATH) + "-wal"),
              Path(str(DB_PATH) + "-shm")):
        try:
            if p.exists():
                p.unlink()
        except Exception:
            pass

    inicializar_db()
    _limpiar_todo()
    _sembrar_basico()

    pasados = 0
    fallidos = 0
    total = 0

    for nombre, fn in TESTS:
        total += 1
        try:
            r = fn()
            if r is False:
                fallidos += 1
                print(f"  ❌ {nombre}")
            else:
                pasados += 1
                print(f"  ✅ {nombre}")
        except AssertionError as ex:
            fallidos += 1
            print(f"  ❌ {nombre}: {ex}")
        except Exception as ex:
            fallidos += 1
            print(f"  ⚠️  {nombre}: {type(ex).__name__}: {ex}")

    print()
    print("=" * 62)
    if fallidos == 0:
        print(f"  ✅ TODOS LOS TESTS PASARON ({pasados}/{total})")
    else:
        print(f"  ⚠️  {pasados} pasados, {fallidos} fallidos "
              f"de {total}")
    print("=" * 62)

    try:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    except Exception:
        pass

    return 0 if fallidos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())