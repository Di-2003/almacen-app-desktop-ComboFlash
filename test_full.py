"""
Carga masiva de datos de prueba: 6 meses de movimientos realistas.

Genera:
  - 5 locales: Almacén + Centro + Vedado + Playa + Miramar
  - 25 productos variados (bebidas, alimentos, limpieza, snacks)
  - Hoy (2026-10-04) → 2027-03-31
  - Ventas diarias por tienda, traspasos semanales, mermas,
    rebajas, reposiciones.
  - Playa se cierra a los 90 días.

Uso:
    python test_full.py
"""
import random
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from rutas import DB_PATH, BACKUPS

random.seed(20261004)

# --- Respaldo BD previa y arranque limpio ---
if DB_PATH.exists():
    sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    respaldo = BACKUPS / f"almacen.test_datos_previo_{sello}.db"
    shutil.copy2(DB_PATH, respaldo)
    print(f"  BD previa respaldada en: {respaldo.name}")
    DB_PATH.unlink()

for f in BACKUPS.glob("almacen_*.db"):
    try:
        f.unlink()
    except Exception:
        pass

from db import inicializar_db, get_conn
import inventario as inv
import locales as loc
from seguridad import crear_hash


# ============================================================
# Helpers
# ============================================================

def crear_admin():
    h, s = crear_hash("admin1234")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO usuarios(username,password_hash,salt,rol,"
            "creado) VALUES(?,?,?,'admin',?)",
            ("admin", h, s,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )


def hora_aleatoria(dia: datetime) -> str:
    """Devuelve una fecha YYYY-MM-DD HH:MM:SS aleatoria dentro del día
    (entre 9:00 y 19:59)."""
    hora = random.randint(9, 19)
    minuto = random.randint(0, 59)
    segundo = random.randint(0, 59)
    return dia.strftime(
        f"%Y-%m-%d {hora:02d}:{minuto:02d}:{segundo:02d}"
    )


# ============================================================
# MAIN
# ============================================================

def main():
    print()
    print("=" * 66)
    print("  CARGA MASIVA DE DATOS DE PRUEBA")
    print("=" * 66)
    print()

    inicializar_db()
    crear_admin()
    admin = {"username": "admin", "rol": "admin"}

    # ---- Locales ----
    print("  Creando locales…")
    almacen = loc.obtener_almacen()
    centro = loc.abrir_tienda("Centro")
    vedado = loc.abrir_tienda("Vedado")
    playa = loc.abrir_tienda("Playa")
    miramar = loc.abrir_tienda("Miramar")
    print(f"    Almacén id={almacen['id']}  "
          f"Centro={centro}  Vedado={vedado}")
    print(f"    Playa={playa}  Miramar={miramar}")

    tiendas = [
        (centro, "Centro"),
        (vedado, "Vedado"),
        (playa, "Playa"),
        (miramar, "Miramar"),
    ]

    # ---- Catálogo ----
    print("\n  Cargando catálogo…")
    # (nombre, codigo, pc, pu, uv, ua, stock_inicial)
    catalogo = [
        # Bebidas
        ("Café La Llave",     "CAF001", 3.00, 5.50, 200, 60,  800),
        ("Refresco Cola",     "REF001", 0.80, 1.50, 300, 100, 1200),
        ("Agua Mineral",      "AGU001", 0.40, 1.00, 500, 150, 2000),
        ("Jugo Naranja",      "JUG001", 1.20, 2.40, 150, 50,  600),
        ("Cerveza Nacional",  "CER001", 1.50, 3.00, 100, 30,  400),
        # Alimentos
        ("Arroz Grano",       "ARR001", 1.20, 2.20, 300, 100, 1000),
        ("Frijol Negro",      "FRI001", 1.50, 2.80, 200, 60,  700),
        ("Pasta Larga",       "PAS001", 0.90, 1.80, 250, 80,  900),
        ("Aceite Girasol",    "ACE001", 2.20, 4.00, 150, 50,  500),
        ("Azúcar Refino",     "AZU001", 0.80, 1.50, 400, 120, 1500),
        ("Leche Entera",      "LEC001", 1.80, 3.00, 200, 60,  800),
        ("Atún Agua",         "ATU001", 1.60, 2.90, 150, 50,  500),
        ("Pan Molde",         "PAN001", 1.00, 2.00, 100, 30,  300),
        ("Huevos Docena",     "HUE001", 2.50, 4.50, 80,  25,  400),
        # Limpieza
        ("Jabón Baño",        "JAB001", 0.50, 1.10, 400, 150, 2000),
        ("Detergente",        "DET001", 2.00, 3.80, 150, 50,  600),
        ("Cloro 1L",          "CLO001", 1.20, 2.20, 200, 60,  800),
        ("Papel Higiénico",   "PHI001", 0.90, 1.80, 300, 100, 1200),
        # Snacks
        ("Chocolate Barra",   "CHO001", 0.70, 1.40, 500, 150, 2000),
        ("Galleta María",     "GAL001", 0.60, 1.20, 400, 120, 1500),
        ("Papas Fritas",      "PAP001", 0.90, 1.90, 250, 80,  900),
        ("Maní Salado",       "MAN001", 0.50, 1.10, 300, 100, 1200),
        # Extras
        ("Vino Tinto",        "VIN001", 5.00, 9.50, 60,  20,  200),
        ("Ron Añejo",         "RON001", 8.00, 15.00, 40, 15,  150),
        ("Cigarrillos",       "CIG001", 2.50, 4.50, 100, 30,  500),
    ]

    for nombre, codigo, pc, pu, uv, ua, cant in catalogo:
        inv.registrar_entrada(
            nombre, cant, admin, almacen["id"],
            codigo=codigo, precio_costo=pc, precio_unitario=pu,
        )
        p = inv.buscar_producto_por_codigo(codigo, almacen["id"])
        inv.cambiar_umbrales(p["id"], uv, ua, admin)

    print(f"    {len(catalogo)} productos cargados")

    # ---- Rango de fechas ----
    hoy = datetime.now().replace(hour=0, minute=0, second=0,
                                  microsecond=0)
    fin = datetime(2027, 3, 31)
    dias_total = (fin - hoy).days + 1
    print(f"\n  Rango: {hoy.date()} → {fin.date()} ({dias_total} días)")

    fecha_cierre_playa = hoy + timedelta(days=90)

    # Productos que cada tienda recibe (por índice en catalogo)
    semilla_tiendas = {
        centro:  [0, 1, 2, 5, 6, 7, 8, 9, 14, 15, 16, 18, 19],
        vedado:  [0, 3, 4, 5, 9, 10, 11, 14, 17, 18, 20, 22],
        playa:   [1, 2, 5, 7, 9, 11, 14, 18, 21, 23],
        miramar: [0, 4, 5, 6, 9, 10, 14, 18, 24],
    }

    movs_generados = 0
    tiendas_act = list(tiendas)

    # ---- Bucle diario ----
    for dia_offset in range(dias_total):
        fecha = hoy + timedelta(days=dia_offset)

        # Cierre de Playa
        if (fecha >= fecha_cierre_playa
                and any(t[0] == playa for t in tiendas_act)):
            loc.cerrar_tienda(playa, "admin")
            tiendas_act = [(t, n) for t, n in tiendas_act
                           if t != playa]
            print(f"    ⚠ Playa cerrada el {fecha.date()}")

        # Traspasos semanales (lunes)
        if fecha.weekday() == 0:
            for tienda_id, _ in tiendas_act:
                idxs = semilla_tiendas.get(tienda_id, [])
                for idx in idxs:
                    if random.random() < 0.7:
                        _, codigo, _, _, _, _, _ = catalogo[idx]
                        cant = random.randint(20, 50)
                        try:
                            inv.registrar_traspaso(
                                codigo, cant, admin,
                                local_origen_id=almacen["id"],
                                local_destino_id=tienda_id,
                                fecha=fecha.strftime(
                                    "%Y-%m-%d 08:00:00"),
                            )
                            movs_generados += 1
                        except Exception:
                            pass

        # Ventas diarias por tienda
        for tienda_id, _ in tiendas_act:
            n_ventas = random.randint(3, 8)
            idxs = semilla_tiendas.get(tienda_id, [])
            if not idxs:
                continue
            for _ in range(n_ventas):
                idx = random.choice(idxs)
                _, codigo, _, pu, _, _, _ = catalogo[idx]

                p = inv.buscar_producto_por_codigo(codigo, tienda_id)
                if p is None or p["stock"] < 1:
                    continue

                cant = random.randint(1, min(5, int(p["stock"])))
                r = random.random()
                if r < 0.92:
                    motivo = "Venta"
                elif r < 0.97:
                    motivo = "Merma"
                else:
                    motivo = "Otro"

                rebaja = 0.0
                if motivo == "Venta" and random.random() < 0.30:
                    rebaja = round(random.choice(
                        [0.05, 0.10, 0.15, 0.20, 0.25, 0.30]), 2)
                    if rebaja > pu:
                        rebaja = 0.0

                try:
                    inv.registrar_salida(
                        codigo, cant, admin, tienda_id,
                        motivo=motivo, rebaja=rebaja,
                        fecha=hora_aleatoria(fecha),
                    )
                    movs_generados += 1
                except Exception:
                    pass

        # Reposición al Almacén (jueves al azar, 30% prob)
        # FIX: pasar el NOMBRE (no el código), porque registrar_entrada
        # busca por nombre y creaba productos fantasma.
        if fecha.weekday() == 3 and random.random() < 0.3:
            idx = random.randint(0, len(catalogo) - 1)
            nombre, _, _, _, _, _, _ = catalogo[idx]
            cant = random.randint(100, 400)
            try:
                inv.registrar_entrada(
                    nombre, cant, admin, almacen["id"],
                    fecha=fecha.strftime("%Y-%m-%d 20:00:00"),
                )
                movs_generados += 1
            except Exception:
                pass

        # Progreso cada 30 días
        if dia_offset % 30 == 0:
            print(f"    Día {dia_offset + 1:>3}/{dias_total}  "
                  f"({fecha.date()})  movs: {movs_generados}")

    print(f"\n  ✅ Movimientos generados en loop: {movs_generados}")

    # ---- Excel ----
    print("\n  Generando Excel…")
    import excel_sync as excel
    data = excel.generar_excel_bytes()
    salida = Path("test_excel_salida.xlsx")
    salida.write_bytes(data)
    print(f"    → {salida.resolve()}")
    print(f"      Tamaño: {len(data):,} bytes")

    # ---- Resumen ----
    print()
    print("=" * 66)
    print("  RESUMEN FINAL")
    print("=" * 66)
    with get_conn() as conn:
        n_movs = conn.execute(
            "SELECT COUNT(*) AS n FROM movimientos"
        ).fetchone()["n"]
        n_ventas = conn.execute(
            "SELECT COUNT(*) AS n FROM movimientos "
            "WHERE tipo='SALIDA' AND LOWER(TRIM(motivo))='venta'"
        ).fetchone()["n"]
        total_venta = conn.execute(
            "SELECT SUM((precio_unitario_momento - rebaja) * cantidad) "
            "AS t FROM movimientos "
            "WHERE tipo='SALIDA' AND LOWER(TRIM(motivo))='venta'"
        ).fetchone()["t"] or 0
    print(f"  Total movimientos en BD:  {n_movs}")
    print(f"  Ventas (SALIDA='Venta'):  {n_ventas}")
    print(f"  Monto total:              ${total_venta:,.2f}")

    for l in loc.listar_locales(solo_activos=False):
        estado = "activo" if l["activo"] else "CERRADO"
        n = len(inv.listar_productos(l["id"], solo_activos=True))
        print(f"  {l['nombre']:<12} [{estado:>7}]  {n} productos")

    print()
    print("  Login: admin / admin1234")
    print()


if __name__ == "__main__":
    try:
        main()
    except Exception as ex:
        import traceback
        print(f"\n  💥 ERROR: {type(ex).__name__}: {ex}")
        traceback.print_exc()