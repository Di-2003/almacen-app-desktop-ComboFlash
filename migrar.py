"""Migración standalone P1(v4) -> P2(v10). Hace backup antes."""
import sys
import io
import shutil
import traceback
from pathlib import Path
from datetime import datetime

# UTF-8 en Windows para que no pete con tildes/flechas
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
sys.path.insert(0, str(Path(__file__).resolve().parent))

from rutas import DB_PATH, BACKUPS


def backup():
    if not DB_PATH.exists():
        print(f"[abort] No existe {DB_PATH}")
        sys.exit(1)
    sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
    destino = BACKUPS / f"almacen_ANTES_MIGRACION_{sello}.db"
    shutil.copy2(DB_PATH, destino)
    print(f"[backup] {destino}")


def main():
    print("=" * 60)
    print(f"Migración P1 -> P2")
    print(f"BD: {DB_PATH}")
    print("=" * 60)

    backup()

    print("\n[1/2] Importando db.py...")
    from db import inicializar_db, VERSION_ESQUEMA
    print(f"      VERSION_ESQUEMA = {VERSION_ESQUEMA}")

    print("\n[2/2] Llamando inicializar_db()...")
    try:
        inicializar_db()
    except Exception:
        print("\nERROR EN MIGRACION:")
        traceback.print_exc()
        sys.exit(2)

    print("\nMigración OK.")

    # Verificar
    import sqlite3
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        ver = conn.execute(
            "SELECT valor FROM meta WHERE clave='version_esquema'"
        ).fetchone()
        print(f"version_esquema = {ver['valor']}")
        cols = conn.execute("PRAGMA table_info(productos)").fetchall()
        tiene = any(c["name"] == "local_id" for c in cols)
        print(f"local_id existe = {tiene}")
        print(f"Productos    = {conn.execute('SELECT COUNT(*) FROM productos').fetchone()[0]}")
        print(f"Movimientos  = {conn.execute('SELECT COUNT(*) FROM movimientos').fetchone()[0]}")
        print(f"Locales      = {conn.execute('SELECT COUNT(*) FROM locales').fetchone()[0]}")
        print(f"Categorías   = {conn.execute('SELECT COUNT(*) FROM categorias').fetchone()[0]}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()