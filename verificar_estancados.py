"""
Verificación exhaustiva de `productos_estancados`.

Comprueba:
  1. Ningún producto con venta reciente está en estancados.
  2. Todo producto activo con stock > 0 está clasificado
     (o vendido o estancado).
  3. Detecta productos sin clasificar (posible bug).
  4. Muestra los motivos reales de los movimientos de estancados,
     para descartar falsos positivos.
"""
from datetime import datetime, timedelta

import metricas as met
from db import get_conn

LOCAL_ID = 1
DIAS = 30
fecha_limite = (datetime.now() - timedelta(days=DIAS)).strftime(
    "%Y-%m-%d %H:%M:%S")

print("=" * 74)
print(f"VERIFICACIÓN — Local {LOCAL_ID}, últimos {DIAS} días")
print("=" * 74)

# ── 1. Listas ──
estancados = met.productos_estancados(
    LOCAL_ID, dias=DIAS, limite=10_000)
estancados_ids = {p["id"] for p in estancados}
print(f"\n[1] Estancados: {len(estancados)} productos")

with get_conn() as conn:
    vendidos = conn.execute(f"""
        SELECT DISTINCT m.producto_id
        FROM movimientos m
        JOIN productos p ON p.id = m.producto_id
        WHERE p.activo = 1 AND p.local_id = ?
          AND m.tipo = 'SALIDA'
          AND {met.SQL_ES_VENTA}
          AND m.fecha >= ?
          AND {met.SQL_NO_ANULADA}
    """, (LOCAL_ID, fecha_limite)).fetchall()
    vendidos_ids = {r["producto_id"] for r in vendidos}
print(f"[2] Vendidos en {DIAS} días: {len(vendidos_ids)} productos")

# ── 2. Verificar solapamiento ──
print("\n" + "-" * 74)
solap = estancados_ids & vendidos_ids
if solap:
    print(f"❌ ERROR: {len(solap)} productos están en AMBAS listas:")
    for pid in solap:
        with get_conn() as conn:
            p = conn.execute(
                "SELECT nombre, codigo FROM productos WHERE id=?",
                (pid,)).fetchone()
            print(f"   {p['codigo']}  {p['nombre']}")
else:
    print("✅ 0 solapamientos (ningún vendido está en estancados)")

# ── 3. Todo producto activo con stock > 0 debe estar clasificado ──
print("\n" + "-" * 74)
with get_conn() as conn:
    todos = conn.execute("""
        SELECT id, nombre, codigo, stock
        FROM productos
        WHERE activo = 1 AND stock > 0 AND local_id = ?
    """, (LOCAL_ID,)).fetchall()
    todos_ids = {r["id"] for r in todos}
print(f"Productos activos con stock > 0: {len(todos_ids)}")

sin_clasificar = todos_ids - estancados_ids - vendidos_ids
if sin_clasificar:
    print(f"\n❌ {len(sin_clasificar)} productos SIN CLASIFICAR:")
    for pid in sin_clasificar:
        with get_conn() as conn:
            p = conn.execute(
                "SELECT nombre, codigo, stock FROM productos "
                "WHERE id=?", (pid,)).fetchone()
            print(f"   {p['codigo']}  {p['nombre']:30}  "
                  f"stock={p['stock']}")
else:
    print("✅ Todos los productos activos con stock están clasificados "
          "(vendidos o estancados)")

# ── 4. Auditoría de motivos en los movimientos de estancados ──
# Para cada estancado, mostrar los motivos de sus movimientos
# recientes. NINGUNO debería ser 'Venta' ni 'Combos'.
print("\n" + "-" * 74)
print("Auditoría: motivos de los movimientos recientes de los estancados")
print("-" * 74)

sospechosos = []
for p in estancados[:30]:  # Muestra hasta 30 para no saturar
    with get_conn() as conn:
        movs = conn.execute("""
            SELECT DISTINCT motivo
            FROM movimientos
            WHERE producto_id = ?
              AND tipo = 'SALIDA'
              AND fecha >= ?
        """, (p["id"], fecha_limite)).fetchall()
    motivos = [m["motivo"] for m in movs if m["motivo"]]
    # ¿Alguno de esos motivos es una venta?
    for m in motivos:
        if m.lower().strip() in ("venta", "combos"):
            sospechosos.append((p, m))
            break

if sospechosos:
    print(f"\n❌ {len(sospechosos)} productos tienen motivos de "
          f"venta pero aparecen como estancados:")
    for p, m in sospechosos:
        print(f"   {p['codigo']}  {p['nombre']}  motivo={m!r}")
else:
    print("✅ Ningún estancado tiene movimientos con motivo "
          "'Venta' o 'Combos'")

# ── 5. Resumen ──
print("\n" + "=" * 74)
if not solap and not sin_clasificar and not sospechosos:
    print("✅ VERIFICACIÓN OK — sin bugs detectados")
else:
    print("❌ VERIFICACIÓN FALLIDA — revisar arriba")
print("=" * 74)