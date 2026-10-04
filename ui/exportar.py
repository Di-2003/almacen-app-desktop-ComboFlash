"""
Exportación e importación de datos.

- Excel completo (hojas fijas + una por local).
- Copia de seguridad de la BD (.db).
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


# ============================================================
# Exportar Excel
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
        return

    if ruta:
        snack(page, f"Excel guardado ({len(data):,} bytes)", "ok")
    else:
        snack(page, "Guardado cancelado", "info")


# ============================================================
# Exportar copia de seguridad (BD)
# ============================================================

async def exportar_backup(app):
    page = app.page
    if not DB_PATH.exists():
        snack(page, "No hay BD que exportar", "error")
        return

    with open(DB_PATH, "rb") as f:
        data = f.read()

    nombre = (f"almacen_backup_"
              f"{datetime.now().strftime('%Y-%m-%d')}.db")

    fp = ft.FilePicker()
    page.services.append(fp)
    page.update()

    try:
        ruta = await fp.save_file(
            file_name=nombre,
            allowed_extensions=["db"],
            src_bytes=data,
        )
    except Exception as ex:
        snack(page, f"Error al guardar: {ex}", "error")
        return

    if ruta:
        snack(page, f"Copia guardada ({len(data):,} bytes)", "ok")
    else:
        snack(page, "Guardado cancelado", "info")


# ============================================================
# Importar copia de seguridad
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
        )
    except Exception as ex:
        snack(page, f"Error al abrir archivo: {ex}", "error")
        return

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

    def confirmar(e):
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM usuarios WHERE id=?",
                (app.usuario["id"],),
            ).fetchone()
        if row is None or not verificar_password(
                tf.value or "", row["salt"], row["password_hash"]):
            snack(page, "Contraseña incorrecta", "error")
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
        ], tight=True, width=340, spacing=8,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton(
                "Importar",
                on_click=confirmar,
                style=ft.ButtonStyle(
                    bgcolor="#dc2626", color="white")),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))


def _hacer_import(app, data):
    page = app.page
    try:
        # 1. Guardar la BD actual
        if DB_PATH.exists():
            sello = datetime.now().strftime("%Y-%m-%d_%H%M%S")
            destino = (BACKUPS /
                    f"almacen_antes_de_importar_{sello}.db")
            shutil.copy2(DB_PATH, destino)

        # 2. Sobrescribir
        with open(DB_PATH, "wb") as f:
            f.write(data)

        # 3. Asegurar esquema actualizado
        inicializar_db()
    except Exception as ex:
        snack(page, f"Error al importar: {ex}", "error")
        return

    snack(page,
          "Copia importada. Se cerrará la sesión.",
          "ok")
    app.cerrar_sesion()


# ============================================================
# Forzar backup ahora (copia interna, no exporta)
# ============================================================

def backup_ahora(app):
    page = app.page
    from backup import hacer_backup
    try:
        destino = hacer_backup()
    except Exception as ex:
        snack(page, f"Error al hacer backup: {ex}", "error")
        return
    if destino:
        snack(page, "Backup interno creado", "ok")
    else:
        snack(page, "Aún no hay BD que respaldar", "info")