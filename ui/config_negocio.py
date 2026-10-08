"""
Datos del negocio + métodos de pago.
"""
import flet as ft
import configuracion_negocio as cfg
from ui import estilos as es
from ui.componentes import snack, mounted
from pathlib import Path


def vista_config_negocio(app):
    page = app.page
    campos_ui = {}

    def refrescar():
        for k, (label, default) in cfg.CAMPOS_NEGOCIO_DICT.items():
            valor = cfg.get_config_negocio(k, default)
            if k in campos_ui:
                campos_ui[k].value = valor
        for tf in campos_ui.values():
            try:
                tf.update()
            except Exception:
                pass

    for k, label, default in cfg.CAMPOS_NEGOCIO:
        campos_ui[k] = ft.TextField(
            label=label,
            value=cfg.get_config_negocio(k, default),
            **es.estilo_textfield(12), height=54,
        )

    def guardar_negocio(e):
        for k, tf in campos_ui.items():
            cfg.set_config_negocio(k, tf.value or "")
        snack(page, "Datos guardados", "ok")
        app.refrescar()

    metodos_col = ft.Column(spacing=8)

    def rebuild_metodos():
        metodos_col.controls.clear()
        for m in cfg.listar_metodos_pago(solo_activos=False):
            metodos_col.controls.append(_fila_metodo(app, m,
                                                     rebuild_metodos))

    rebuild_metodos()

    contenido = ft.Column([
        ft.Text("Datos del negocio", size=14,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Container(height=4),
        *campos_ui.values(),
        ft.Container(height=6),
        ft.FilledButton("Guardar datos", icon=ft.Icons.SAVE,
                        on_click=guardar_negocio,
                        width=10000, height=46,
                        style=es.estilo_boton_marca()),
        ft.Container(height=20),
        ft.Divider(height=1, color=es.COLOR_BORDE),
        ft.Container(height=10),
        ft.Text("Métodos de pago", size=14,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Text(
            "Activa los que uses y configura la cuenta "
            "(teléfono, email, tarjeta) para mostrar al cliente.",
            size=11, color=es.COLOR_TEXTO_SUAVE),
        ft.Container(height=6),
        metodos_col,
        ft.Container(height=30),
    ], spacing=8, scroll=ft.ScrollMode.AUTO)

    return ft.View(
        route="/config-negocio",
        controls=[ft.Container(content=contenido, expand=True,
                               padding=ft.Padding.all(16))],
        appbar=ft.AppBar(
            title=ft.Text("Datos del negocio", size=16,
                          color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE,
            leading=ft.IconButton(
                ft.Icons.ARROW_BACK,
                on_click=lambda e: app.ir("/perfil"),
                icon_color=es.COLOR_ACENTO),
        ),
        bgcolor=es.COLOR_FONDO,
    )


def _fila_metodo(app, m, on_refresh):
    page = app.page
    cuenta = m.get("cuenta") or ""

    def toggle(e):
        cfg.actualizar_metodo_pago(m["clave"],
                                    activo=e.control.value)
        on_refresh()

    def editar(e):
        _editar_metodo(app, m, on_refresh)

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Switch(value=bool(m["activo"]),
                          active_color=es.COLOR_ACENTO,
                          on_change=toggle),
                ft.Text(m["etiqueta"], size=14, expand=True,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
                ft.IconButton(ft.Icons.EDIT, icon_size=18,
                              icon_color=es.COLOR_ACENTO,
                              on_click=editar),
            ], spacing=8,
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            ft.Text(f"Cuenta: {cuenta}" if cuenta
                    else "Sin cuenta configurada",
                    size=11, color=es.COLOR_TEXTO_SUAVE),
        ], spacing=2),
        padding=10,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=10,
    )


def _editar_metodo(app, m, on_refresh):
    page = app.page
    tf_cuenta = ft.TextField(
        label="Cuenta / teléfono / email / tarjeta",
        value=m.get("cuenta") or "",
        **es.estilo_textfield(12), height=54)
    tf_qr = ft.TextField(
        label="Ruta de imagen QR (opcional)",
        value=m.get("qr_imagen") or "",
        **es.estilo_textfield(12), height=54)

    def guardar(e):
        cfg.actualizar_metodo_pago(
            m["clave"],
            cuenta=tf_cuenta.value,
            qr_imagen=tf_qr.value)
        page.pop_dialog()
        snack(page, "Método actualizado", "ok")
        on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"Editar: {m['etiqueta']}"),
        content=ft.Column([
            tf_cuenta, tf_qr,
            ft.Text(
                "La ruta del QR debe ser un archivo de imagen "
                "accesible desde el dispositivo.",
                size=11, color=es.COLOR_TEXTO_SUAVE),
        ], tight=True, width=340, spacing=10),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))