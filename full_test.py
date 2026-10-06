"""
full_test.py — Test EXHAUSTIVO de todas las funcionalidades.

Verifica cada función, cada fix aplicado, cada validación y cada
caso borde. Cubre ~65 tests.

Uso:
    python full_test.py

Crea una BD temporal en ./_test_full/, ejecuta todos los tests, y
al final borra esa carpeta. NO toca la BD real.
"""
import os
import sys
import shutil
from datetime import datetime
from pathlib import Path

# ============================================================
# Preparar entorno ANTES de importar db.py
# ============================================================
TEST_DIR = Path("./_test_full").absolute()
if TEST_DIR.exists():
    shutil.rmtree(TEST_DIR)
TEST_DIR.mkdir(parents=True)
os.environ["FLET_APP_STORAGE_DATA"] = str(TEST_DIR)

# ============================================================
# Imports (ya con el env var puesto)
# ============================================================
from db import (inicializar_db, get_conn, GENERAL_ID,
                get_pref, set_pref)
import inventario as inv
import locales as loc
import usuarios as um
from seguridad import crear_hash, verificar_password, generar_salt


# ============================================================
# Test runner
# ============================================================
class TestRunner:
    def __init__(self):
        self.pasados = 0
        self.fallados = 0
        self.errores = []

    def test(self, nombre, fn):
        try:
            fn()
            self.pasados += 1
            print(f"  \033[92m✓\033[0m {nombre}")
        except AssertionError as e:
            self.fallados += 1
            self.errores.append((nombre, str(e)))
            print(f"  \033[91m✗\033[0m {nombre}: {e}")
        except Exception as e:
            self.fallados += 1
            msg = f"{type(e).__name__}: {e}"
            self.errores.append((nombre, msg))
            print(f"  \033[91m💥\033[0m {nombre}: {msg}")

    def resumen(self):
        total = self.pasados + self.fallados
        print()
        print("=" * 66)
        if self.fallados == 0:
            print(f"  \033[92m✅ TODOS LOS TESTS PASARON "
                  f"({self.pasados}/{total})\033[0m")
        else:
            print(f"  \033[91m❌ {self.fallados}/{total} "
                  f"tests fallados\033[0m")
            print()
            for n, e in self.errores:
                print(f"    - {n}: {e}")
        print("=" * 66)
        return self.fallados == 0


# ============================================================
# Helpers de aserción
# ============================================================
def eq(a, b, msg=""):
    assert a == b, f"{msg}: esperado={b!r} obtenido={a!r}"

def ne(a, b, msg=""):
    assert a != b, f"{msg}: no debe ser {b!r}"

def gt(a, b, msg=""):
    assert a > b, f"{msg}: {a!r} debe ser > {b!r}"

def ge(a, b, msg=""):
    assert a >= b, f"{msg}: {a!r} debe ser >= {b!r}"

def lt(a, b, msg=""):
    assert a < b, f"{msg}: {a!r} debe ser < {b!r}"

def raises(exc_type, fn, msg=""):
    try:
        fn()
    except exc_type:
        return
    except Exception as e:
        raise AssertionError(
            f"{msg}: esperaba {exc_type.__name__}, llegó "
            f"{type(e).__name__}: {e}"
        )
    raise AssertionError(
        f"{msg}: no lanzó excepción (se esperaba {exc_type.__name__})"
    )


# ============================================================
# Globals de test
# ============================================================
ADMIN = {"username": "admin", "rol": "admin"}
ALMACEN_ID = None
CENTRO_ID = None
VEDADO_ID = None


# ============================================================
# Setup
# ============================================================
def setup():
    print("\n\033[94m[SETUP] Inicializando base de datos "
          "temporal…\033[0m")
    inicializar_db()
    h, s = crear_hash("admin1234")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO usuarios(username,password_hash,salt,rol,"
            "creado) VALUES(?,?,?,'admin',?)",
            ("admin", h, s,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
    print(f"  BD creada en: {TEST_DIR}")


# ============================================================
# 1. Inicialización BD
# ============================================================
def test_db_inicializacion(t):
    def check_tablas():
        with get_conn() as conn:
            for tabla in ["meta", "locales", "usuarios",
                          "configuracion", "productos", "movimientos"]:
                row = conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table' AND name=?",
                    (tabla,)
                ).fetchone()
                assert row is not None, f"Falta tabla {tabla}"
    t.test("BD: todas las tablas existen", check_tablas)

    def check_version():
        with get_conn() as conn:
            row = conn.execute(
                "SELECT valor FROM meta WHERE clave='version_esquema'"
            ).fetchone()
            assert row is not None
            eq(int(row["valor"]), 6, "version_esquema")
    t.test("BD: version_esquema = 6", check_version)

    def check_almacen():
        global ALMACEN_ID
        alm = loc.obtener_almacen()
        assert alm is not None, "Almacén no auto-creado"
        eq(alm["nombre"], "Almacén")
        eq(alm["es_almacen"], 1)
        ALMACEN_ID = alm["id"]
    t.test("BD: Almacén auto-creado", check_almacen)

    def check_defaults():
        eq(get_pref("motivo_default_salida"), "Venta",
           "motivo por defecto debe ser Venta (fix #1)")
        eq(get_pref("tasa_usd"), "1.0", "tasa_usd default")
        eq(get_pref("tema"), "oscuro", "tema default")
    t.test("BD: defaults (motivo=Venta, tasa_usd=1.0)",
           check_defaults)


# ============================================================
# 2. Seguridad (hash de passwords)
# ============================================================
def test_seguridad(t):
    def hash_verifica():
        h, s = crear_hash("micontraseña")
        assert verificar_password("micontraseña", s, h)
        assert not verificar_password("otra", s, h)
    t.test("Seguridad: hash + verificar", hash_verifica)

    def salt_unico():
        s1 = generar_salt()
        s2 = generar_salt()
        ne(s1, s2, "los salts deben ser distintos")
        eq(len(s1), 32, "salt hex 16 bytes = 32 chars")
    t.test("Seguridad: salt único de 16 bytes", salt_unico)


# ============================================================
# 3. Configuración
# ============================================================
def test_config(t):
    def cambio_motivo():
        inv.set_config("motivo_default_salida", "Combos")
        eq(inv.motivo_default_salida(), "Combos")
        inv.set_config("motivo_default_salida", "Venta")
        eq(inv.motivo_default_salida(), "Venta")
    t.test("Config: cambiar motivo_default_salida", cambio_motivo)

    def cambio_tasa():
        inv.set_config("tasa_usd", "250")
        eq(inv.get_tasa_usd(), 250.0)
        inv.set_config("tasa_usd", "1.0")
    t.test("Config: cambiar tasa_usd", cambio_tasa)

    def tasa_invalida():
        inv.set_config("tasa_usd", "abc")
        eq(inv.get_tasa_usd(), 1.0, "fallback a 1.0")
        inv.set_config("tasa_usd", "1.0")
    t.test("Config: tasa_usd inválida → fallback 1.0",
           tasa_invalida)

    def umbrales_default():
        uv, ua = inv.get_umbrales_default()
        eq(uv, 50)
        eq(ua, 20)
    t.test("Config: umbrales por defecto (50, 20)",
           umbrales_default)


# ============================================================
# 4. Usuarios
# ============================================================
def test_usuarios(t):
    def crear():
        uid = um.crear_usuario("juan", "pass1234", "almacen", ADMIN)
        gt(uid, 0)
        u = um.obtener_usuario(uid)
        eq(u["username"], "juan")
        eq(u["rol"], "almacen")
    t.test("Usuarios: crear usuario", crear)

    def duplicado():
        raises(um.UsuarioYaExiste,
               lambda: um.crear_usuario("juan", "x1234",
                                        "comun", ADMIN))
    t.test("Usuarios: no permite duplicados", duplicado)

    def password_corta():
        raises(ValueError,
               lambda: um.crear_usuario("pedro", "abc",
                                        "comun", ADMIN))
    t.test("Usuarios: password < 4 rechazado", password_corta)

    def username_corto():
        raises(ValueError,
               lambda: um.crear_usuario("ab", "pass1234",
                                        "comun", ADMIN))
    t.test("Usuarios: username < 3 rechazado", username_corto)

    def rol_invalido():
        raises(ValueError,
               lambda: um.crear_usuario("pedro", "pass1234",
                                        "super", ADMIN))
    t.test("Usuarios: rol inválido rechazado", rol_invalido)

    def no_admin_puede_crear():
        raises(PermissionError,
               lambda: um.crear_usuario(
                   "x", "pass1234", "comun",
                   {"username": "juan", "rol": "almacen"}))
    t.test("Usuarios: solo admin puede crear",
           no_admin_puede_crear)

    def actualizar_perfil():
        uid = um.crear_usuario("test_act", "old1234", "comun", ADMIN)
        nuevo = um.actualizar_perfil(uid, "test_act_renamed",
                                     "old1234", "new1234")
        eq(nuevo["username"], "test_act_renamed")
        u = um.obtener_usuario(uid)
        assert verificar_password("new1234", u["salt"],
                                   u["password_hash"])
    t.test("Usuarios: actualizar perfil (username + password)",
           actualizar_perfil)

    def password_actual_mala():
        uid = um.crear_usuario("test_pwd", "correct", "comun", ADMIN)
        raises(um.PasswordIncorrecta,
               lambda: um.actualizar_perfil(uid, "test_pwd",
                                            "wrong", None))
    t.test("Usuarios: password actual incorrecta rechazada",
           password_actual_mala)

    def cambiar_rol():
        uid = um.crear_usuario("test_rol", "pass1234", "comun", ADMIN)
        um.cambiar_rol(uid, "almacen", ADMIN)
        eq(um.obtener_usuario(uid)["rol"], "almacen")
    t.test("Usuarios: cambiar rol", cambiar_rol)

    # FIX: usar username único "test_toggle" en vez de "test_act2"
    def activar_desactivar():
        uid = um.crear_usuario("test_toggle", "pass1234",
                               "comun", ADMIN)
        um.activar_usuario(uid, False, ADMIN)
        eq(um.obtener_usuario(uid)["activo"], 0)
        um.activar_usuario(uid, True, ADMIN)
        eq(um.obtener_usuario(uid)["activo"], 1)
    t.test("Usuarios: activar/desactivar", activar_desactivar)

    def resetear_password():
        uid = um.crear_usuario("test_reset", "pass1234",
                               "comun", ADMIN)
        um.resetear_password(uid, "nuevo1234", ADMIN)
        u = um.obtener_usuario(uid)
        assert verificar_password("nuevo1234", u["salt"],
                                   u["password_hash"])
    t.test("Usuarios: resetear password", resetear_password)

    def eliminar_propio():
        raises(ValueError,
               lambda: um.eliminar_usuario(
                   ADMIN.get("id", 1), 1, ADMIN))
    t.test("Usuarios: no eliminar propio usuario", eliminar_propio)

    def listar_solo_admin():
        raises(PermissionError,
               lambda: um.listar_usuarios(
                   {"username": "x", "rol": "comun"}))
    t.test("Usuarios: listar solo admin", listar_solo_admin)


# ============================================================
# 5. Locales
# ============================================================
def test_locales(t):
    global CENTRO_ID, VEDADO_ID

    def crear():
        global CENTRO_ID
        CENTRO_ID = loc.abrir_tienda("Centro")
        gt(CENTRO_ID, 0)
        c = loc.obtener_local(CENTRO_ID)
        eq(c["nombre"], "Centro")
        eq(c["es_almacen"], 0)
    t.test("Locales: abrir tienda", crear)

    def crear_segunda():
        global VEDADO_ID
        VEDADO_ID = loc.abrir_tienda("Vedado")
        gt(VEDADO_ID, 0)
    t.test("Locales: abrir segunda tienda", crear_segunda)

    def duplicado():
        raises(ValueError, lambda: loc.abrir_tienda("Centro"))
    t.test("Locales: nombre duplicado rechazado", duplicado)

    def reservados():
        raises(ValueError, lambda: loc.abrir_tienda("Almacén"))
        raises(ValueError, lambda: loc.abrir_tienda("General"))
    t.test("Locales: nombres reservados rechazados", reservados)

    def corto():
        raises(ValueError, lambda: loc.abrir_tienda("A"))
    t.test("Locales: nombre muy corto rechazado", corto)

    def renombrar():
        loc.renombrar_local(VEDADO_ID, "Vedado Nuevo")
        eq(loc.obtener_local(VEDADO_ID)["nombre"], "Vedado Nuevo")
        loc.renombrar_local(VEDADO_ID, "Vedado")
    t.test("Locales: renombrar", renombrar)

    def no_renombrar_almacen():
        raises(ValueError,
               lambda: loc.renombrar_local(ALMACEN_ID, "Otro"))
    t.test("Locales: no renombrar Almacén",
           no_renombrar_almacen)

    def listar_activos():
        activos = loc.listar_locales(solo_activos=True)
        ge(len(activos), 3, "Almacén + Centro + Vedado")
    t.test("Locales: listar activos", listar_activos)

    def listar_tiendas():
        tiendas = loc.listar_tiendas(solo_activas=True)
        eq(len(tiendas), 2, "Centro + Vedado")
        for ti in tiendas:
            eq(ti["es_almacen"], 0)
    t.test("Locales: listar solo tiendas", listar_tiendas)

    def es_almacen():
        assert loc.es_almacen(ALMACEN_ID)
        assert not loc.es_almacen(CENTRO_ID)
    t.test("Locales: es_almacen", es_almacen)

    def es_general():
        assert loc.es_general(GENERAL_ID)
        assert not loc.es_general(ALMACEN_ID)
    t.test("Locales: es_general", es_general)

    def menu():
        items = loc.listar_para_menu()
        ge(len(items), 3)
        eq(items[0][0], GENERAL_ID, "General va primero")
    t.test("Locales: listar_para_menu empieza con General", menu)


# ============================================================
# 6. Códigos Fxyyyy
# ============================================================
def test_codigos(t):
    def normalizar():
        eq(inv.normalizar_codigo("  fa0001  "), "FA0001")
        eq(inv.normalizar_codigo("fa 0001"), "FA0001")
        eq(inv.normalizar_codigo("Fa0001"), "FA0001")
        eq(inv.normalizar_codigo(""), None)
        eq(inv.normalizar_codigo(None), None)
    t.test("Códigos: normalizar", normalizar)

    def primero_local_vacio():
        nuevo = loc.abrir_tienda("Test Codigos")
        eq(inv.siguiente_codigo(nuevo), "FA0001")
    t.test("Códigos: primer código FA0001 en local vacío",
           primero_local_vacio)

    def secuencia():
        nuevo = loc.abrir_tienda("Test Secuencia")
        inv.registrar_entrada("C1", 1, ADMIN, nuevo, codigo="FA0001")
        eq(inv.siguiente_codigo(nuevo), "FA0002")
        inv.registrar_entrada("C2", 1, ADMIN, nuevo, codigo="FA0002")
        inv.registrar_entrada("C3", 1, ADMIN, nuevo, codigo="FA0003")
        eq(inv.siguiente_codigo(nuevo), "FA0004")
    t.test("Códigos: secuencia incrementa", secuencia)

    def no_cuenta_codigos_raros():
        nuevo = loc.abrir_tienda("Test Raros")
        inv.registrar_entrada("R1", 1, ADMIN, nuevo, codigo="ABC123")
        eq(inv.siguiente_codigo(nuevo), "FA0001",
           "códigos sin formato Fxyyyy se ignoran")
    t.test("Códigos: ignora códigos que no son Fxyyyy",
           no_cuenta_codigos_raros)


# ============================================================
# 7. Entradas
# ============================================================
def test_entradas(t):
    def nueva():
        info = inv.registrar_entrada(
            "Producto Nuevo 1", 50, ADMIN, ALMACEN_ID,
            codigo="FB0001", precio_costo=10, precio_unitario=20)
        eq(info["stock"], 50)
        eq(info["nombre"], "Producto Nuevo 1")
    t.test("Entrada: crear producto nuevo", nueva)

    def existente_con_mismo_codigo():
        """FIX BUG #2: antes fallaba por código duplicado."""
        info = inv.registrar_entrada(
            "Producto Nuevo 1", 30, ADMIN, ALMACEN_ID,
            codigo="FB0001", precio_costo=10, precio_unitario=20)
        eq(info["stock"], 80, "stock acumulado")
    t.test("Entrada: sumar stock con mismo código (FIX BUG)",
           existente_con_mismo_codigo)

    def existente_sin_codigo():
        info = inv.registrar_entrada(
            "Producto Nuevo 1", 10, ADMIN, ALMACEN_ID)
        eq(info["stock"], 90)
    t.test("Entrada: producto existente sin código",
           existente_sin_codigo)

    def cantidad_invalida():
        raises(ValueError,
               lambda: inv.registrar_entrada("X", 0, ADMIN,
                                             ALMACEN_ID))
        raises(ValueError,
               lambda: inv.registrar_entrada("X", -5, ADMIN,
                                             ALMACEN_ID))
    t.test("Entrada: cantidad <= 0 rechazada", cantidad_invalida)

    def nombre_vacio():
        raises(ValueError,
               lambda: inv.registrar_entrada("", 10, ADMIN,
                                             ALMACEN_ID))
        raises(ValueError,
               lambda: inv.registrar_entrada("   ", 10, ADMIN,
                                             ALMACEN_ID))
    t.test("Entrada: nombre vacío rechazado", nombre_vacio)

    def rol_comun():
        raises(PermissionError,
               lambda: inv.registrar_entrada(
                   "X", 10,
                   {"username": "pepe", "rol": "comun"},
                   ALMACEN_ID))
    t.test("Entrada: rol común no puede", rol_comun)

    def general_bloqueado():
        raises(ValueError,
               lambda: inv.registrar_entrada("X", 10, ADMIN,
                                             GENERAL_ID))
    t.test("Entrada: General bloqueado", general_bloqueado)

    def codigo_duplicado_otro():
        raises(ValueError,
               lambda: inv.registrar_entrada(
                   "Otro Producto Distinto", 10, ADMIN,
                   ALMACEN_ID, codigo="FB0001"))
    t.test("Entrada: código duplicado en otro producto rechazado",
           codigo_duplicado_otro)

    def fecha_personalizada():
        info = inv.registrar_entrada(
            "Producto Retro", 5, ADMIN, ALMACEN_ID,
            fecha="2025-01-15 10:30:00")
        p = inv.buscar_producto_por_nombre("Producto Retro",
                                            ALMACEN_ID)
        with get_conn() as conn:
            row = conn.execute(
                "SELECT fecha FROM movimientos "
                "WHERE producto_id=? AND tipo='ENTRADA' "
                "ORDER BY id DESC LIMIT 1",
                (p["id"],)
            ).fetchone()
            eq(row["fecha"], "2025-01-15 10:30:00")
    t.test("Entrada: fecha personalizada", fecha_personalizada)


# ============================================================
# 8. Salidas
# ============================================================
def test_salidas(t):
    inv.registrar_entrada("Prod Salida", 100, ADMIN, ALMACEN_ID,
                          codigo="FC0001", precio_costo=5,
                          precio_unitario=10)

    def normal():
        info = inv.registrar_salida("Prod Salida", 10, ADMIN,
                                     ALMACEN_ID, motivo="Venta")
        eq(info["stock"], 90)
    t.test("Salida: normal", normal)

    def motivo_default():
        """FIX #1: motivo por defecto es Venta."""
        inv.registrar_salida("Prod Salida", 5, ADMIN, ALMACEN_ID)
        with get_conn() as conn:
            row = conn.execute(
                "SELECT motivo FROM movimientos WHERE tipo='SALIDA' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            eq(row["motivo"], "Venta", "motivo por defecto")
    t.test("Salida: motivo por defecto = Venta (FIX #1)",
           motivo_default)

    def con_rebaja():
        info = inv.registrar_salida("Prod Salida", 5, ADMIN,
                                     ALMACEN_ID, motivo="Venta",
                                     rebaja=2.0)
        eq(info["stock"], 80)
    t.test("Salida: con rebaja", con_rebaja)

    def stock_insuficiente():
        raises(inv.StockInsuficiente,
               lambda: inv.registrar_salida("Prod Salida", 9999,
                                             ADMIN, ALMACEN_ID))
    t.test("Salida: stock insuficiente", stock_insuficiente)

    def producto_inexistente():
        raises(inv.ProductoNoExiste,
               lambda: inv.registrar_salida("NoExiste", 1, ADMIN,
                                             ALMACEN_ID))
    t.test("Salida: producto no existe", producto_inexistente)

    def rebaja_mayor_precio():
        raises(ValueError,
               lambda: inv.registrar_salida(
                   "Prod Salida", 1, ADMIN, ALMACEN_ID, rebaja=100))
    t.test("Salida: rebaja > precio rechazada",
           rebaja_mayor_precio)

    def por_codigo():
        info = inv.registrar_salida("FC0001", 3, ADMIN,
                                     ALMACEN_ID, motivo="Venta")
        eq(info["stock"], 77)
    t.test("Salida: por código", por_codigo)

    def cantidad_negativa():
        raises(ValueError,
               lambda: inv.registrar_salida("Prod Salida", -1,
                                             ADMIN, ALMACEN_ID))
    t.test("Salida: cantidad negativa rechazada",
           cantidad_negativa)

    def fecha_personalizada():
        inv.registrar_salida("Prod Salida", 2, ADMIN, ALMACEN_ID,
                              motivo="Venta",
                              fecha="2025-06-20 14:00:00")
        with get_conn() as conn:
            row = conn.execute(
                "SELECT fecha FROM movimientos WHERE tipo='SALIDA' "
                "ORDER BY id DESC LIMIT 1"
            ).fetchone()
            eq(row["fecha"], "2025-06-20 14:00:00")
    t.test("Salida: fecha personalizada", fecha_personalizada)

    def general_bloqueado():
        raises(ValueError,
               lambda: inv.registrar_salida("X", 1, ADMIN,
                                             GENERAL_ID))
    t.test("Salida: General bloqueado", general_bloqueado)


# ============================================================
# 9. Traspasos
# ============================================================
def test_traspasos(t):
    inv.registrar_entrada("Prod Traspaso", 100, ADMIN, ALMACEN_ID,
                          codigo="FD0001", precio_costo=2,
                          precio_unitario=4)

    def normal():
        inv.registrar_traspaso("Prod Traspaso", 30, ADMIN,
                                ALMACEN_ID, CENTRO_ID)
        pa = inv.buscar_producto_por_nombre("Prod Traspaso",
                                             ALMACEN_ID)
        pc = inv.buscar_producto_por_nombre("Prod Traspaso",
                                             CENTRO_ID)
        eq(pa["stock"], 70)
        eq(pc["stock"], 30)
    t.test("Traspaso: Almacén → Centro", normal)

    def origen_igual_destino():
        raises(ValueError,
               lambda: inv.registrar_traspaso(
                   "Prod Traspaso", 5, ADMIN, ALMACEN_ID,
                   ALMACEN_ID))
    t.test("Traspaso: origen=destino rechazado",
           origen_igual_destino)

    def general_bloqueado():
        raises(ValueError,
               lambda: inv.registrar_traspaso(
                   "X", 5, ADMIN, GENERAL_ID, CENTRO_ID))
    t.test("Traspaso: General bloqueado", general_bloqueado)

    def stock_insuficiente():
        raises(inv.StockInsuficiente,
               lambda: inv.registrar_traspaso(
                   "Prod Traspaso", 9999, ADMIN, ALMACEN_ID,
                   CENTRO_ID))
    t.test("Traspaso: stock insuficiente", stock_insuficiente)

    def cantidad_negativa():
        raises(ValueError,
               lambda: inv.registrar_traspaso(
                   "Prod Traspaso", -1, ADMIN, ALMACEN_ID, CENTRO_ID))
    t.test("Traspaso: cantidad negativa rechazada",
           cantidad_negativa)

    def comparte_codigo():
        pc = inv.buscar_producto_por_nombre("Prod Traspaso",
                                             CENTRO_ID)
        eq(pc["codigo"], "FD0001",
           "el código se replica al traspasar")
    t.test("Traspaso: mismo código en destino", comparte_codigo)


# ============================================================
# 10. Precios (costo/venta + propagación)
# ============================================================
def test_precios(t):
    inv.registrar_entrada("Prod Precio", 50, ADMIN, ALMACEN_ID,
                          codigo="FE0001", precio_costo=10,
                          precio_unitario=20)
    p = inv.buscar_producto_por_codigo("FE0001", ALMACEN_ID)

    def cambiar_costo():
        inv.set_precio_costo(p["id"], 15.5, ADMIN)
        p2 = inv.buscar_producto_por_codigo("FE0001", ALMACEN_ID)
        eq(p2["precio_costo"], 15.5)
    t.test("Precio: cambiar costo", cambiar_costo)

    def cambiar_venta():
        inv.set_precio_unitario(p["id"], 35.0, ADMIN)
        p2 = inv.buscar_producto_por_codigo("FE0001", ALMACEN_ID)
        eq(p2["precio_unitario"], 35.0)
    t.test("Precio: cambiar venta", cambiar_venta)

    def propagacion():
        inv.registrar_entrada("Prod Precio", 20, ADMIN, CENTRO_ID,
                              codigo="FE0001", precio_costo=10,
                              precio_unitario=20)
        pa = inv.buscar_producto_por_codigo("FE0001", ALMACEN_ID)
        inv.set_precio_unitario(pa["id"], 99.0, ADMIN)
        pc = inv.buscar_producto_por_codigo("FE0001", CENTRO_ID)
        eq(pc["precio_unitario"], 99.0, "propagación a Centro")
        inv.set_precio_unitario(pa["id"], 35.0, ADMIN)
    t.test("Precio: propagación a otros locales", propagacion)

    def negativo():
        raises(ValueError,
               lambda: inv.set_precio_costo(p["id"], -5, ADMIN))
        raises(ValueError,
               lambda: inv.set_precio_unitario(p["id"], -5, ADMIN))
    t.test("Precio: negativo rechazado", negativo)

    def comun_bloqueado():
        raises(PermissionError,
               lambda: inv.set_precio_costo(
                   p["id"], 5,
                   {"username": "x", "rol": "comun"}))
    t.test("Precio: rol común bloqueado", comun_bloqueado)


# ============================================================
# 11. Edición de código
# ============================================================
def test_codigo_edicion(t):
    inv.registrar_entrada("Prod Cod", 10, ADMIN, ALMACEN_ID,
                          codigo="FF0001")
    p = inv.buscar_producto_por_codigo("FF0001", ALMACEN_ID)

    def cambiar():
        inv.set_codigo(p["id"], "FF9999", ADMIN)
        assert inv.buscar_producto_por_codigo("FF9999", ALMACEN_ID)
    t.test("Código: cambiar", cambiar)

    def duplicado():
        inv.registrar_entrada("Prod Cod 2", 10, ADMIN, ALMACEN_ID,
                              codigo="FG0001")
        p2 = inv.buscar_producto_por_codigo("FG0001", ALMACEN_ID)
        raises(ValueError,
               lambda: inv.set_codigo(p2["id"], "FF9999", ADMIN))
    t.test("Código: duplicado rechazado", duplicado)

    def vacio_permitido():
        inv.set_codigo(p["id"], "", ADMIN)
        p2 = inv.buscar_producto_por_codigo("FF9999", ALMACEN_ID)
        assert p2 is None
    t.test("Código: vacío permitido", vacio_permitido)


# ============================================================
# 12. Renombrar
# ============================================================
def test_renombrar(t):
    inv.registrar_entrada("Prod Viejo", 10, ADMIN, ALMACEN_ID,
                          codigo="FH0001")
    p = inv.buscar_producto_por_codigo("FH0001", ALMACEN_ID)

    def normal():
        inv.renombrar_producto(p["id"], "Prod Nuevo", ADMIN)
        p2 = inv.buscar_producto_por_codigo("FH0001", ALMACEN_ID)
        eq(p2["nombre"], "Prod Nuevo")
    t.test("Renombrar: normal", normal)

    def vacio():
        raises(ValueError,
               lambda: inv.renombrar_producto(p["id"], "", ADMIN))
    t.test("Renombrar: vacío rechazado", vacio)

    def igual():
        raises(ValueError,
               lambda: inv.renombrar_producto(p["id"], "Prod Nuevo",
                                              ADMIN))
    t.test("Renombrar: igual rechazado", igual)

    def colision():
        inv.registrar_entrada("Otro Nombre", 10, ADMIN, ALMACEN_ID,
                              codigo="FI0001")
        p2 = inv.buscar_producto_por_codigo("FI0001", ALMACEN_ID)
        raises(ValueError,
               lambda: inv.renombrar_producto(p2["id"],
                                              "Prod Nuevo", ADMIN))
    t.test("Renombrar: colisión rechazada", colision)


# ============================================================
# 13. Umbrales
# ============================================================
def test_umbrales(t):
    inv.registrar_entrada("Prod Umbral", 100, ADMIN, ALMACEN_ID,
                          codigo="FJ0001")
    p = inv.buscar_producto_por_codigo("FJ0001", ALMACEN_ID)

    def cambiar():
        inv.cambiar_umbrales(p["id"], 30, 10, ADMIN)
        p2 = inv.buscar_producto_por_codigo("FJ0001", ALMACEN_ID)
        eq(p2["umbral_verde"], 30)
        eq(p2["umbral_amarillo"], 10)
    t.test("Umbrales: cambiar", cambiar)

    def verde_menor():
        raises(ValueError,
               lambda: inv.cambiar_umbrales(p["id"], 10, 20, ADMIN))
    t.test("Umbrales: verde <= amarillo rechazado", verde_menor)

    def negativo():
        raises(ValueError,
               lambda: inv.cambiar_umbrales(p["id"], 10, -5, ADMIN))
    t.test("Umbrales: negativo rechazado", negativo)

    def colores():
        eq(inv.color_stock(100, 50, 20), "verde")
        eq(inv.color_stock(50, 50, 20), "verde")
        eq(inv.color_stock(30, 50, 20), "amarillo")
        eq(inv.color_stock(20, 50, 20), "amarillo")
        eq(inv.color_stock(5, 50, 20), "rojo")
        eq(inv.color_stock(0, 50, 20), "rojo")
    t.test("Umbrales: colores correctos", colores)


# ============================================================
# 14. Dar de baja
# ============================================================
def test_baja(t):
    inv.registrar_entrada("Prod Baja", 25, ADMIN, ALMACEN_ID,
                          codigo="FK0001")
    p = inv.buscar_producto_por_codigo("FK0001", ALMACEN_ID)

    def dar_baja():
        inv.dar_baja(p["id"], ADMIN, motivo="Dañado")
        p2 = inv.buscar_producto_por_codigo("FK0001", ALMACEN_ID)
        eq(p2["activo"], 0)
    t.test("Baja: dar de baja", dar_baja)

    def doble():
        raises(ValueError, lambda: inv.dar_baja(p["id"], ADMIN))
    t.test("Baja: no se puede dar de baja 2 veces", doble)

    def no_aparece_en_activos():
        prods = inv.listar_productos(ALMACEN_ID, solo_activos=True)
        nombres = [x["nombre"] for x in prods]
        assert "Prod Baja" not in nombres
    t.test("Baja: no aparece en lista de activos",
           no_aparece_en_activos)


# ============================================================
# 15. Búsqueda global (autocompletado)
# ============================================================
def test_busqueda_global(t):
    inv.registrar_entrada("Prod Global", 10, ADMIN, ALMACEN_ID,
                          codigo="FL0001")

    def por_codigo():
        p = inv.buscar_producto_global_por_codigo("FL0001")
        assert p is not None
        eq(p["nombre"], "Prod Global")
        assert "local_nombre" in p
    t.test("Búsqueda global: por código", por_codigo)

    def por_nombre():
        p = inv.buscar_producto_global_por_nombre("Prod Global")
        assert p is not None
        eq(p["codigo"], "FL0001")
    t.test("Búsqueda global: por nombre", por_nombre)

    def no_existe():
        eq(inv.buscar_producto_global_por_codigo("ZZ9999"), None)
        eq(inv.buscar_producto_global_por_nombre("NoExiste"), None)
    t.test("Búsqueda global: no existe → None", no_existe)

    def normalizar_codigo():
        p = inv.buscar_producto_global_por_codigo("  fl0001  ")
        assert p is not None
    t.test("Búsqueda global: normaliza código", normalizar_codigo)


# ============================================================
# 16. Totales por concepto (FIX #3)
# ============================================================
def test_totales_por_concepto(t):
    local = loc.abrir_tienda("Test Totales")
    inv.registrar_entrada("P1", 100, ADMIN, local, codigo="FA1001",
                          precio_costo=1, precio_unitario=2)
    inv.registrar_entrada("P2", 50, ADMIN, local, codigo="FA1002",
                          precio_costo=1, precio_unitario=2)
    inv.registrar_salida("P1", 10, ADMIN, local, motivo="Venta")
    inv.registrar_salida("P1", 5, ADMIN, local, motivo="Merma")
    inv.registrar_salida("P2", 3, ADMIN, local, motivo="Venta")

    def check():
        tc = inv.totales_por_concepto(local)
        eq(tc["entradas"]["n"], 2)
        eq(tc["entradas"]["cantidad"], 150.0)
        eq(tc["ventas"]["n"], 2)
        eq(tc["ventas"]["cantidad"], 13.0)
        eq(tc["ventas"]["monto"], 26.0)  # (10+3)*2
        eq(tc["otras_salidas"]["n"], 1)
        eq(tc["otras_salidas"]["cantidad"], 5.0)
        eq(tc["bajas"]["n"], 0)
    t.test("Totales por concepto: conteos correctos (FIX #3)",
           check)

    def general():
        tc = inv.totales_por_concepto(GENERAL_ID)
        ge(tc["ventas"]["n"], 2)
    t.test("Totales por concepto: funciona en General", general)


# ============================================================
# 17. Eliminar movimiento (FIX #5)
# ============================================================
def test_eliminar_movimiento(t):
    local = loc.abrir_tienda("Test Eliminar")
    inv.registrar_entrada("PE", 100, ADMIN, local, codigo="FA2001",
                          precio_costo=1, precio_unitario=2)
    p = inv.buscar_producto_por_codigo("FA2001", local)

    def eliminar_entrada():
        with get_conn() as conn:
            mov = conn.execute(
                "SELECT id FROM movimientos WHERE tipo='ENTRADA' "
                "AND producto_id=? ORDER BY id DESC LIMIT 1",
                (p["id"],)
            ).fetchone()
        inv.eliminar_movimiento(mov["id"], ADMIN)
        p2 = inv.buscar_producto_por_codigo("FA2001", local)
        eq(p2["stock"], 0.0, "stock restaurado a 0")
    t.test("Eliminar mov: entrada revierte stock",
           eliminar_entrada)

    def eliminar_salida():
        inv.registrar_entrada("PE", 100, ADMIN, local,
                              codigo="FA2001")
        p2 = inv.buscar_producto_por_codigo("FA2001", local)
        eq(p2["stock"], 100.0)

        inv.registrar_salida("PE", 30, ADMIN, local, motivo="Venta")
        p3 = inv.buscar_producto_por_codigo("FA2001", local)
        eq(p3["stock"], 70.0)

        with get_conn() as conn:
            mov = conn.execute(
                "SELECT id FROM movimientos WHERE tipo='SALIDA' "
                "AND producto_id=? ORDER BY id DESC LIMIT 1",
                (p3["id"],)
            ).fetchone()
        inv.eliminar_movimiento(mov["id"], ADMIN)
        p4 = inv.buscar_producto_por_codigo("FA2001", local)
        eq(p4["stock"], 100.0,
           "stock restaurado tras eliminar salida")
    t.test("Eliminar mov: salida restaura stock", eliminar_salida)

    def eliminar_baja_falla():
        p5 = inv.buscar_producto_por_codigo("FA2001", local)
        inv.dar_baja(p5["id"], ADMIN)
        with get_conn() as conn:
            mov = conn.execute(
                "SELECT id FROM movimientos WHERE tipo='BAJA' "
                "AND producto_id=? ORDER BY id DESC LIMIT 1",
                (p5["id"],)
            ).fetchone()
        raises(ValueError,
               lambda: inv.eliminar_movimiento(mov["id"], ADMIN))
    t.test("Eliminar mov: BAJA rechazada (por diseño)",
           eliminar_baja_falla)

    def eliminar_traspaso():
        local2 = loc.abrir_tienda("Test Elim Traspaso")
        inv.registrar_entrada("PTE", 100, ADMIN, local,
                              codigo="FA3001")
        inv.registrar_traspaso("PTE", 30, ADMIN, local, local2)

        po = inv.buscar_producto_por_codigo("FA3001", local)
        pd = inv.buscar_producto_por_codigo("FA3001", local2)
        eq(po["stock"], 70.0)
        eq(pd["stock"], 30.0)

        with get_conn() as conn:
            mov = conn.execute(
                "SELECT id FROM movimientos "
                "WHERE tipo='TRASPASO_SALIDA' "
                "AND producto_id=? ORDER BY id DESC LIMIT 1",
                (po["id"],)
            ).fetchone()
        inv.eliminar_movimiento(mov["id"], ADMIN)

        po2 = inv.buscar_producto_por_codigo("FA3001", local)
        pd2 = inv.buscar_producto_por_codigo("FA3001", local2)
        eq(po2["stock"], 100.0, "stock origen restaurado")
        eq(pd2["stock"], 0.0, "stock destino restaurado")
    t.test("Eliminar mov: traspaso elimina ambos",
           eliminar_traspaso)

    def comun_bloqueado():
        raises(PermissionError,
               lambda: inv.eliminar_movimiento(
                   1, {"username": "x", "rol": "comun"}))
    t.test("Eliminar mov: rol común bloqueado",
           comun_bloqueado)

    def inexistente():
        raises(ValueError,
               lambda: inv.eliminar_movimiento(999999, ADMIN))
    t.test("Eliminar mov: id inexistente rechazado", inexistente)


# ============================================================
# 18. Total local y métricas
# ============================================================
def test_totales_local(t):
    local = loc.abrir_tienda("Test Totales Local")
    inv.registrar_entrada("M1", 100, ADMIN, local, codigo="FA4001",
                          precio_costo=5, precio_unitario=10)
    inv.registrar_entrada("M2", 50, ADMIN, local, codigo="FA4002",
                          precio_costo=3, precio_unitario=8)

    def check():
        t = inv.totales_local(local)
        eq(round(t["invertido"], 2), round(100*5 + 50*3, 2))
        eq(round(t["venta_total"], 2), round(100*10 + 50*8, 2))
        eq(round(t["diferencia"], 2),
           round((100*10 + 50*8) - (100*5 + 50*3), 2))
    t.test("Totales local: cálculo correcto", check)


# ============================================================
# 19. Productos por color / stock cero
# ============================================================
def test_productos_filtros(t):
    local = loc.abrir_tienda("Test Filtros")
    # FIX: registrar_entrada exige cantidad > 0. Creamos V4 con 1
    # y luego sacamos todo para dejarlo en 0.
    inv.registrar_entrada("V1", 100, ADMIN, local, codigo="FA5001")
    inv.registrar_entrada("V2", 30, ADMIN, local, codigo="FA5002")
    inv.registrar_entrada("V3", 5, ADMIN, local, codigo="FA5003")
    inv.registrar_entrada("V4", 1, ADMIN, local, codigo="FA5004")

    # Dejar V4 en stock 0 mediante una salida total
    inv.registrar_salida("V4", 1, ADMIN, local, motivo="Merma")

    def verde():
        prods = inv.productos_por_color(local, "verde")
        eq(len(prods), 1)
        eq(prods[0]["nombre"], "V1")
    t.test("Filtros: productos en verde", verde)

    def amarillo():
        prods = inv.productos_por_color(local, "amarillo")
        eq(len(prods), 1)
        eq(prods[0]["nombre"], "V2")
    t.test("Filtros: productos en amarillo", amarillo)

    def rojo():
        prods = inv.productos_por_color(local, "rojo")
        eq(len(prods), 2)  # V3 y V4
    t.test("Filtros: productos en rojo", rojo)

    def stock_cero():
        prods = inv.productos_stock_cero(local)
        eq(len(prods), 1)
        eq(prods[0]["nombre"], "V4")
    t.test("Filtros: productos stock 0", stock_cero)


# ============================================================
# 20. Vista General
# ============================================================
def test_general(t):
    def listar():
        prods = inv.listar_productos(GENERAL_ID, solo_activos=True)
        gt(len(prods), 0, "debe haber productos")
    t.test("General: lista productos agregados", listar)

    def buscar_por_nombre():
        p = inv.buscar_producto_por_nombre("Prod Global", GENERAL_ID)
        assert p is not None
    t.test("General: búsqueda por nombre", buscar_por_nombre)

    def buscar_por_codigo():
        p = inv.buscar_producto_por_codigo("FL0001", GENERAL_ID)
        assert p is not None
    t.test("General: búsqueda por código", buscar_por_codigo)


# ============================================================
# 21. Motivos recientes
# ============================================================
def test_motivos_recientes(t):
    local = loc.abrir_tienda("Test Motivos")
    inv.registrar_entrada("MR", 50, ADMIN, local, codigo="FA6001")
    inv.registrar_salida("MR", 5, ADMIN, local, motivo="Venta")
    inv.registrar_salida("MR", 3, ADMIN, local, motivo="Merma")
    inv.registrar_salida("MR", 2, ADMIN, local, motivo="Combos")

    def listar():
        motivos = inv.motivos_usados_recientes(10)
        assert "Venta" in motivos
        assert "Merma" in motivos
        assert "Combos" in motivos
    t.test("Motivos recientes: incluye los usados", listar)


# ============================================================
# 22. Excel (genera sin errores)
# ============================================================
def test_excel(t):
    def generar():
        import excel_sync as excel
        data = excel.generar_excel_bytes()
        gt(len(data), 1000, "Excel debe pesar > 1 KB")
        assert data[:2] == b"PK", "xlsx es un ZIP (firma PK)"
    t.test("Excel: generar bytes válidos", generar)


# ============================================================
# 23. Backup (interno + exportar a carpeta)
# ============================================================
def test_backup(t):
    from backup import hacer_backup
    from rutas import BACKUPS, DB_PATH

    def interno():
        antes = len(list(BACKUPS.glob("almacen_*.db")))
        destino = hacer_backup()
        assert destino is not None
        assert Path(destino).exists()
        despues = len(list(BACKUPS.glob("almacen_*.db")))
        ge(despues, antes + 1)
    t.test("Backup interno: crea archivo", interno)

    def exportar_a_carpeta():
        destino = TEST_DIR / "mi_export.db"
        shutil.copy2(DB_PATH, destino)
        assert destino.exists()
        gt(destino.stat().st_size, 0)
    t.test("Backup export: copia a ruta elegida",
           exportar_a_carpeta)

    def importar_desde_archivo():
        fuente = TEST_DIR / "mi_export.db"
        respaldo = TEST_DIR / "antes_import.db"
        shutil.copy2(DB_PATH, respaldo)
        shutil.copy2(fuente, DB_PATH)
        inicializar_db()
        with get_conn() as conn:
            row = conn.execute(
                "SELECT COUNT(*) AS n FROM usuarios"
            ).fetchone()
            gt(row["n"], 0)
    t.test("Backup import: reemplaza BD correctamente",
           importar_desde_archivo)


# ============================================================
# 24. Cierre de tienda
# ============================================================
def test_cerrar_tienda(t):
    local = loc.abrir_tienda("Test Cerrar")
    inv.registrar_entrada("CT1", 100, ADMIN, local,
                          codigo="FA7001")
    inv.registrar_entrada("CT2", 50, ADMIN, local,
                          codigo="FA7002")

    def cerrar():
        loc.cerrar_tienda(local, "admin")
        l = loc.obtener_local(local)
        eq(l["activo"], 0)
    t.test("Cerrar tienda: queda inactiva", cerrar)

    def traspaso_a_almacen():
        pa = inv.buscar_producto_por_nombre("CT1", ALMACEN_ID)
        assert pa is not None, "CT1 debe estar en Almacén"
        ge(pa["stock"], 100)
    t.test("Cerrar tienda: productos pasan al Almacén",
           traspaso_a_almacen)

    def no_cerrar_almacen():
        raises(ValueError,
               lambda: loc.cerrar_tienda(ALMACEN_ID, "admin"))
    t.test("Cerrar tienda: no se puede cerrar Almacén",
           no_cerrar_almacen)


# ============================================================
# 25. Preferencias (local actual)
# ============================================================
def test_preferencias(t):
    def local_actual_almacen():
        lid = loc.get_local_actual("nuevo_user")
        eq(lid, ALMACEN_ID)
    t.test("Prefs: local por defecto = Almacén",
           local_actual_almacen)

    def set_y_get():
        loc.set_local_actual("test_user", CENTRO_ID)
        eq(loc.get_local_actual("test_user"), CENTRO_ID)
    t.test("Prefs: set/get local actual", set_y_get)

    def local_inexistente():
        loc.set_local_actual("test_user2", 999999)
        eq(loc.get_local_actual("test_user2"), ALMACEN_ID,
           "si el local ya no existe → Almacén")
    t.test("Prefs: local inexistente → Almacén",
           local_inexistente)


# ============================================================
# MAIN
# ============================================================
def main():
    print()
    print("=" * 66)
    print("  \033[93mFULL TEST — Almacén Raidel (móvil)\033[0m")
    print("  Verifica TODAS las funciones y los fixes aplicados.")
    print("=" * 66)

    setup()

    t = TestRunner()

    print("\n\033[94m[1] Inicialización BD\033[0m")
    test_db_inicializacion(t)

    print("\n\033[94m[2] Seguridad (hash/verificación)\033[0m")
    test_seguridad(t)

    print("\n\033[94m[3] Configuración\033[0m")
    test_config(t)

    print("\n\033[94m[4] Usuarios\033[0m")
    test_usuarios(t)

    print("\n\033[94m[5] Locales\033[0m")
    test_locales(t)

    print("\n\033[94m[6] Códigos Fxyyyy\033[0m")
    test_codigos(t)

    print("\n\033[94m[7] Entradas\033[0m")
    test_entradas(t)

    print("\n\033[94m[8] Salidas\033[0m")
    test_salidas(t)

    print("\n\033[94m[9] Traspasos\033[0m")
    test_traspasos(t)

    print("\n\033[94m[10] Precios (costo/venta + propagación)"
          "\033[0m")
    test_precios(t)

    print("\n\033[94m[11] Edición de código\033[0m")
    test_codigo_edicion(t)

    print("\n\033[94m[12] Renombrar producto\033[0m")
    test_renombrar(t)

    print("\n\033[94m[13] Umbrales\033[0m")
    test_umbrales(t)

    print("\n\033[94m[14] Dar de baja\033[0m")
    test_baja(t)

    print("\n\033[94m[15] Búsqueda global (autocompletado)"
          "\033[0m")
    test_busqueda_global(t)

    print("\n\033[94m[16] Totales por concepto (FIX #3)\033[0m")
    test_totales_por_concepto(t)

    print("\n\033[94m[17] Eliminar movimiento (FIX #5)\033[0m")
    test_eliminar_movimiento(t)

    print("\n\033[94m[18] Totales por local (métricas)\033[0m")
    test_totales_local(t)

    print("\n\033[94m[19] Productos por color\033[0m")
    test_productos_filtros(t)

    print("\n\033[94m[20] Vista General\033[0m")
    test_general(t)

    print("\n\033[94m[21] Motivos recientes\033[0m")
    test_motivos_recientes(t)

    print("\n\033[94m[22] Excel\033[0m")
    test_excel(t)

    print("\n\033[94m[23] Backup (interno + export/import)"
          "\033[0m")
    test_backup(t)

    print("\n\033[94m[24] Cierre de tienda\033[0m")
    test_cerrar_tienda(t)

    print("\n\033[94m[25] Preferencias de local actual\033[0m")
    test_preferencias(t)

    # Limpieza
    print(f"\n\033[94m[CLEANUP] Borrando {TEST_DIR}…\033[0m")
    try:
        shutil.rmtree(TEST_DIR, ignore_errors=True)
        print("  OK")
    except Exception as e:
        print(f"  Aviso: {e}")

    ok = t.resumen()
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()