"""
Exportación e importación de datos.

- Excel completo (hojas fijas + una por local).
- Excel de SALIDAS DEL DÍA (todas, sin filtrar motivo).
- Importar copia de seguridad (con confirmación por contraseña).
- Backup Destino / Interno (SAF Android; en desktop usa FilePicker).
"""
import shutil
from datetime import datetime
from pathlib import Path

import flet as ft

from rutas import DB_PATH, BACKUPS
from db import get_conn, inicializar_db
from seguridad import verificar_password
from ui import estilos as es
from ui.componentes import snack
import excel_sync as excel
import inventario as inv


BACKUP_CARPETA_KEY = "backup_carpeta"


# ============================================================
# Helpers
# ============================================================

def _cerrar_picker(page, fp):
    try:
        page.services.remove(fp)
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass


def _nombre_backup() -> str:
    return (f"almacen_backup_"
            f"{datetime.now().strftime('%Y-%m-%d_%H%M%S')}.db")


def get_carpeta_destino() -> str | None:
    try:
        return inv.get_config(BACKUP_CARPETA_KEY)
    except Exception:
        return None


# ============================================================
# 1. Exportar Excel completo
# ============================================================

async def exportar_excel(app):
    page = app.page
    try:
        data = excel.generar_excel_bytes()
    except Exception as ex:
        snack(page, f"Error al generar Excel: {ex}", "error")
        return

    nombre = f"inventario_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    fp = ft.FilePicker()
    page.services.append(fp)
    page.update()

    try:
        ruta = await fp.save_file(
            file_name=nombre,
            allowed_extensions=["xlsx"],
            src_bytes=data,
        )
    except Exception as ex:
        snack(page, f"Error al guardar: {ex}", "error")
        _cerrar_picker(page, fp)
        return
    _cerrar_picker(page, fp)

    if ruta:
        snack(page, f"Excel guardado ({len(data):,} bytes)", "ok")
    else:
        snack(page, "Guardado cancelado", "info")


# ============================================================
# 1.b. Exportar SOLO salidas del día (sin filtrar motivo)
# ============================================================

async def exportar_salidas_hoy(app):
    """
    Exporta TODAS las salidas del día actual (cualquier motivo)
    para cuadre diario.
    """
    page = app.page

    try:
        local = (None if app.es_general() else app.local_id)
        data = excel.generar_excel_salidas_hoy(local_id=local)
    except ValueError:
        snack(page, "No hay salidas registradas hoy", "info")
        return
    except Exception as ex:
        snack(page, f"Error al generar: {ex}", "error")
        return

    nombre = f"salidas_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    fp = ft.FilePicker()
    page.services.append(fp)
    page.update()

    try:
        ruta = await fp.save_file(
            file_name=nombre,
            allowed_extensions=["xlsx"],
            src_bytes=data,
        )
    except Exception as ex:
        snack(page, f"Error al guardar: {ex}", "error")
        _cerrar_picker(page, fp)
        return
    _cerrar_picker(page, fp)

    if ruta:
        snack(page, f"Salidas guardadas ({len(data):,} bytes)", "ok")
    else:
        snack(page, "Guardado cancelado", "info")


# ============================================================
# 2. Importar copia de seguridad
# ============================================================

async def importar_backup(app):
    page = app.page

    fp = ft.FilePicker()
    page.services.append(fp)
    page.update()

    try:
        files = await fp.pick_files(
            allow_multiple=False,
            allowed_extensions=["db"],
            dialog_title="Elige la copia de seguridad",
        )
    except Exception as ex:
        snack(page, f"Error al abrir archivo: {ex}", "error")
        _cerrar_picker(page, fp)
        return
    _cerrar_picker(page, fp)

    if not files:
        return

    ruta = files[0].path
    if not ruta or not Path(ruta).exists():
        snack(page, "No se pudo leer el archivo", "error")
        return

    with open(ruta, "rb") as f:
        data = f.read()

    _confirmar_import(app, data)


def _confirmar_import(app, data):
    page = app.page

    tf = ft.TextField(
        label="Tu contraseña",
        password=True,
        can_reveal_password=True,
        **es.estilo_textfield(12),
        height=54,
    )
    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def confirmar(e):
        error_lbl.value = ""
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM usuarios WHERE id=?",
                (app.usuario["id"],),
            ).fetchone()
        if row is None or not verificar_password(
                tf.value or "", row["salt"], row["password_hash"]):
            error_lbl.value = "Contraseña incorrecta"
            page.update()
            return
        page.pop_dialog()
        _hacer_import(app, data)

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Confirmar importación"),
        content=ft.Column([
            ft.Text(
                "Se reemplazará la base de datos actual con el "
                "archivo seleccionado.\n\n"
                "Antes de hacerlo, la BD actual se guardará como "
                "respaldo en la carpeta backups/.\n\n"
                "Escribe tu contraseña para confirmar:",
                size=13),
            ft.Container(height=8),
            tf,
            error_lbl,
        ], tight=True, width=340, spacing=8,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Importar",
                on_click=confirmar,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _hacer_import(app, data):
    """
    Importa una BD .db reemplazando la actual.

    Escribe primero a un archivo temporal y luego usa os.replace()
    para el reemplazo atómico. Esto evita [Errno 22] cuando SQLite
    tiene el archivo original abierto.
    """
    page = app.page
    try:
        from rutas import DB_PATH, BACKUPS
        import gc
        import os

        # ── 1. Forzar recolección (cierra conexiones huérfanas) ──
        gc.collect()

        # ── 2. Backup del actual ──
        if DB_PATH.exists():
            sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            destino = BACKUPS / f"almacen_antes_de_importar_{sello}.db"
            try:
                BACKUPS.mkdir(parents=True, exist_ok=True)
                shutil.copy2(DB_PATH, destino)
            except Exception as e:
                print(f"[import] backup falló: {e}")

        # ── 3. Borrar WAL/SHM huérfanos (SQLite en modo WAL) ──
        for sufijo in ("-wal", "-shm"):
            p = Path(str(DB_PATH) + sufijo)
            try:
                if p.exists():
                    p.unlink()
            except Exception as e:
                print(f"[import] no pude borrar {p}: {e}")

        # ── 4. Escribir la nueva BD a un archivo TEMPORAL ──
        # Nunca sobrescribimos el original directamente; así si
        # algo falla, la BD actual sigue intacta.
        tmp_path = DB_PATH.with_name(DB_PATH.name + ".importing")
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except Exception:
            pass

        with open(tmp_path, "wb") as f:
            f.write(data)

        # ── 5. Reemplazo ATÓMICO ──
        # os.replace usa MoveFileEx en Windows: funciona incluso si
        # el destino existe, siempre que no esté bloqueado en exclusiva.
        os.replace(str(tmp_path), str(DB_PATH))

        # ── 6. Reinicializar (por si el esquema necesita ajustes) ──
        inicializar_db()

    except Exception as ex:
        import traceback
        traceback.print_exc()
        snack(page, f"Error al importar: {ex}", "error")
        return

    snack(page, "Copia importada. Se cerrará la sesión.", "ok")
    app.cerrar_sesion()

# ============================================================
# 3. Backup Destino (elegir carpeta, se guarda)
# ============================================================

async def backup_destino(app):
    """
    Abre el selector nativo de carpetas (SAF).
    El usuario elige dónde se guardarán los backups.
    """
    page = app.page

    fp = ft.FilePicker()
    page.services.append(fp)
    page.update()

    try:
        carpeta = await fp.get_directory_path(
            dialog_title="Elige la carpeta destino para backups",
        )
    except Exception as ex:
        snack(page, f"Error: {ex}", "error")
        _cerrar_picker(page, fp)
        return
    _cerrar_picker(page, fp)

    if not carpeta:
        snack(page, "Selección cancelada", "info")
        return

    inv.set_config(BACKUP_CARPETA_KEY, carpeta)
    snack(page, "Carpeta destino guardada", "ok")


# ============================================================
# 4. Backup Interno (guardar el .db en la carpeta destino)
# ============================================================

async def backup_interno(app):
    """
    Guarda el .db en la carpeta destino configurada.
    """
    page = app.page

    if not DB_PATH.exists():
        snack(page, "No hay BD que respaldar", "error")
        return

    carpeta = get_carpeta_destino()
    if not carpeta:
        snack(page,
              "Primero configura la carpeta en «Backup Destino»",
              "warn")
        return

    with open(DB_PATH, "rb") as f:
        data = f.read()

    fp = ft.FilePicker()
    page.services.append(fp)
    page.update()

    try:
        ruta = await fp.save_file(
            file_name=_nombre_backup(),
            allowed_extensions=["db"],
            src_bytes=data,
        )
    except Exception as ex:
        snack(page, f"Error al guardar: {ex}", "error")
        _cerrar_picker(page, fp)
        return
    _cerrar_picker(page, fp)

    if ruta:
        snack(page, f"Backup guardado ({len(data):,} bytes)", "ok")
    else:
        snack(page, "Guardado cancelado", "info")


# ============================================================
# Aliases retro-compatibles
# ============================================================

async def exportar_backup(app):
    await backup_interno(app)


async def elegir_carpeta_backup(app):
    await backup_destino(app)


def backup_ahora(app):
    """Copia interna a la carpeta privada backups/ (sin diálogo)."""
    page = app.page
    from backup import hacer_backup
    try:
        destino = hacer_backup()
    except Exception as ex:
        snack(page, f"Error al hacer backup: {ex}", "error")
        return
    if destino:
        snack(page, "Backup interno creado en backups/", "ok")
    else:
        snack(page, "Aún no hay BD que respaldar", "info")
        
# ============================================================
# Excel DIARIO (una hoja por local)
# ============================================================

async def exportar_excel_diario(app):
    """
    Excel con todos los locales del día actual:
      - Hoja "Resumen" con totales por local.
      - Una hoja por cada local activo con sus movimientos.
    """
    page = app.page

    try:
        data = excel.generar_excel_diario()
    except Exception as ex:
        snack(page, f"Error al generar: {ex}", "error")
        return

    nombre = f"diario_{datetime.now().strftime('%Y-%m-%d')}.xlsx"

    fp = ft.FilePicker()
    page.services.append(fp)
    page.update()

    try:
        ruta = await fp.save_file(
            file_name=nombre,
            allowed_extensions=["xlsx"],
            src_bytes=data,
        )
    except Exception as ex:
        snack(page, f"Error al guardar: {ex}", "error")
        _cerrar_picker(page, fp)
        return
    _cerrar_picker(page, fp)

    if ruta:
        snack(page, f"Excel diario guardado ({len(data):,} bytes)", "ok")
    else:
        snack(page, "Guardado cancelado", "info")
        

