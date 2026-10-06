"""
Exportación e importación de datos.

Flujo:
  1. "Backup Destino": el usuario elige UNA carpeta donde se
     guardarán los backups. Se guarda como preferencia.
  2. "Backup Interno": guarda el .db en esa carpeta (con nombre
     automático). Como Android 11+ usa SAF, se abre el diálogo
     de guardado ya con el nombre relleno.

- Excel completo (hojas fijas + una por local).
- Importar copia de seguridad (con confirmación por contraseña).
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
    """Quita el FilePicker de los servicios y refresca."""
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
    """Devuelve la carpeta configurada, o None."""
    try:
        return inv.get_config(BACKUP_CARPETA_KEY)
    except Exception:
        return None


# ============================================================
# 1. Exportar Excel
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
    page = app.page
    try:
        if DB_PATH.exists():
            sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            destino = (BACKUPS /
                       f"almacen_antes_de_importar_{sello}.db")
            shutil.copy2(DB_PATH, destino)

        with open(DB_PATH, "wb") as f:
            f.write(data)

        inicializar_db()
    except Exception as ex:
        snack(page, f"Error al importar: {ex}", "error")
        return

    snack(page,
          "Copia importada. Se cerrará la sesión.",
          "ok")
    app.cerrar_sesion()


# ============================================================
# 3. Backup Destino (elegir carpeta, se guarda)
# ============================================================

async def backup_destino(app):
    """
    Abre el selector nativo de carpetas (SAF). El usuario elige
    la carpeta donde se guardarán los backups. Se guarda como
    preferencia para que "Backup Interno" la use después.
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
    Como Android 11+ no permite escribir silenciosamente en una
    carpeta SAF (necesita confirmación del usuario), se abre el
    diálogo de guardado con el nombre ya relleno.
    El usuario solo tiene que tocar "Guardar".
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