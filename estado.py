"""Muestra el estado exacto de la BD."""
import sqlite3
from rutas import DB_PATH

c = sqlite3.connect(DB_PATH)
c.row_factory = sqlite3.Row

print("=" * 55)
print(f"BD: {DB_PATH}")
print(f"Tamaño: {DB_PATH.stat().st_size:,} bytes")
print("=" * 55)

print("\n--- Todas las tablas ---")
for r in c.execute(
    "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
).fetchall():
    print(f"  {r['name']}")

# Contar en cada tabla relevante (si existe)
print("\n--- Conteos ---")
for t in ("productos", "movimientos", "usuarios", "locales",
          "categorias", "_productos_v4", "_movimientos_v4"):
    try:
        n = c.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        print(f"  {t:20s} = {n}")
    except Exception as e:
        print(f"  {t:20s} = (no existe)")

# Columnas de productos
print("\n--- Columnas de 'productos' ---")
try:
    for r in c.execute("PRAGMA table_info(productos)").fetchall():
        print(f"  {r['name']}")
except Exception as e:
    print(f"  error: {e}")

# Versión
print("\n--- Versión ---")
try:
    r = c.execute(
        "SELECT valor FROM meta WHERE clave='version_esquema'"
    ).fetchone()
    print(f"  version_esquema = {r['valor'] if r else '??'}")
except Exception as e:
    print(f"  error: {e}")

c.close()
print("=" * 55)