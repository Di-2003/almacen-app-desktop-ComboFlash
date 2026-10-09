"""Muestra exactamente con qué BD está trabajando la app."""
import sqlite3
from rutas import DB_PATH, RAIZ, DATOS
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

print("=" * 60)
print(f"RAIZ    : {RAIZ}")
print(f"DATOS   : {DATOS}")
print(f"DB_PATH : {DB_PATH}")
print(f"Existe  : {DB_PATH.exists()}")

if not DB_PATH.exists():
    print("\n❌ No hay BD. Copia tu almacen.db real a DATOS/")
    raise SystemExit(1)

tam = DB_PATH.stat().st_size
print(f"Tamaño  : {tam:,} bytes")

conn = sqlite3.connect(DB_PATH)
conn.row_factory = sqlite3.Row
try:
    print("\n--- Tablas ---")
    tablas = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    print(", ".join(t["name"] for t in tablas))

    print("\n--- Columnas de 'productos' ---")
    cols = conn.execute("PRAGMA table_info(productos)").fetchall()
    print(", ".join(c["name"] for c in cols))
    tiene_local = any(c["name"] == "local_id" for c in cols)
    print(f"\n¿Tiene 'local_id'? {tiene_local}  "
          f"-> {'P2 (v7+)' if tiene_local else 'P1 (v4) - MIGRABLE'}")

    print("\n--- Datos ---")
    try:
        n_prod = conn.execute("SELECT COUNT(*) FROM productos").fetchone()[0]
        print(f"Productos: {n_prod}")
    except Exception as e:
        print(f"Productos: (error {e})")
    try:
        n_movs = conn.execute("SELECT COUNT(*) FROM movimientos").fetchone()[0]
        print(f"Movimientos: {n_movs}")
    except Exception as e:
        print(f"Movimientos: (error {e})")
    try:
        n_usr = conn.execute("SELECT COUNT(*) FROM usuarios").fetchone()[0]
        print(f"Usuarios: {n_usr}")
    except Exception as e:
        print(f"Usuarios: (error {e})")

    print("\n--- Versión ---")
    try:
        row = conn.execute(
            "SELECT valor FROM meta WHERE clave='version_esquema'"
        ).fetchone()
        print(f"version_esquema = {row['valor'] if row else '(sin marcar)'}")
    except Exception as e:
        print(f"(error {e})")
finally:
    conn.close()

print("=" * 60)