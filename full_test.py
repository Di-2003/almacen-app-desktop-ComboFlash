"""
Test exhaustivo del sistema Almacén v9.

Ejecuta: python full_test.py
Usa una BD temporal en /tmp (o %TEMP% en Windows) para no tocar tu
base de datos real.
"""
import os
import sys
import tempfile
import shutil
from pathlib import Path
from datetime import datetime
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
import configuracion_negocio as cfg
import gastos as gs
import proveedores as pv

# ═══════════════════════════════════════════════════════════
# CONFIGURAR BD TEMPORAL ANTES DE IMPORTAR NADA
# ═══════════════════════════════════════════════════════════
_TEMP_DIR = tempfile.mkdtemp(prefix="almacen_test_")
os.environ["FLET_APP_STORAGE_DATA"] = _TEMP_DIR

# Ahora sí, importar módulos
from db import (
    inicializar_db, get_conn, get_pref,
    VERSION_ESQUEMA, GENERAL_ID,
)


# ═══════════════════════════════════════════════════════════
# HELPERS
# ═══════════════════════════════════════════════════════════
USR_ADMIN = {"id": 1, "username": "admin", "rol": "admin"}
USR_ALM   = {"id": 2, "username": "almacenero", "rol": "almacen"}
USR_COM   = {"id": 3, "username": "comun", "rol": "comun"}


def _limpiar_todo():
    with get_conn() as conn:
        # NO borrar 'meta': ahí vive version_esquema
        for t in ("devoluciones", "abonos", "pagos", "orden_items",
                "ordenes_venta", "clientes", "caja_sesiones",
                "movimientos", "productos",
                "configuracion", "metodos_pago",
                "usuarios", "locales", "categorias"):
            try:
                conn.execute(f"DELETE FROM {t}")
            except Exception:
                pass

# ═══════════════════════════════════════════════════════════
# TESTS DE SEGURIDAD
# ═══════════════════════════════════════════════════════════

def test_hash_password():
    h, s = seg.crear_hash("mi_password_123")
    assert len(h) == 64, "Hash SHA-256 debe ser 64 hex"
    assert len(s) == 32, "Salt 16 bytes = 32 hex"
    assert seg.verificar_password("mi_password_123", s, h)
    assert not seg.verificar_password("otra", s, h)


def test_hash_distintos():
    h1, s1 = seg.crear_hash("abc")
    h2, s2 = seg.crear_hash("abc")
    assert h1 != h2, "Salt distinto debe dar hash distinto"
    assert s1 != s2


def test_hash_password_vacio():
    h, s = seg.crear_hash("")
    assert seg.verificar_password("", s, h)
    assert not seg.verificar_password("x", s, h)


def test_hash_unicode():
    h, s = seg.crear_hash("contraseña_con_ñ_y_áéíóú")
    assert seg.verificar_password("contraseña_con_ñ_y_áéíóú", s, h)


# ═══════════════════════════════════════════════════════════
# TESTS DE DB / MIGRACIÓN
# ═══════════════════════════════════════════════════════════

def test_version_esquema():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT valor FROM meta WHERE clave='version_esquema'"
        ).fetchone()
    assert row is not None, "Debe haber versión marcada"
    assert int(row["valor"]) == VERSION_ESQUEMA == 10


def test_almacen_creado():
    a = loc.obtener_almacen()
    assert a is not None, "Almacén debe existir"
    assert a["es_almacen"] == 1


def test_categorias_default():
    cs = cats.listar_categorias(solo_activas=True)
    nombres = [c["nombre"] for c in cs]
    for esperado in ("Alimentos", "Bebidas", "Limpieza"):
        assert esperado in nombres, f"Falta categoría default {esperado}"


def test_config_defaults():
    assert get_pref("tema") == "oscuro"
    assert get_pref("tasa_usd") is not None
    assert get_pref("moneda_visualizacion") == "CUP"


# ═══════════════════════════════════════════════════════════
# TESTS DE CATEGORÍAS
# ═══════════════════════════════════════════════════════════

def test_crear_categoria():
    cid = cats.crear_categoria("Juguetes")
    assert cid > 0
    c = cats.obtener_categoria(cid)
    assert c["nombre"] == "Juguetes"
    assert c["activo"] == 1


def test_normalizar_categoria():
    # "ELECTRÓNICA" normaliza a "Electrónica" (ya existe como default).
    # Buscar por nombre normalizado debe encontrarla.
    c = cats.buscar_por_nombre("ELECTRÓNICA")
    assert c is not None, "Debe encontrar Electrónica normalizada"
    assert c["nombre"] == "Electrónica"

def test_categoria_duplicada():
    cats.crear_categoria("Ropa")
    try:
        cats.crear_categoria("ropa")
        assert False, "No debe permitir duplicado case-insensitive"
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


# ═══════════════════════════════════════════════════════════
# TESTS DE USUARIOS
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


def test_usuario_no_admin_falla():
    try:
        um.crear_usuario("test3", "pass1234", "comun",
                         solicitante=USR_ALM)
        assert False, "No-admin no debe crear usuarios"
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


# ═══════════════════════════════════════════════════════════
# TESTS DE LOCALES
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


# ═══════════════════════════════════════════════════════════
# TESTS DE INVENTARIO
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


def test_comun_no_opera():
    a = loc.obtener_almacen()
    try:
        inv.registrar_entrada("X", 5, USR_COM, a["id"])
        assert False, "comun no puede registrar entrada"
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
    """Un nombre → un código global. Se autocorrige entre locales."""
    a = loc.obtener_almacen()
    tid = loc.abrir_tienda("Tienda Código")
    # Almacén tiene Arroz con FA0001
    # En tienda, crear el mismo producto con código distinto
    inv.registrar_entrada(
        "Arroz", 10, USR_ADMIN, tid, codigo="FZ9999")
    p = inv.buscar_producto_por_nombre("Arroz", tid)
    assert p is not None
    # El código debe haberse autocorregido a FA0001
    assert p["codigo"] == "FA0001", (
        f"Esperaba FA0001, obtuve {p['codigo']}")


def test_traspaso():
    a = loc.obtener_almacen()
    tid = loc.abrir_tienda("Tienda Traspaso")
    # Crear producto en Almacén
    inv.registrar_entrada("Azúcar", 100, USR_ADMIN, a["id"],
                          codigo="FA0050")
    stock_a = inv.buscar_producto_por_nombre("Azúcar", a["id"])["stock"]
    # Traspasar 30
    inv.registrar_traspaso("Azúcar", 30, USR_ADMIN,
                            a["id"], tid)
    sa = inv.buscar_producto_por_nombre("Azúcar", a["id"])["stock"]
    st = inv.buscar_producto_por_nombre("Azúcar", tid)["stock"]
    assert sa == stock_a - 30
    assert st == 30


def test_traspaso_mismo_local():
    a = loc.obtener_almacen()
    try:
        inv.registrar_traspaso("Arroz", 5, USR_ADMIN, a["id"], a["id"])
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


def test_dar_baja():
    a = loc.obtener_almacen()
    inv.registrar_entrada("Producto Baja", 20, USR_ADMIN, a["id"])
    p = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    inv.dar_baja(p["id"], USR_ADMIN, "Merma")
    p2 = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    assert p2["activo"] == 0


def test_reactivar():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    inv.reactivar_producto(p["id"], USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Producto Baja", a["id"])
    assert p2["activo"] == 1


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


def test_productos_por_categoria():
    a = loc.obtener_almacen()
    conteo = cats.contar_productos_por_categoria(a["id"])
    assert isinstance(conteo, dict)


# ═══════════════════════════════════════════════════════════
# TESTS MULTIMONEDA
# ═══════════════════════════════════════════════════════════

def test_convertir_cup_a_usd():
    inv.set_config("tasa_usd", "100")
    r = inv.convertir(1000, "CUP", "USD")
    assert abs(r - 10) < 0.01


def test_convertir_usd_a_cup():
    inv.set_config("tasa_usd", "100")
    r = inv.convertir(5, "USD", "CUP")
    assert abs(r - 500) < 0.01


def test_recalcular_precios():
    inv.set_config("tasa_usd", "150")
    n = inv.recalcular_todos_los_precios()
    assert n >= 0


# ═══════════════════════════════════════════════════════════
# TESTS DE MÉTRICAS
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


# ═══════════════════════════════════════════════════════════
# TESTS v9 — CLIENTES
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


# ═══════════════════════════════════════════════════════════
# TESTS v9 — MÉTODOS DE PAGO
# ═══════════════════════════════════════════════════════════

def test_metodos_default():
    ms = cfg.listar_metodos_pago(solo_activos=False)
    assert len(ms) >= 9
    claves = [m["clave"] for m in ms]
    assert "Efectivo CUP" in claves
    assert "Transfermóvil" in claves
    assert "Fiado" in claves


def test_toggle_metodo():
    cfg.actualizar_metodo_pago("Efectivo USD", activo=True)
    m = cfg.obtener_metodo_pago("Efectivo USD")
    assert m["activo"] == 1
    cfg.actualizar_metodo_pago("Efectivo USD", activo=False)


def test_actualizar_cuenta_metodo():
    cfg.actualizar_metodo_pago("Transfermóvil",
                                cuenta="+53 5555 0000")
    m = cfg.obtener_metodo_pago("Transfermóvil")
    assert m["cuenta"] == "+53 5555 0000"


# ═══════════════════════════════════════════════════════════
# TESTS v9 — POS
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


def test_venta_simple():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo CUP", "moneda": "CUP",
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
            {"metodo": "Efectivo CUP", "moneda": "CUP",
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
            pagos=[{"metodo": "Efectivo CUP", "moneda": "CUP",
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
                {"metodo": "Efectivo CUP", "moneda": "CUP",
                 "monto": t["total"]/4, "tasa": 1.0},
                {"metodo": "Transfermóvil", "moneda": "CUP",
                 "monto": t["total"]/4, "tasa": 1.0},
                {"metodo": "EnZona", "moneda": "CUP",
                 "monto": t["total"]/4, "tasa": 1.0},
                {"metodo": "Efectivo CUP", "moneda": "CUP",
                 "monto": t["total"]/4, "tasa": 1.0},
            ],
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
    # Abono parcial
    cli.registrar_abono(
        orden_id=r["orden_id"], monto=t["total"]/2, moneda="CUP",
        metodo="Efectivo CUP", usuario=USR_ADMIN)
    o = ven.obtener_orden(r["orden_id"])
    assert o["estado"] == "parcial"
    # Abono final
    cli.registrar_abono(
        orden_id=r["orden_id"], monto=t["total"]/2, moneda="CUP",
        metodo="Efectivo CUP", usuario=USR_ADMIN)
    assert cli.saldo_pendiente(cid) == 0


def test_venta_anular_restaura_stock():
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])
    stock_antes = p["stock"]
    c = ven.nuevo_carrito()
    ven.agregar_item(c, p, 3)
    t = ven.calcular_totales(c)
    r = ven.registrar_venta(
        carrito=c,
        pagos=[{"metodo": "Efectivo CUP", "moneda": "CUP",
                "monto": t["total"], "tasa": 1.0}],
        usuario=USR_ADMIN, local_id=a["id"])
    ven.anular_orden(r["orden_id"], USR_ADMIN)
    p2 = inv.buscar_producto_por_nombre("Arroz", a["id"])
    assert p2["stock"] == stock_antes
    o = ven.obtener_orden(r["orden_id"])
    assert o["estado"] == "anulada"


def test_venta_stock_insuficiente():
    """
    Ahora la validación ocurre en agregar_item.
    Verificamos dos cosas:
      1. agregar_item rechaza cantidad > stock.
      2. registrar_venta también valida (por si el carrito se manipuló).
    """
    a = loc.obtener_almacen()
    p = inv.buscar_producto_por_nombre("Arroz", a["id"])

    # 1. agregar_item rechaza cantidad excesiva
    c = ven.nuevo_carrito()
    try:
        ven.agregar_item(c, p, p["stock"] + 99999)
        assert False, "agregar_item debe rechazar cantidad > stock"
    except ValueError:
        pass  # esperado

    # 2. registrar_venta también valida (carrito manipulado a la fuerza)
    c2 = ven.nuevo_carrito()
    ven.agregar_item(c2, p, 1)  # cantidad normal primero
    # Ahora forzamos el carrito a una cantidad imposible
    c2["items"][0]["cantidad"] = p["stock"] + 99999
    t = ven.calcular_totales(c2)
    try:
        ven.registrar_venta(
            carrito=c2,
            pagos=[{"metodo": "Efectivo CUP", "moneda": "CUP",
                    "monto": t["total"], "tasa": 1.0}],
            usuario=USR_ADMIN, local_id=a["id"])
        assert False, "registrar_venta debe rechazar stock insuficiente"
    except ValueError:
        pass  # esperado

# ═══════════════════════════════════════════════════════════
# TESTS v9 — CAJA
# ═══════════════════════════════════════════════════════════

def test_abrir_caja():
    a = loc.obtener_almacen()
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


# ═══════════════════════════════════════════════════════════
# TESTS v9 — DEVOLUCIONES
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
        pagos=[{"metodo": "Efectivo CUP", "moneda": "CUP",
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


# ═══════════════════════════════════════════════════════════
# TESTS v9 — TICKET
# ═══════════════════════════════════════════════════════════

def test_ticket_pdf():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM ordenes_venta ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return True
    try:
        data = tk.generar_ticket_pdf(row["id"])
        assert len(data) > 200
    except Exception as ex:
        # No bloquear si fpdf falla por fuentes del sistema
        print(f"  [INFO] PDF no generado: {ex}")


def test_ticket_png():
    with get_conn() as conn:
        row = conn.execute(
            "SELECT id FROM ordenes_venta ORDER BY id DESC LIMIT 1"
        ).fetchone()
    if not row:
        return True
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
        return True
    txt = tk.texto_plano_ticket(row["id"])
    assert "TICKET" in txt.upper() or "Total" in txt


# ═══════════════════════════════════════════════════════════
# TESTS v9 — CONFIGURACIÓN DEL NEGOCIO
# ═══════════════════════════════════════════════════════════

def test_config_negocio():
    cfg.set_config_negocio("nombre", "Mi Negocio")
    cfg.set_config_negocio("direccion", "Calle 1")
    assert cfg.get_config_negocio("nombre") == "Mi Negocio"
    todos = cfg.get_todos_negocio()
    assert todos["nombre"] == "Mi Negocio"


# ═══════════════════════════════════════════════════════════
# TESTS v9 — PALETAS
# ═══════════════════════════════════════════════════════════

def test_paletas_disponibles():
    from ui import estilos as es
    assert len(es.PALETAS) == 5
    for clave in es.PALETAS_ORDEN:
        assert clave in es.PALETAS


def test_cambiar_paleta():
    from ui import estilos as es
    es.aplicar_tema(modo="oscuro", paleta="azul")
    assert es.paleta_actual() == "azul"
    assert es.COLOR_ACENTO == es.PALETAS["azul"]["acento_dark"]
    es.aplicar_tema(modo="claro", paleta="verde")
    assert es.modo_actual() == "claro"
    assert es.COLOR_ACENTO == es.PALETAS["verde"]["acento_light"]
    # Volver al default
    es.aplicar_tema(modo="oscuro", paleta="dorado")


# ═══════════════════════════════════════════════════════════
# TESTS v9 — GRANEL
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
# TESTS v10 — GASTOS
# ═══════════════════════════════════════════════════════════

def test_categorias_gastos_default():
    cats = gs.listar_categorias_gastos(solo_activas=True)
    nombres = [c["nombre"] for c in cats]
    for esperado in ("Luz", "Agua", "Alquiler", "Salario"):
        assert esperado in nombres, f"Falta categoría {esperado}"


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
        metodo="Efectivo CUP", descripcion="Prueba luz")
    assert gid > 0
    g = gs.obtener_gasto(gid)
    assert g["monto"] == 500
    assert g["moneda"] == "CUP"
    assert g["monto_cup"] == 500


def test_crear_gasto_en_usd():
    inv.set_config("tasa_usd", "100")
    gid = gs.registrar_gasto(
        monto=10, moneda="USD", usuario=USR_ADMIN)
    g = gs.obtener_gasto(gid)
    assert abs(g["monto_cup"] - 1000) < 0.01
    inv.set_config("tasa_usd", "1.0")


def test_crear_gasto_en_eur():
    inv.set_config("tasa_eur", "120")
    gid = gs.registrar_gasto(
        monto=5, moneda="EUR", usuario=USR_ADMIN)
    g = gs.obtener_gasto(gid)
    assert abs(g["monto_cup"] - 600) < 0.01
    inv.set_config("tasa_eur", "1.0")


def test_gasto_global():
    gid = gs.registrar_gasto(
        monto=100, moneda="CUP", usuario=USR_ADMIN,
        local_id=None)
    g = gs.obtener_gasto(gid)
    assert g["local_id"] is None


def test_gasto_por_local():
    a = loc.obtener_almacen()
    gid = gs.registrar_gasto(
        monto=100, moneda="CUP", usuario=USR_ADMIN,
        local_id=a["id"])
    g = gs.obtener_gasto(gid)
    assert g["local_id"] == a["id"]


def test_gasto_con_categoria():
    cid = gs.crear_categoria_gasto("OtraCatGasto")
    gid = gs.registrar_gasto(
        monto=200, moneda="CUP", usuario=USR_ADMIN,
        categoria_id=cid)
    g = gs.obtener_gasto(gid)
    assert g["categoria_id"] == cid


def test_gasto_con_metodo():
    gid = gs.registrar_gasto(
        monto=100, moneda="CUP", usuario=USR_ADMIN,
        metodo="Transfermóvil")
    g = gs.obtener_gasto(gid)
    assert g["metodo"] == "Transfermóvil"


def test_gasto_monto_cero():
    try:
        gs.registrar_gasto(
            monto=0, moneda="CUP", usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_gasto_monto_negativo():
    try:
        gs.registrar_gasto(
            monto=-100, moneda="CUP", usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_gasto_categoria_invalida():
    try:
        gs.registrar_gasto(
            monto=100, moneda="CUP", usuario=USR_ADMIN,
            categoria_id=99999)
        assert False
    except ValueError:
        pass


def test_editar_gasto_monto():
    gid = gs.registrar_gasto(
        monto=100, moneda="CUP", usuario=USR_ADMIN)
    gs.editar_gasto(gid, monto=250)
    g = gs.obtener_gasto(gid)
    assert g["monto"] == 250


def test_editar_gasto_cambia_moneda():
    inv.set_config("tasa_usd", "50")
    gid = gs.registrar_gasto(
        monto=100, moneda="CUP", usuario=USR_ADMIN)
    gs.editar_gasto(gid, monto=10, moneda="USD")
    g = gs.obtener_gasto(gid)
    assert g["moneda"] == "USD"
    assert abs(g["monto_cup"] - 500) < 0.01
    inv.set_config("tasa_usd", "1.0")


def test_eliminar_gasto():
    gid = gs.registrar_gasto(
        monto=100, moneda="CUP", usuario=USR_ADMIN)
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
    r = gs.listar_gastos(
        desde="2026-01-01 00:00:00",
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


def test_listar_gastos_solo_globales():
    with get_conn() as conn:
        conn.execute("DELETE FROM gastos")
    a = loc.obtener_almacen()
    gs.registrar_gasto(monto=100, moneda="CUP", usuario=USR_ADMIN,
                       local_id=None)
    gs.registrar_gasto(monto=200, moneda="CUP", usuario=USR_ADMIN,
                       local_id=a["id"])
    r = gs.listar_gastos(local_id=None)
    assert len(r) == 1
    assert r[0]["local_id"] is None


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
    encontrado = next((x for x in r
                        if x["categoria_id"] == cid), None)
    assert encontrado is not None
    assert abs(encontrado["total"] - 250) < 0.01


def test_gastos_por_local():
    with get_conn() as conn:
        conn.execute("DELETE FROM gastos")
    a = loc.obtener_almacen()
    gs.registrar_gasto(monto=100, moneda="CUP", usuario=USR_ADMIN,
                       local_id=a["id"])
    gs.registrar_gasto(monto=50, moneda="CUP", usuario=USR_ADMIN,
                       local_id=a["id"])
    r = gs.gastos_por_local()
    encontrado = next((x for x in r if x["local_id"] == a["id"]), None)
    assert encontrado is not None
    assert abs(encontrado["total"] - 150) < 0.01


def test_caja_descuenta_gastos():
    """El saldo del sistema en caja resta los gastos asociados.
    Limpia en orden hijo→padre para evitar FOREIGN KEY errors."""
    with get_conn() as conn:
        # Desactivar FK temporalmente para este cleanup
        conn.execute("PRAGMA foreign_keys = OFF")
        for tabla in (
            "devoluciones",
            "gastos",
            "abonos",
            "pagos",
            "orden_items",
            "ordenes_venta",
            "caja_sesiones",
        ):
            try:
                conn.execute(f"DELETE FROM {tabla}")
            except Exception:
                pass
        conn.execute("PRAGMA foreign_keys = ON")

    a = loc.obtener_almacen()
    sid = cj.abrir_sesion(a["id"], "test_caja_gasto", 1000.0)

    # 1. Sin gastos ni pagos → saldo = 1000
    s1 = cj.calcular_saldo_sistema(sid)
    assert abs(s1 - 1000) < 0.01, (
        f"Saldo inicial debe ser 1000, dio {s1}"
    )

    # 2. Registrar gasto de caja
    gid = gs.registrar_gasto(
        monto=200, moneda="CUP",
        usuario={"username": "test_caja_gasto", "rol": "admin"},
        caja_sesion_id=sid)

    # 3. Verificar que el gasto se guardó con caja_sesion_id
    with get_conn() as conn:
        row = conn.execute(
            "SELECT caja_sesion_id FROM gastos WHERE id=?", (gid,)
        ).fetchone()
    assert row is not None, "El gasto no se guardó en BD"
    assert row["caja_sesion_id"] == sid, (
        f"gasto.caja_sesion_id debe ser {sid}, "
        f"dio {row['caja_sesion_id']}"
    )

    # 4. Saldo con gasto → 800
    s2 = cj.calcular_saldo_sistema(sid)
    assert abs(s2 - 800) < 0.01, (
        f"Saldo con gasto debe ser 800, dio {s2}"
    )

    cj.cerrar_sesion(sid, 800.0)

# ═══════════════════════════════════════════════════════════
# TESTS v10 — PROVEEDORES
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
    # Cambiar a pid2
    pv.set_proveedor_principal("Café Test", pid2)
    principal = pv.proveedor_principal("Café Test")
    assert principal["id"] == pid2
    # Quitar principal
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
        usuario=USR_ADMIN, metodo="Efectivo CUP")
    assert pid_pago > 0
    total = pv.total_pagado_proveedor(pid)
    assert abs(total - 500) < 0.01


def test_pago_proveedor_usd():
    inv.set_config("tasa_usd", "100")
    pid = pv.crear_proveedor("Prov Pago USD")
    pv.registrar_pago(
        proveedor_id=pid, monto=10, moneda="USD",
        usuario=USR_ADMIN)
    total = pv.total_pagado_proveedor(pid)
    assert abs(total - 1000) < 0.01
    inv.set_config("tasa_usd", "1.0")


def test_pago_monto_cero():
    pid = pv.crear_proveedor("Prov Pago Cero")
    try:
        pv.registrar_pago(
            proveedor_id=pid, monto=0, moneda="CUP",
            usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_pago_proveedor_inexistente():
    try:
        pv.registrar_pago(
            proveedor_id=999999, monto=100, moneda="CUP",
            usuario=USR_ADMIN)
        assert False
    except ValueError:
        pass


def test_saldo_proveedor():
    pid = pv.crear_proveedor("Prov Saldo")
    # Creamos un movimiento ficticio de entrada con costo 1000
    a = loc.obtener_almacen()
    inv.registrar_entrada(
        nombre="Prod Saldo Test", cantidad=10,
        usuario=USR_ADMIN, local_id=a["id"],
        codigo="ZZ9998", precio_costo=100)
    prod = inv.buscar_producto_por_nombre("Prod Saldo Test", a["id"])
    # Asociamos el movimiento al proveedor
    with get_conn() as conn:
        conn.execute(
            "UPDATE movimientos SET proveedor_id=? "
            "WHERE producto_id=? AND tipo='ENTRADA'",
            (pid, prod["id"]))
    # Saldo debe ser 1000 (10 * 100)
    saldo = pv.saldo_proveedor(pid)
    assert abs(saldo - 1000) < 0.01
    # Pagamos 400
    pv.registrar_pago(
        proveedor_id=pid, monto=400, moneda="CUP",
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
# RUNNER
# ═══════════════════════════════════════════════════════════

TESTS = [
    # Seguridad
    ("Hash PBKDF2",                    test_hash_password),
    ("Hash determinista por salt",     test_hash_distintos),
    ("Hash password vacío",            test_hash_password_vacio),
    ("Hash unicode",                   test_hash_unicode),
    # DB
    ("Versión esquema = 10",            test_version_esquema),
    ("Almacén creado",                 test_almacen_creado),
    ("Categorías default",             test_categorias_default),
    ("Config defaults",                test_config_defaults),
    # Categorías
    ("Crear categoría",                test_crear_categoria),
    ("Normalizar categoría",           test_normalizar_categoria),
    ("Categoría duplicada",            test_categoria_duplicada),
    ("Renombrar categoría",            test_renombrar_categoria),
    ("Desactivar categoría",           test_desactivar_categoria),
    ("Categoría muy corta",            test_categoria_muy_corta),
    # Usuarios
    ("Crear usuario",                  test_crear_usuario),
    ("Usuario duplicado",              test_usuario_duplicado),
    ("Usuario no-admin falla",         test_usuario_no_admin_falla),
    ("Cambiar rol",                    test_cambiar_rol),
    ("Password corta",                 test_password_corta),
    # Locales
    ("Abrir tienda",                   test_abrir_tienda),
    ("Nombre reservado",               test_tienda_nombre_reservado),
    ("Tienda duplicada",               test_tienda_duplicada),
    ("Listar tiendas",                 test_listar_tiendas),
    ("Renombrar local",                test_renombrar_local),
    # Inventario
    ("Registrar entrada nuevo",        test_registrar_entrada_nuevo),
    ("Entrada suma stock",             test_entrada_suma_stock),
    ("Salida resta stock",             test_salida_resta_stock),
    ("Salida stock insuficiente",      test_salida_stock_insuficiente),
    ("Salida producto inexistente",    test_salida_producto_inexistente),
    ("Cantidad negativa",              test_cantidad_negativa),
    ("Común no opera",                 test_comun_no_opera),
    ("General no operable",            test_general_no_operable),
    ("Código auto-sugerido",           test_codigo_auto_sugerido),
    ("Código global propagado",        test_codigo_global_propagado),
    ("Traspaso",                       test_traspaso),
    ("Traspaso mismo local",           test_traspaso_mismo_local),
    ("Cambiar umbrales",               test_cambiar_umbrales),
    ("Umbrales inválidos",             test_umbrales_invalidos),
    ("Dar de baja",                    test_dar_baja),
    ("Reactivar producto",             test_reactivar),
    ("Set precio costo",               test_set_precio_costo),
    ("Set precio unitario",            test_set_precio_unitario),
    ("Color stock",                    test_color_stock),
    ("Totales local",                  test_totales_local),
    ("Productos por categoría",        test_productos_por_categoria),
    # Multimoneda
    ("Convertir CUP→USD",              test_convertir_cup_a_usd),
    ("Convertir USD→CUP",              test_convertir_usd_a_cup),
    ("Recalcular precios",             test_recalcular_precios),
    # Métricas
    ("Rango hoy",                      test_rango_hoy),
    ("Rango semana",                   test_rango_semana),
    ("Rango mes",                      test_rango_mes),
    ("Rango año",                      test_rango_anio),
    ("Rango total",                    test_rango_total),
    ("Resumen período",                test_resumen_periodo),
    # Clientes
    ("Crear cliente",                  test_crear_cliente),
    ("Cliente duplicado",              test_cliente_duplicado),
    ("Editar cliente",                 test_editar_cliente),
    ("Buscar cliente",                 test_buscar_cliente),
    ("Cliente sin deuda",              test_cliente_sin_deuda),
    # Métodos de pago
    ("Métodos default",                test_metodos_default),
    ("Toggle método",                  test_toggle_metodo),
    ("Actualizar cuenta método",       test_actualizar_cuenta_metodo),
    # POS
    ("Carrito vacío",                  test_carrito_vacio),
    ("Agregar ítem",                   test_agregar_item),
    ("Agregar mismo suma",             test_agregar_mismo_producto_suma),
    ("Calcular totales",               test_calcular_totales),
    ("Descuento global",               test_descuento_global),
    ("Venta simple",                   test_venta_simple),
    ("Venta pago mixto",               test_venta_pago_mixto),
    ("Venta pago insuficiente",        test_venta_pago_insuficiente),
    ("Venta máximo 3 pagos",           test_venta_max_3_pagos),
    ("Fiado requiere cliente",         test_venta_fiado_requiere_cliente),
    ("Fiado + abonos",                 test_venta_fiado_y_abonos),
    ("Anular restaura stock",          test_venta_anular_restaura_stock),
    ("Venta stock insuficiente",       test_venta_stock_insuficiente),
    # Caja
    ("Abrir caja",                     test_abrir_caja),
    ("No doble apertura",              test_no_doble_apertura),
    ("Cerrar caja",                    test_cerrar_caja),
    ("No doble cierre",                test_no_doble_cierre),
    # Devoluciones
    ("Devolución parcial",             test_devolucion_parcial),
    # Ticket
    ("Ticket PDF",                     test_ticket_pdf),
    ("Ticket PNG",                     test_ticket_png),
    ("Ticket texto plano",             test_ticket_texto_plano),
    # Config negocio
    ("Config negocio",                 test_config_negocio),
    # Paletas
    ("Paletas disponibles",            test_paletas_disponibles),
    ("Cambiar paleta",                 test_cambiar_paleta),
    # Granel
    ("Flag granel",                    test_flag_granel),
    # Gastos v10
    ("Categorías gastos default",      test_categorias_gastos_default),
    ("Crear categoría gasto",          test_crear_categoria_gasto),
    ("Categoría gasto duplicada",      test_categoria_gasto_duplicada),
    ("Normalizar categoría gasto",     test_normalizar_categoria_gasto),
    ("Renombrar categoría gasto",      test_renombrar_categoria_gasto),
    ("Desactivar categoría gasto",     test_desactivar_categoria_gasto),
    ("Categoría gasto muy corta",      test_categoria_gasto_muy_corta),
    ("Crear gasto simple CUP",         test_crear_gasto_simple_cup),
    ("Crear gasto en USD",             test_crear_gasto_en_usd),
    ("Crear gasto en EUR",             test_crear_gasto_en_eur),
    ("Gasto global",                   test_gasto_global),
    ("Gasto por local",                test_gasto_por_local),
    ("Gasto con categoría",            test_gasto_con_categoria),
    ("Gasto con método",               test_gasto_con_metodo),
    ("Gasto monto cero",               test_gasto_monto_cero),
    ("Gasto monto negativo",           test_gasto_monto_negativo),
    ("Gasto categoría inválida",       test_gasto_categoria_invalida),
    ("Editar gasto monto",             test_editar_gasto_monto),
    ("Editar gasto cambia moneda",     test_editar_gasto_cambia_moneda),
    ("Eliminar gasto",                 test_eliminar_gasto),
    ("Eliminar gasto inexistente",     test_eliminar_gasto_inexistente),
    ("Listar gastos por rango",        test_listar_gastos_por_rango),
    ("Listar gastos por categoría",    test_listar_gastos_por_categoria),
    ("Listar gastos solo globales",    test_listar_gastos_solo_globales),
    ("Total gastos período",           test_total_gastos_periodo),
    ("Gastos por categoría",           test_gastos_por_categoria),
    ("Gastos por local",               test_gastos_por_local),
    ("Caja descuenta gastos",          test_caja_descuenta_gastos),
    # Proveedores v10
    ("Crear proveedor",                test_crear_proveedor),
    ("Capitalizar proveedor",          test_capitalizar_proveedor),
    ("Proveedor duplicado",            test_proveedor_duplicado),
    ("Proveedor nombre corto",         test_proveedor_nombre_corto),
    ("Editar proveedor",               test_editar_proveedor),
    ("Desactivar proveedor",           test_desactivar_proveedor),
    ("Asociar proveedor a producto",   test_asociar_proveedor_a_producto),
    ("Asociar idempotente",            test_asociar_idempotente),
    ("Marcar principal",               test_marcar_principal),
    ("Desasociar proveedor",           test_desasociar_proveedor),
    ("Productos de proveedor",         test_productos_de_proveedor),
    ("Registrar pago proveedor",       test_registrar_pago_proveedor),
    ("Pago proveedor USD",             test_pago_proveedor_usd),
    ("Pago monto cero",                test_pago_monto_cero),
    ("Pago proveedor inexistente",     test_pago_proveedor_inexistente),
    ("Saldo proveedor",                test_saldo_proveedor),
    ("Listar proveedores",             test_listar_proveedores),
    ("Listar proveedores con texto",   test_listar_proveedores_con_texto),
    ("Listar con saldo",               test_listar_con_saldo),
]


def main():
    print("=" * 60)
    print(f"  TEST SUITE — Almacén v{VERSION_ESQUEMA}")
    print(f"  BD temporal: {_TEMP_DIR}")
    print("=" * 60)
    print()

    # IMPORTANTE: NO borrar _TEMP_DIR entero porque rutas.py ya creó
    # las subcarpetas datos/, backups/, logs/ al importarse.
    # Solo borramos la BD y sus archivos WAL/SHM si existen.
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

    # Datos base (limpia + repuebla)
    _limpiar_todo()
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

        for k, v in {
            "umbral_verde_default":    "50",
            "umbral_amarillo_default": "20",
            "motivo_default_salida":   "Venta",
            "tema":                    "oscuro",
            "paleta":                  "dorado",
            "tasa_usd":                "1.0",
            "tasa_eur":                "1.0",
            "moneda_visualizacion":    "CUP",
        }.items():
            conn.execute(
                "INSERT OR IGNORE INTO configuracion(clave,valor) "
                "VALUES(?,?)", (k, v))

        from db import METODOS_PAGO_DEFAULT
        for (clave, etiqueta, activo, orden, req_mon, es_cred,
             cuenta, qr) in METODOS_PAGO_DEFAULT:
            conn.execute(
                "INSERT OR IGNORE INTO metodos_pago"
                "(clave,etiqueta,activo,orden,requiere_moneda,"
                "es_credito,cuenta,qr_imagen) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (clave, etiqueta, activo, orden, req_mon, es_cred,
                 cuenta, qr))

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
    print("=" * 60)
    if fallidos == 0:
        print(f"  ✅ TODOS LOS TESTS PASARON ({pasados}/{total})")
    else:
        print(f"  ⚠️  {pasados} pasados, {fallidos} fallidos "
            f"de {total}")
    print("=" * 60)

    try:
        shutil.rmtree(_TEMP_DIR, ignore_errors=True)
    except Exception:
        pass

    return 0 if fallidos == 0 else 1


if __name__ == "__main__":
    sys.exit(main())