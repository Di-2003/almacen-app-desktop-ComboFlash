import flet as ft
import inventario as inv
import locales as loc
import categorias as cats
from db import GENERAL_ID
from ui import estilos as es
from ui.componentes import (
    fila_producto, snack, campo_busqueda, empty_state,
    bottom_sheet, imagen_opcional, mounted,
    cerrar_dialogo, panel_modal, mostrar_modal,
)
from ui import modales


PASO_PAGINACION = 30


def barra_navegacion(app, indice):
    """Barra inferior de 5 botones: Inicio · POS · Métricas · Historial · Perfil."""
    def cambiar(e):
        rutas = ["/principal", "/pos", "/dashboard",
                 "/movimientos", "/perfil"]
        app.ir(rutas[e.control.selected_index])

    return ft.NavigationBar(
        selected_index=indice,
        bgcolor=es.COLOR_SUPERFICIE,
        indicator_color=es.COLOR_ACENTO_SUAVE,
        label_behavior=ft.NavigationBarLabelBehavior.ALWAYS_SHOW,
        destinations=[
            ft.NavigationBarDestination(
                icon=ft.Icons.HOME_OUTLINED,
                selected_icon=ft.Icons.HOME,
                label="Inicio"),
            ft.NavigationBarDestination(
                icon=ft.Icons.POINT_OF_SALE_OUTLINED,
                selected_icon=ft.Icons.POINT_OF_SALE,
                label="POS"),
            ft.NavigationBarDestination(
                icon=ft.Icons.BAR_CHART_OUTLINED,
                selected_icon=ft.Icons.BAR_CHART,
                label="Métricas"),
            ft.NavigationBarDestination(
                icon=ft.Icons.HISTORY_OUTLINED,
                selected_icon=ft.Icons.HISTORY,
                label="Historial"),
            ft.NavigationBarDestination(
                icon=ft.Icons.PERSON_OUTLINE,
                selected_icon=ft.Icons.PERSON,
                label="Perfil"),
        ],
        on_change=cambiar,
    )


def _tarjeta_resumen(total, n_productos, n_rojo=0):
    extras = []
    if n_rojo > 0:
        extras.append(
            ft.Container(
                content=ft.Text(f"{n_rojo} en crítico",
                                size=10, color="white",
                                weight=ft.FontWeight.BOLD),
                bgcolor=es.COLOR_PELIGRO,
                padding=ft.Padding.symmetric(horizontal=8, vertical=3),
                border_radius=20,
            )
        )

    fila_sup = ft.Row(
        [
            ft.Container(
                content=ft.Icon(ft.Icons.INVENTORY_2,
                                color=es.COLOR_MARCA_NEGRO, size=18),
                bgcolor=es.COLOR_ACENTO,
                padding=10, border_radius=10,
            ),
            ft.Text("Valor del inventario", size=12,
                    color=es.COLOR_TEXTO_SUAVE,
                    weight=ft.FontWeight.W_600,
                    expand=True),
            ft.Container(
                content=ft.Text(f"{n_productos} prod.",
                                size=11,
                                weight=ft.FontWeight.BOLD,
                                color=es.COLOR_ACENTO),
                bgcolor=es.COLOR_ACENTO_SUAVE,
                padding=ft.Padding.symmetric(horizontal=10, vertical=5),
                border_radius=20,
            ),
        ],
        spacing=10,
        vertical_alignment=ft.CrossAxisAlignment.CENTER,
    )

    fila_valor = ft.Text(
        f"${total:,.2f}",
        size=22, weight=ft.FontWeight.BOLD,
        color=es.COLOR_TEXTO,
        max_lines=1,
        overflow=ft.TextOverflow.ELLIPSIS,
    )

    contenido = [fila_sup, ft.Container(height=6), fila_valor]
    if extras:
        contenido += [ft.Container(height=6), ft.Row(extras, spacing=6)]

    return ft.Container(
        content=ft.Column(contenido, spacing=0),
        padding=14,
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=16,
        shadow=ft.BoxShadow(
            blur_radius=10, spread_radius=0,
            color=es.SOMBRA_CARD,
            offset=ft.Offset(0, 2),
        ),
    )


def _chip_local(app):
    nombre = loc.nombre_local(app.local_id)

    def abrir_selector(e):
        _abrir_selector_local(app)

    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.STOREFRONT,
                        color=es.COLOR_ACENTO, size=18),
                ft.Text(nombre, size=13,
                        weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN,
                        color=es.COLOR_ACENTO, size=18),
            ],
            spacing=6,
            tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        bgcolor=es.COLOR_ACENTO_SUAVE,
        border_radius=20,
        on_click=abrir_selector,
        ink=True,
    )


def _chip_tipo(app):
    cat_id = app.filtro_tipo
    if cat_id is None:
        etiqueta = "Todos"
    else:
        c = cats.obtener_categoria(cat_id)
        etiqueta = c["nombre"] if c else "Todos"

    def abrir(e):
        _abrir_selector_tipo(app)

    return ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.CATEGORY,
                        color=es.COLOR_ACENTO, size=16),
                ft.Text(etiqueta, size=12,
                        weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO),
                ft.Icon(ft.Icons.ARROW_DROP_DOWN,
                        color=es.COLOR_ACENTO, size=16),
            ],
            spacing=4, tight=True,
        ),
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        bgcolor=es.COLOR_ACENTO_SUAVE,
        border_radius=20,
        on_click=abrir,
        ink=True,
    )


def _abrir_selector_local(app):
    page = app.page
    items = loc.listar_para_menu()
    actual = app.local_id
    bs_ref = {"bs": None}

    def elegir(lid):
        def _hacer(e):
            def _despues():
                app.cambiar_local(lid)
            cerrar_dialogo(page, bs_ref["bs"], on_close=_despues)
        return _hacer

    tiles = []
    for lid, nombre in items:
        es_actual = (lid == actual)
        icono = (ft.Icons.STAR if es_actual
                 else ft.Icons.STOREFRONT_OUTLINED)
        color = es.COLOR_ACENTO if es_actual else es.COLOR_TEXTO_SUAVE
        tiles.append(ft.Container(
            content=ft.Row(
                [
                    ft.Icon(icono, color=color, size=20),
                    ft.Text(nombre, size=14, color=es.COLOR_TEXTO,
                            weight=(ft.FontWeight.BOLD if es_actual
                                    else ft.FontWeight.NORMAL),
                            expand=True),
                    ft.Icon(ft.Icons.CHECK, color=es.COLOR_ACENTO, size=20)
                    if es_actual else ft.Container(width=20),
                ],
                spacing=12,
            ),
            padding=14,
            bgcolor=(es.COLOR_ACENTO_SUAVE if es_actual
                     else es.COLOR_SUPERFICIE_2),
            border_radius=10,
            on_click=elegir(lid),
            ink=True,
        ))

    contenido = ft.Column([
        ft.Text("Cambiar de local", size=16,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Container(height=4),
        ft.Column(tiles, spacing=6),
    ], spacing=6, tight=True)

    bs = bottom_sheet(contenido, page=page)
    bs_ref["bs"] = bs
    page.show_dialog(bs)


# ============================================================
# SELECTOR DE TIPOS
# ============================================================

def _abrir_selector_tipo(app):
    page = app.page

    def construir_contenido():
        def elegir(cat_id):
            def _hacer(e):
                cerrar_actual()
                app.set_filtro_tipo(cat_id)
            return _hacer

        def crear_nueva(e):
            cerrar_actual()
            _dlg_nueva_categoria_inicio(app, on_creada=app.refrescar)

        def abrir_acciones(cat):
            def _hacer(e):
                cerrar_actual()
                _menu_acciones_categoria(app, cat, on_done=app.refrescar)
            return _hacer

        rol = app.usuario["rol"]
        puede_admin = rol in ("admin", "almacen")

        tiles = []

        es_todos = app.filtro_tipo is None
        tiles.append(ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.ALL_INCLUSIVE,
                        color=es.COLOR_ACENTO if es_todos
                        else es.COLOR_TEXTO_SUAVE,
                        size=20),
                ft.Text("Todos", size=14, color=es.COLOR_TEXTO,
                        expand=True,
                        weight=(ft.FontWeight.BOLD if es_todos
                                else ft.FontWeight.NORMAL)),
                ft.Icon(ft.Icons.CHECK, color=es.COLOR_ACENTO, size=20)
                if es_todos else ft.Container(width=20),
            ], spacing=12),
            padding=14,
            bgcolor=(es.COLOR_ACENTO_SUAVE if es_todos
                     else es.COLOR_SUPERFICIE_2),
            border_radius=10, on_click=elegir(None), ink=True,
        ))

        todas = cats.listar_categorias(solo_activas=False)
        activas = [c for c in todas if c["activo"] == 1]
        inactivas = [c for c in todas if c["activo"] == 0]
        ordenadas = activas + inactivas

        for c in ordenadas:
            activa = (c["activo"] == 1)
            es_actual = (app.filtro_tipo == c["id"])

            if activa:
                texto_color = es.COLOR_TEXTO
                icono_color = (es.COLOR_ACENTO if es_actual
                               else es.COLOR_TEXTO_SUAVE)
                cuerpo_on_click = elegir(c["id"])
                cuerpo_ink = True
            else:
                texto_color = es.COLOR_TEXTO_TENUE
                icono_color = es.COLOR_TEXTO_TENUE
                cuerpo_on_click = None
                cuerpo_ink = False

            cuerpo = ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CATEGORY,
                            color=icono_color, size=20),
                    ft.Text(
                        c["nombre"] + ("" if activa else "  (inactivo)"),
                        size=14, color=texto_color, expand=True,
                        weight=(ft.FontWeight.BOLD
                                if es_actual else ft.FontWeight.NORMAL)),
                    ft.Icon(ft.Icons.CHECK, color=es.COLOR_ACENTO,
                            size=18) if es_actual
                    else ft.Container(width=18),
                ], spacing=12),
                padding=ft.Padding.only(left=14, top=12, right=4,
                                        bottom=12),
                on_click=cuerpo_on_click,
                ink=cuerpo_ink,
                expand=True,
            )

            flecha = ft.IconButton(
                ft.Icons.CHEVRON_RIGHT,
                icon_color=es.COLOR_TEXTO_TENUE,
                icon_size=20,
                tooltip="Opciones",
                on_click=abrir_acciones(c),
            )

            tiles.append(ft.Container(
                content=ft.Row([cuerpo, flecha], spacing=0),
                bgcolor=(es.COLOR_ACENTO_SUAVE if es_actual
                         else es.COLOR_SUPERFICIE_2),
                border_radius=10,
            ))

        if puede_admin:
            tiles.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.ADD, color=es.COLOR_ACENTO, size=20),
                    ft.Text("Nueva categoría", size=14,
                            color=es.COLOR_ACENTO,
                            weight=ft.FontWeight.W_600),
                ], spacing=12),
                padding=14,
                bgcolor=es.COLOR_SUPERFICIE_2,
                border=ft.Border.all(1, es.COLOR_ACENTO),
                border_radius=10,
                on_click=crear_nueva,
                ink=True,
            ))

        return ft.Column([
            ft.Text("Filtrar por tipo", size=16,
                    weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
            ft.Container(height=10),
            ft.Column(tiles, spacing=6),
            ft.Container(height=10),
            ft.Row([
                ft.TextButton(
                    "Cerrar",
                    on_click=lambda e: cerrar_actual(),
                    style=ft.ButtonStyle(color=es.COLOR_TEXTO_SUAVE),
                ),
            ], alignment=ft.MainAxisAlignment.END),
        ], spacing=0, tight=True, scroll=ft.ScrollMode.AUTO)

    cerrar_ref = {"fn": None}

    def cerrar_actual():
        if cerrar_ref["fn"]:
            cerrar_ref["fn"]()

    contenido = panel_modal(construir_contenido(), width=360)
    cerrar_ref["fn"] = mostrar_modal(page, contenido)


def _menu_acciones_categoria(app, cat, on_done=None):
    page = app.page
    cerrar_ref = {"fn": None}

    def cerrar_actual():
        if cerrar_ref["fn"]:
            cerrar_ref["fn"]()

    def renombrar(e):
        cerrar_actual()
        _dlg_renombrar_categoria(app, cat, on_done=on_done)

    def toggle(e):
        cerrar_actual()
        _toggle_categoria(app, cat, on_done=on_done)

    accion = "Desactivar" if cat["activo"] else "Activar"

    contenido = ft.Column([
        ft.Text(cat["nombre"], size=17, weight=ft.FontWeight.BOLD,
                color=es.COLOR_TEXTO),
        ft.Container(height=10),
        ft.ListTile(
            leading=ft.Icon(ft.Icons.EDIT, color=es.COLOR_ACENTO),
            title=ft.Text("Renombrar", color=es.COLOR_TEXTO),
            on_click=renombrar,
        ),
        ft.ListTile(
            leading=ft.Icon(
                ft.Icons.TOGGLE_ON if cat["activo"]
                else ft.Icons.TOGGLE_OFF,
                color=(es.COLOR_PELIGRO if cat["activo"]
                       else es.COLOR_EXITO)),
            title=ft.Text(accion, color=es.COLOR_TEXTO),
            on_click=toggle,
        ),
        ft.Container(height=4),
        ft.Row([
            ft.TextButton(
                "Cerrar",
                on_click=lambda e: cerrar_actual(),
                style=ft.ButtonStyle(color=es.COLOR_TEXTO_SUAVE),
            ),
        ], alignment=ft.MainAxisAlignment.END),
    ], spacing=0, tight=True)

    contenido_wrap = panel_modal(contenido, width=320)
    cerrar_ref["fn"] = mostrar_modal(page, contenido_wrap)


def _dlg_renombrar_categoria(app, cat, on_done=None):
    page = app.page
    cerrar_ref = {"fn": None}

    def cerrar_actual():
        if cerrar_ref["fn"]:
            cerrar_ref["fn"]()

    tf = ft.TextField(label="Nuevo nombre", value=cat["nombre"],
                      autofocus=True,
                      **es.estilo_textfield(12), height=54)
    error_lbl = ft.Text("", size=12, color=es.COLOR_PELIGRO)

    def guardar(e):
        error_lbl.value = ""
        try:
            cats.renombrar_categoria(cat["id"], tf.value or "")
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        snack(page, "Tipo renombrado", "ok")
        cerrar_actual()

    def cancelar(e):
        cerrar_actual()

    contenido = ft.Column([
        ft.Text(f"Renombrar: {cat['nombre']}", size=16,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Container(height=10),
        tf,
        error_lbl,
        ft.Container(height=8),
        ft.Row([
            ft.TextButton("Cancelar", on_click=cancelar,
                          style=ft.ButtonStyle(
                              color=es.COLOR_TEXTO_SUAVE)),
            ft.FilledButton("Guardar", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ], alignment=ft.MainAxisAlignment.END),
    ], spacing=0, tight=True)

    panel = panel_modal(contenido, width=340)

    def on_close_final():
        if on_done:
            on_done()

    cerrar_ref["fn"] = mostrar_modal(page, panel, on_close=on_close_final)


def _toggle_categoria(app, cat, on_done=None):
    page = app.page
    cerrar_ref = {"fn": None}

    def cerrar_actual():
        if cerrar_ref["fn"]:
            cerrar_ref["fn"]()

    accion = "Desactivar" if cat["activo"] else "Activar"

    def hacer(e):
        try:
            if cat["activo"]:
                cats.eliminar_categoria(cat["id"])
            else:
                cats.crear_categoria(cat["nombre"])
        except Exception as ex:
            snack(page, str(ex), "error")
            return
        msg = (f"«{cat['nombre']}» desactivado" if cat["activo"]
               else f"«{cat['nombre']}» activado")
        snack(page, msg, "ok")
        if app.filtro_tipo == cat["id"] and cat["activo"]:
            app.filtro_tipo = None
        cerrar_actual()

    def cancelar(e):
        cerrar_actual()

    texto = (f"¿{accion} el tipo «{cat['nombre']}»?\n\n"
             "Los productos que lo tengan quedarán como "
             "«Sin categoría»." if cat["activo"]
             else f"¿Activar el tipo «{cat['nombre']}»?")

    contenido = ft.Column([
        ft.Text(f"{accion} tipo", size=16,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Container(height=10),
        ft.Text(texto, size=13, color=es.COLOR_TEXTO),
        ft.Container(height=12),
        ft.Row([
            ft.TextButton("Cancelar", on_click=cancelar,
                          style=ft.ButtonStyle(
                              color=es.COLOR_TEXTO_SUAVE)),
            ft.FilledButton(
                accion, on_click=hacer,
                style=ft.ButtonStyle(
                    bgcolor=(es.COLOR_PELIGRO if cat["activo"]
                             else es.COLOR_EXITO),
                    color="white")),
        ], alignment=ft.MainAxisAlignment.END),
    ], spacing=0, tight=True)

    panel = panel_modal(contenido, width=340)

    def on_close_final():
        if on_done:
            on_done()

    cerrar_ref["fn"] = mostrar_modal(page, panel, on_close=on_close_final)


def _dlg_nueva_categoria_inicio(app, on_creada=None):
    page = app.page
    cerrar_ref = {"fn": None}

    def cerrar_actual():
        if cerrar_ref["fn"]:
            cerrar_ref["fn"]()

    tf = ft.TextField(
        label="Nombre del tipo", autofocus=True,
        **es.estilo_textfield(12), height=54)
    sugerencia = ft.Text("", size=11, color=es.COLOR_ACENTO)
    error_lbl = ft.Text("", size=12, color=es.COLOR_PELIGRO)

    def on_change(e):
        val = (tf.value or "").strip()
        sugerencia.value = ""
        if val:
            existente = cats.buscar_por_nombre(val)
            if existente and existente["activo"]:
                sugerencia.value = f"«{existente['nombre']}» ya existe"
            elif existente and not existente["activo"]:
                sugerencia.value = (f"«{existente['nombre']}» existe "
                                    f"inactivo — se reactivará")
        try:
            sugerencia.update()
        except Exception:
            pass

    tf.on_change = on_change

    def guardar(e):
        error_lbl.value = ""
        nombre = (tf.value or "").strip()
        if not nombre:
            error_lbl.value = "Escribe un nombre"
            page.update()
            return
        try:
            cats.crear_categoria(nombre)
        except Exception as ex:
            error_lbl.value = str(ex)
            page.update()
            return
        snack(page, "Categoría creada", "ok")
        cerrar_actual()

    def cancelar(e):
        cerrar_actual()

    contenido = ft.Column([
        ft.Text("Nueva categoría", size=16,
                weight=ft.FontWeight.BOLD, color=es.COLOR_TEXTO),
        ft.Container(height=10),
        tf,
        sugerencia,
        error_lbl,
        ft.Container(height=8),
        ft.Row([
            ft.TextButton("Cancelar", on_click=cancelar,
                          style=ft.ButtonStyle(
                              color=es.COLOR_TEXTO_SUAVE)),
            ft.FilledButton("Crear", on_click=guardar,
                            style=es.estilo_boton_marca()),
        ], alignment=ft.MainAxisAlignment.END),
    ], spacing=0, tight=True)

    panel = panel_modal(contenido, width=340)

    def on_close_final():
        if on_creada:
            on_creada()

    cerrar_ref["fn"] = mostrar_modal(page, panel, on_close=on_close_final)


# ============================================================
# VISTA PRINCIPAL
# ============================================================

def vista_principal(app):
    page = app.page

    contenedor_resumen = ft.Container()
    lista_cont = ft.Column(spacing=10, scroll=ft.ScrollMode.AUTO,
                            expand=True)
    estado = {"visibles": PASO_PAGINACION}

    def refrescar():
        try:
            lista_cont.controls.clear()

            productos = inv.listar_productos(app.local_id, solo_activos=True)

            if app.filtro_tipo is not None:
                productos = [p for p in productos
                             if p.get("categoria_id") == app.filtro_tipo]

            f = app.filtro
            if f:
                productos = [
                    p for p in productos
                    if f in p["nombre"].lower()
                    or f in (p.get("codigo") or "").lower()
                ]

            total_filtrado = len(productos)
            visibles = productos[:estado["visibles"]]

            for p in visibles:
                lista_cont.controls.append(fila_producto(
                    p,
                    on_tap=lambda e, prod=p:
                        modales.abrir_detalle_producto(
                            app, prod, on_refresh=refrescar)))

            if not productos:
                lista_cont.controls.append(empty_state(
                    ft.Icons.INBOX_OUTLINED,
                    "Sin productos",
                    "Ajusta los filtros o agrega uno nuevo."))
            elif total_filtrado > estado["visibles"]:
                restantes = total_filtrado - estado["visibles"]

                def cargar_mas(e):
                    estado["visibles"] += PASO_PAGINACION
                    refrescar()

                lista_cont.controls.append(ft.Container(
                    content=ft.TextButton(
                        f"Ver {min(PASO_PAGINACION, restantes)} más "
                        f"({restantes} restantes)",
                        icon=ft.Icons.EXPAND_MORE,
                        on_click=cargar_mas,
                        style=ft.ButtonStyle(color=es.COLOR_ACENTO)),
                    alignment=ft.Alignment.CENTER,
                    padding=20,
                ))

            t = inv.totales_local(app.local_id)
            n_rojo = sum(1 for p in productos
                         if inv.color_de_producto(p) == "rojo")
            contenedor_resumen.content = _tarjeta_resumen(
                t["invertido"], total_filtrado, n_rojo)

            if mounted(lista_cont):
                lista_cont.update()
            if mounted(contenedor_resumen):
                contenedor_resumen.update()
        except Exception as ex:
            print(f"[ERROR] refrescar(): {ex}")
            import traceback
            traceback.print_exc()

    def on_search(e):
        app.filtro = (e.control.value or "").lower()
        estado["visibles"] = PASO_PAGINACION
        refrescar()

    cap = campo_busqueda(
        hint="Buscar por nombre o código…",
        valor=app.filtro,
        on_change=on_search,
    )

    def abrir_entrada(e):
        modales.modal_entrada(app, on_refresh=refrescar)

    def abrir_salida(e):
        modales.modal_salida(app, on_refresh=refrescar)

    rol = app.usuario["rol"]
    puede_operar = rol in ("admin", "almacen") and not app.es_general()

    if puede_operar:
        botones = ft.Row([
            ft.FilledButton(
                "Entrada", icon=ft.Icons.ADD,
                on_click=abrir_entrada,
                expand=True, height=46,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_EXITO, color="white",
                    shape=ft.RoundedRectangleBorder(
                        radius=ft.BorderRadius.all(12)))),
            ft.FilledButton(
                "Salida", icon=ft.Icons.REMOVE,
                on_click=abrir_salida,
                expand=True, height=46,
                style=ft.ButtonStyle(
                    bgcolor=es.COLOR_PELIGRO, color="white",
                    shape=ft.RoundedRectangleBorder(
                        radius=ft.BorderRadius.all(12)))),
        ], spacing=10)
    else:
        botones = ft.Container(height=0)

    cabecera = ft.Container(
        content=ft.Column([
            ft.Row([_chip_local(app), _chip_tipo(app)],
                   spacing=8, wrap=False),
            ft.Container(height=2),
            cap,
            ft.Container(height=2),
            contenedor_resumen,
            ft.Container(height=2),
            botones,
        ], spacing=8),
        padding=ft.Padding.only(left=14, top=14, right=14, bottom=4),
        bgcolor=es.COLOR_FONDO,
    )

    refrescar()

    logo_fallback = ft.Icon(ft.Icons.INVENTORY_2,
                            color=es.COLOR_ACENTO, size=26)
    logo = imagen_opcional("icon.png", logo_fallback,
                           width=30, height=30)

    nombre_usuario = app.usuario["username"] if app.usuario else ""

    # FAB: acceso rápido al POS cuando el usuario puede vender
    fab = None
    if puede_operar:
        fab = ft.FloatingActionButton(
            icon=ft.Icons.POINT_OF_SALE,
            bgcolor=es.COLOR_ACENTO,
            foreground_color="#ffffff",
            tooltip="Nueva venta (POS)",
            on_click=lambda e: app.ir("/pos"),
        )

    return ft.View(
        route="/principal",
        controls=[
            cabecera,
            ft.Container(content=lista_cont, expand=True),
        ],
        appbar=ft.AppBar(
            title=ft.Row(
                [logo,
                 ft.Text(f"Almacen {nombre_usuario}", size=15,
                         color=es.COLOR_TEXTO)],
                spacing=8,
            ),
            bgcolor=es.COLOR_SUPERFICIE,
            elevation=0,
            leading=ft.IconButton(
                ft.Icons.MENU,
                on_click=lambda e: app.abrir_drawer(),
                icon_color=es.COLOR_ACENTO),
            actions=[
                ft.IconButton(
                    ft.Icons.REFRESH,
                    on_click=lambda e: (refrescar(),
                                        snack(page, "Actualizado", "ok")),
                    icon_color=es.COLOR_ACENTO,
                ),
            ],
        ),
        floating_action_button=fab,
        navigation_bar=barra_navegacion(app, 0),
        bgcolor=es.COLOR_FONDO,
    )