"""
Modal para gestionar los proveedores de un producto.
"""
import flet as ft
import proveedores as pv
from ui import estilos as es
from ui.componentes import snack, mostrar_modal


def abrir_proveedores_producto(app, prod, on_refresh=None):
    page = app.page
    nombre_producto = prod.get("nombre") or ""
    if not nombre_producto:
        snack(page, "Producto sin nombre", "error")
        return

    cerrar_ref = {"fn": None}

    def cerrar():
        if cerrar_ref["fn"]:
            cerrar_ref["fn"]()

    lista_col = ft.Column(spacing=6, tight=True)

    def rebuild():
        lista_col.controls.clear()
        provs = pv.proveedores_de_producto(nombre_producto)
        if not provs:
            lista_col.controls.append(ft.Container(
                content=ft.Text(
                    "Sin proveedores asociados. Agrega uno abajo.",
                    size=12, color=es.COLOR_TEXTO_SUAVE),
                padding=14,
                bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=10))
        else:
            for p in provs:
                es_principal = p.get("es_principal") == 1
                lista_col.controls.append(_fila_prov_producto(
                    app, nombre_producto, p, es_principal,
                    rebuild, on_refresh))

        if hasattr(lista_col, "update"):
            try:
                lista_col.update()
            except Exception:
                pass

    def agregar(e):
        _dlg_agregar_proveedor(app, nombre_producto, rebuild, on_refresh)

    # Cabecera con título + X
    cabecera = ft.Row([
        ft.Text(f"Proveedores de «{nombre_producto}»",
                size=15, weight=ft.FontWeight.BOLD,
                color=es.COLOR_TEXTO, expand=True,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS),
        ft.IconButton(
            ft.Icons.CLOSE,
            icon_color=es.COLOR_TEXTO_SUAVE,
            tooltip="Cerrar",
            on_click=lambda e: cerrar()),
    ], vertical_alignment=ft.CrossAxisAlignment.CENTER)

    contenido = ft.Column([
        cabecera,
        ft.Container(height=6),
        ft.Text(
            "Marca uno como principal para que aparezca por defecto "
            "al dar entrada.",
            size=11, color=es.COLOR_TEXTO_SUAVE),
        ft.Container(height=10),
        lista_col,
        ft.Container(height=10),
        ft.FilledButton(
            "Agregar proveedor",
            icon=ft.Icons.ADD,
            on_click=agregar,
            width=10000, height=42,
            style=es.estilo_boton_marca()),
    ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO)

    panel = ft.Container(
        content=contenido,
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=16,
        padding=20,
        width=440,
        shadow=ft.BoxShadow(
            blur_radius=20, spread_radius=0,
            color="#00000099",
            offset=ft.Offset(0, 6)),
        border=ft.Border.all(1, es.COLOR_BORDE),
    )

    cerrar_ref["fn"] = mostrar_modal(
        page, panel, on_close=on_refresh if on_refresh else None)
    rebuild()


def _fila_prov_producto(app, nombre_producto, p, es_principal,
                        rebuild, on_refresh):
    page = app.page

    def set_principal(e):
        try:
            if es_principal:
                pv.set_proveedor_principal(nombre_producto, 0)
            else:
                pv.set_proveedor_principal(nombre_producto, p["id"])
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        rebuild()

    def quitar(e):
        try:
            pv.desasociar_proveedor(nombre_producto, p["id"])
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        rebuild()

    return ft.Container(
        content=ft.Row([
            ft.Container(
                content=ft.Icon(
                    ft.Icons.STAR if es_principal
                    else ft.Icons.STOREFRONT_OUTLINED,
                    color=(es.COLOR_ACENTO if es_principal
                           else es.COLOR_TEXTO_SUAVE),
                    size=20),
                bgcolor=(es.COLOR_ACENTO_SUAVE if es_principal
                         else es.COLOR_SUPERFICIE_2),
                padding=8, border_radius=10),
            ft.Column([
                ft.Text(p["nombre"], size=14,
                        weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(
                    "Principal" if es_principal
                    else "Secundario",
                    size=11,
                    color=(es.COLOR_ACENTO if es_principal
                           else es.COLOR_TEXTO_SUAVE)),
            ], spacing=2, expand=True),
            ft.IconButton(
                ft.Icons.STAR_BORDER if not es_principal
                else ft.Icons.STAR,
                icon_size=20,
                icon_color=(es.COLOR_ACENTO if es_principal
                            else es.COLOR_TEXTO_TENUE),
                tooltip=("Quitar principal" if es_principal
                         else "Marcar como principal"),
                on_click=set_principal),
            ft.IconButton(
                ft.Icons.CLOSE, icon_size=18,
                icon_color=es.COLOR_PELIGRO,
                tooltip="Quitar proveedor",
                on_click=quitar),
        ], spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=10,
        bgcolor=es.COLOR_SUPERFICIE_2,
        border_radius=10,
    )


def _dlg_agregar_proveedor(app, nombre_producto, on_done, on_refresh):
    page = app.page

    provs = pv.listar_proveedores(solo_activos=True)
    actuales_ids = {p["id"] for p in
                    pv.proveedores_de_producto(nombre_producto)}
    disponibles = [p for p in provs if p["id"] not in actuales_ids]

    ops = [ft.DropdownOption(key="", text="— Selecciona —")]
    for p in disponibles:
        ops.append(ft.DropdownOption(
            key=str(p["id"]), text=p["nombre"]))

    dd = ft.Dropdown(
        label="Proveedor existente",
        value="",
        options=ops,
        **es.borde_textfield(12))

    sw_principal = ft.Switch(
        label="Marcar como principal",
        value=False,
        active_color=es.COLOR_ACENTO)

    tf_nuevo = ft.TextField(
        label="O crea uno nuevo (nombre)",
        **es.estilo_textfield(12), height=54)
    tf_tel = ft.TextField(
        label="Teléfono del nuevo (opcional)",
        keyboard_type=ft.KeyboardType.PHONE,
        **es.estilo_textfield(12), height=54)

    error_lbl = ft.Text("", color=es.COLOR_PELIGRO, size=12)

    def guardar(e):
        error_lbl.value = ""
        try:
            nuevo_nombre = (tf_nuevo.value or "").strip()
            if nuevo_nombre:
                pid = pv.crear_proveedor(nuevo_nombre,
                                          telefono=tf_tel.value)
            elif dd.value:
                pid = int(dd.value)
            else:
                error_lbl.value = "Selecciona o crea un proveedor"
                page.update()
                return

            pv.asociar_proveedor(
                nombre_producto, pid,
                es_principal=1 if sw_principal.value else 0)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        page.pop_dialog()
        snack(page, "Proveedor asociado", "ok")
        on_done()
        if on_refresh:
            on_refresh()

    page.show_dialog(ft.AlertDialog(
        title=ft.Text("Agregar proveedor"),
        content=ft.Column([
            dd,
            sw_principal,
            ft.Divider(height=1, color=es.COLOR_BORDE),
            ft.Text("O crea uno nuevo:", size=11,
                    color=es.COLOR_TEXTO_SUAVE),
            tf_nuevo,
            tf_tel,
            error_lbl,
        ], tight=True, width=380, spacing=10,
            scroll=ft.ScrollMode.AUTO),
        actions=[
            ft.TextButton("Cancelar",
                          on_click=lambda e: page.pop_dialog()),
            ft.FilledButton("Agregar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ],
        actions_alignment=ft.MainAxisAlignment.END,
    ))