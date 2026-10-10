import flet as ft
from ui import estilos as es
import os
from pathlib import Path


def ruta_asset(nombre: str) -> str:
    base = os.environ.get("FLET_ASSETS_DIR")
    if base:
        return str(Path(base) / nombre)
    raiz = Path(__file__).resolve().parent.parent
    return str(raiz / "assets" / nombre)   # ← "recursos" → "assets"


def src_asset(nombre: str) -> str:
    """
    Nombre para ft.Image(src=...).
    Flet lo resuelve contra assets_dir ('recursos'), así que aquí
    va SOLO el nombre del archivo, sin la carpeta.
    """
    return nombre


def imagen_opcional(nombre, fallback, width=None, height=None,
                    fit=ft.BoxFit.CONTAIN):
    try:
        if Path(ruta_asset(nombre)).exists():
            # src es relativo a assets_dir → solo el nombre
            return ft.Image(src=src_asset(nombre), fit=fit,
                            width=width, height=height)
    except Exception:
        pass
    return fallback


def chip_estado(color: str) -> ft.Container:
    return ft.Container(
        width=14, height=14,
        bgcolor=es.COLOR_ESTADO_TEXTO[color],
        border_radius=7,
        border=ft.Border.all(1, es.COLOR_ESTADO_BORDE[color]),
    )


def chip_inactivo() -> ft.Container:
    return ft.Container(
        width=14, height=14,
        bgcolor=es.COLOR_TEXTO_TENUE,
        border_radius=7,
    )


def badge(texto, color=None) -> ft.Container:
    color = color or es.COLOR_ACENTO
    return ft.Container(
        content=ft.Text(str(texto), size=10,
                        color=es.COLOR_MARCA_NEGRO,
                        weight=ft.FontWeight.BOLD),
        bgcolor=color,
        padding=ft.Padding.symmetric(horizontal=7, vertical=2),
        border_radius=10,
    )


def tarjeta_metrica(titulo, valor, subtitulo="", color=None, on_tap=None):
    color = color or es.COLOR_ACENTO
    contenido = ft.Column(
        [
            ft.Row([
                ft.Container(width=8, height=8, bgcolor=color,
                             border_radius=4),
                ft.Text(titulo, size=11, color=es.COLOR_TEXTO_SUAVE,
                        weight=ft.FontWeight.W_600),
            ], spacing=6, tight=True),
            ft.Text(valor, size=24, weight=ft.FontWeight.BOLD,
                    color=es.COLOR_TEXTO),
            ft.Text(subtitulo, size=10, color=es.COLOR_TEXTO_TENUE)
            if subtitulo else ft.Container(height=1),
        ],
        spacing=4,
    )
    cont = ft.Container(
        content=contenido,
        padding=16,
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=16,
        shadow=ft.BoxShadow(
            blur_radius=3, spread_radius=0,
            color=es.SOMBRA_SUAVE,
            offset=ft.Offset(0, 1),
        ),
    )
    if on_tap:
        cont.on_click = on_tap
        cont.ink = True
    return cont


def fila_producto(prod, on_tap=None) -> ft.Container:
    import inventario as inv
    color = inv.color_de_producto(prod)
    pc_cup = float(prod.get("precio_costo", 0) or 0)
    pu_cup = float(prod.get("precio_unitario", 0) or 0)
    mc = (prod.get("moneda_costo") or "CUP").upper()
    mv = (prod.get("moneda_venta") or "CUP").upper()
    stock_txt = inv.fmt_cantidad(prod["stock"])
    codigo = (prod.get("codigo") or "").strip()
    esta_activo = prod.get("activo", 1) == 1

    cabecera = ft.Row(
        [
            ft.Text(prod["nombre"], size=15,
                    weight=ft.FontWeight.W_600,
                    color=es.COLOR_TEXTO, max_lines=2,
                    overflow=ft.TextOverflow.ELLIPSIS, expand=True),
            badge(codigo, es.COLOR_ACENTO) if codigo
            else ft.Container(width=1),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    def _dato(label, valor, sub=""):
        hijos = [
            ft.Text(label, size=10, color=es.COLOR_TEXTO_TENUE),
            ft.Text(valor, size=13, color=es.COLOR_TEXTO,
                    weight=ft.FontWeight.W_600),
        ]
        if sub:
            hijos.append(ft.Text(sub, size=9,
                                 color=es.COLOR_ACENTO))
        return ft.Column(hijos, spacing=2)

    sub_costo = f"({mc})" if mc != "CUP" else ""
    sub_venta = f"({mv})" if mv != "CUP" else ""

    fila_datos = ft.Row(
        [
            ft.Container(content=_dato("Stock", stock_txt), expand=True),
            ft.Container(content=_dato("Costo", f"${inv.fmt_precio(pc_cup)}",
                                       sub_costo), expand=True),
            ft.Container(content=_dato("Venta", f"${inv.fmt_precio(pu_cup)}",
                                       sub_venta), expand=True),
        ],
        spacing=0,
    )

    chip_ctrl = chip_estado(color) if esta_activo else chip_inactivo()

    return ft.Container(
        content=ft.Column([
            ft.Row([
                ft.Container(cabecera, expand=True),
                chip_ctrl,
            ], spacing=8, vertical_alignment=ft.CrossAxisAlignment.START),
            ft.Container(height=8),
            fila_datos,
        ], spacing=0),
        padding=ft.Padding.only(left=16, top=14, right=14, bottom=14),
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=14,
        border=ft.Border.all(1, es.COLOR_BORDE),
        shadow=ft.BoxShadow(
            blur_radius=8, spread_radius=0,
            color=es.SOMBRA_SUAVE,
            offset=ft.Offset(0, 2),
        ),
        on_click=on_tap,
        ink=True,
        opacity=0.6 if not esta_activo else 1.0,
    )


def caja_info(texto, tipo="info") -> ft.Container:
    colores = {
        "info": (es.COLOR_INFO_SUAVE, es.COLOR_INFO),
        "ok": (es.COLOR_EXITO_SUAVE, es.COLOR_EXITO),
        "warn": (es.COLOR_AMBAR_SUAVE, es.COLOR_AMBAR),
        "error": (es.COLOR_PELIGRO_SUAVE, es.COLOR_PELIGRO),
    }
    bg, fg = colores.get(tipo, colores["info"])
    return ft.Container(
        content=ft.Text(texto, size=12, color=fg),
        bgcolor=bg,
        padding=ft.Padding.symmetric(horizontal=14, vertical=10),
        border_radius=10,
    )


def campo_busqueda(hint="Buscar…", on_change=None, valor=""):
    tf = ft.TextField(
        value=valor, hint_text=hint,
        border=es.borde_textfield_none(),
        filled=False, bgcolor="transparent",
        content_padding=ft.Padding.symmetric(horizontal=0, vertical=12),
        on_change=on_change, expand=True, text_size=14,
    )
    cont = ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.SEARCH, color=es.COLOR_TEXTO_TENUE, size=20),
            tf,
        ], spacing=6, vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=26,
        padding=ft.Padding.symmetric(horizontal=16, vertical=2),
        shadow=ft.BoxShadow(
            blur_radius=8, spread_radius=0,
            color=es.SOMBRA_SUAVE,
            offset=ft.Offset(0, 2),
        ),
    )
    cont._tf = tf
    return cont


def empty_state(icono, titulo, subtitulo="") -> ft.Container:
    return ft.Container(
        content=ft.Column([
            ft.Container(
                content=ft.Icon(icono, size=36, color=es.COLOR_ACENTO),
                bgcolor=es.COLOR_ACENTO_SUAVE,
                padding=18, border_radius=100,
            ),
            ft.Container(height=10),
            ft.Text(titulo, size=15, weight=ft.FontWeight.W_600,
                    color=es.COLOR_TEXTO, text_align=ft.TextAlign.CENTER,
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
            ft.Text(subtitulo, size=12, color=es.COLOR_TEXTO_SUAVE,
                    text_align=ft.TextAlign.CENTER, max_lines=3,
                    overflow=ft.TextOverflow.ELLIPSIS)
            if subtitulo else ft.Container(height=1),
        ], horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6, tight=True),
        padding=24, alignment=ft.Alignment.CENTER,
    )


def bottom_sheet(content, page=None, alto_max_pct=0.85) -> ft.BottomSheet:
    alto = None
    if page is not None:
        try:
            h = getattr(page, "height", None)
            if not h:
                w = getattr(page, "window", None)
                if w is not None:
                    h = getattr(w, "height", None)
            if h:
                alto = int(h * alto_max_pct)
        except Exception:
            pass
    col = ft.Column([
        ft.Row([ft.Container(width=40, height=4,
                              bgcolor=es.COLOR_BORDE_FUERTE,
                              border_radius=2)],
               alignment=ft.MainAxisAlignment.CENTER),
        ft.Container(height=8),
        ft.Container(content=content, expand=True),
    ], tight=True, spacing=0, scroll=ft.ScrollMode.AUTO)
    cont = ft.Container(
        content=col,
        padding=ft.Padding.only(left=16, top=10, right=16, bottom=20),
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=ft.BorderRadius.only(top_left=20, top_right=20),
    )
    if alto:
        cont.height = alto
    return ft.BottomSheet(content=cont)


def snack(page, texto, tipo="info"):
    """SnackBar diferido para no chocar con cierres de diálogos.
    Aparece abajo. Para notificaciones arriba usar toast()."""
    colores = {
        "info": "#374151", "ok": "#16a34a",
        "error": "#dc2626", "warn": "#ca8a04",
    }

    async def _show():
        import asyncio
        try:
            await asyncio.sleep(0.15)
        except Exception:
            pass
        sb = ft.SnackBar(
            content=ft.Text(texto, color="white", size=13),
            bgcolor=colores.get(tipo, "#374151"),
            duration=15000,
            behavior=ft.SnackBarBehavior.FLOATING,
            show_close_icon=True,
            close_icon_color="white",
        )
        try:
            page.open(sb)
        except Exception:
            try:
                page.show_dialog(sb)
            except Exception:
                pass

    try:
        page.run_task(_show)
    except Exception:
        pass


def toast(page, texto, tipo="ok", duracion=2.0):
    """
    Notificación flotante en la parte SUPERIOR de la pantalla.
    Alternativa a snack() cuando el mensaje no debe aparecer abajo
    (por ejemplo, al agregar al carrito en el POS).
    Se autodestruye después de `duracion` segundos.
    """
    colores = {
        "info": "#374151", "ok": "#16a34a",
        "error": "#dc2626", "warn": "#ca8a04",
    }
    icono = {
        "info": ft.Icons.INFO_OUTLINE,
        "ok": ft.Icons.CHECK_CIRCLE,
        "error": ft.Icons.ERROR_OUTLINE,
        "warn": ft.Icons.WARNING_AMBER,
    }.get(tipo, ft.Icons.INFO_OUTLINE)

    contenido = ft.Container(
        content=ft.Row([
            ft.Icon(icono, color="white", size=20),
            ft.Text(texto, color="white", size=13,
                    max_lines=2, overflow=ft.TextOverflow.ELLIPSIS,
                    expand=True),
        ], spacing=10,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=colores.get(tipo, "#374151"),
        padding=ft.Padding.symmetric(horizontal=16, vertical=12),
        border_radius=12,
        shadow=ft.BoxShadow(
            blur_radius=12, spread_radius=0,
            color="#00000088",
            offset=ft.Offset(0, 3)),
    )

    overlay = ft.Container(
        content=contenido,
        top=60, left=14, right=14,
    )

    async def _show_and_hide():
        import asyncio
        try:
            page.overlay.append(overlay)
            page.update()
        except Exception:
            return
        try:
            await asyncio.sleep(duracion)
        except Exception:
            pass
        try:
            if overlay in page.overlay:
                page.overlay.remove(overlay)
            page.update()
        except Exception:
            pass

    try:
        page.run_task(_show_and_hide)
    except Exception:
        pass


def cerrar_dialogo(page, control=None, on_close=None):
    """
    Cierra el diálogo/BottomSheet de arriba.
    Si on_close existe, se ejecuta DIFERIDO (150ms) para que el pop
    se aplique antes de abrir otro diálogo.
    """
    try:
        page.pop_dialog()
    except Exception:
        pass
    try:
        page.update()
    except Exception:
        pass

    if on_close is None:
        return

    async def _deferred():
        import asyncio
        try:
            await asyncio.sleep(0.15)
        except Exception:
            pass
        try:
            on_close()
        except Exception as ex:
            print(f"[cerrar_dialogo] on_close error: {ex}")

    try:
        page.run_task(_deferred)
    except Exception:
        # Fallback sincrónico
        try:
            on_close()
        except Exception:
            pass


def cursor_al_final(e):
    tf = e.control
    try:
        texto = tf.value or ""
        tf.selection = ft.TextSelection(
            base_offset=len(texto), extent_offset=len(texto))
        tf.update()
    except Exception:
        pass


def mounted(ctrl) -> bool:
    try:
        _ = ctrl.page
        return True
    except Exception:
        return False


def panel_modal(contenido, width=340):
    """Envuelve contenido con estilo de diálogo."""
    return ft.Container(
        content=contenido,
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=16,
        padding=20,
        width=width,
        shadow=ft.BoxShadow(
            blur_radius=20,
            spread_radius=0,
            color="#00000099",
            offset=ft.Offset(0, 6),
        ),
        border=ft.Border.all(1, es.COLOR_BORDE),
    )


def mostrar_modal(page, contenido, on_close=None):
    """
    Muestra contenido centrado con barrier semi-transparente.
    Solo puede haber UN modal abierto a la vez: si hay otro, se cierra.
    Devuelve una función cerrar() para cerrarlo manualmente.
    """
    # Cerrar cualquier modal anterior
    actual = getattr(page, "_modal_actual", None)
    if actual is not None:
        try:
            if actual in page.overlay:
                page.overlay.remove(actual)
        except Exception:
            pass

    estado = {"cerrado": False}

    def cerrar():
        if estado["cerrado"]:
            return
        estado["cerrado"] = True
        ov = getattr(page, "_modal_actual", None)
        if ov is None:
            return
        try:
            if ov in page.overlay:
                page.overlay.remove(ov)
        except Exception:
            pass
        try:
            page._modal_actual = None
        except Exception:
            pass
        try:
            page.update()
        except Exception:
            pass
        if on_close is not None:
            # Diferido para que el pop se aplique antes de abrir otro
            async def _deferred():
                import asyncio
                try:
                    await asyncio.sleep(0.15)
                except Exception:
                    pass
                try:
                    on_close()
                except Exception as ex:
                    print(f"[mostrar_modal] on_close error: {ex}")
            try:
                page.run_task(_deferred)
            except Exception:
                try:
                    on_close()
                except Exception:
                    pass

    barrier = ft.Container(
        bgcolor="#80000000",
        expand=True,
        on_click=lambda e: cerrar(),
    )

    # Contenedor del centro: expand=True, sin on_click
    # Los clicks dentro del contenido van al contenido.
    # Los clicks fuera (en la zona oscura) van al barrier.
    centro = ft.Container(
        content=contenido,
        alignment=ft.Alignment.CENTER,
        expand=True,
    )

    overlay = ft.Stack([barrier, centro], expand=True)
    try:
        page.overlay.append(overlay)
        page._modal_actual = overlay
        page.update()
    except Exception as ex:
        print(f"[mostrar_modal] error al abrir: {ex}")

    return cerrar


async def _copiar_async(page, texto) -> bool:
    """Copia texto al portapapeles probando los dos APIs de Flet."""
    # API nuevo (Flet >= 0.27): page.clipboard.set() async
    try:
        clipboard = getattr(page, "clipboard", None)
        if clipboard is None:
            clipboard = ft.Clipboard()
            page.services.append(clipboard)
            page.update()
        await clipboard.set(texto)
        return True
    except Exception:
        pass

    # API antiguo (por si acaso)
    try:
        page.set_clipboard(texto)
        return True
    except Exception:
        pass

    return False


def copiar_portapapeles(page, texto, app=None):
    """
    Copia al portapapeles usando la API disponible.
    Si nada funciona, muestra un diálogo con el texto seleccionable.
    """
    async def _run():
        ok = await _copiar_async(page, texto)
        if ok:
            try:
                toast(page, "Copiado al portapapeles", "ok")
            except Exception:
                pass
        else:
            _mostrar_texto_para_copiar(page, texto)

    try:
        page.run_task(_run)
    except Exception:
        _mostrar_texto_para_copiar(page, texto)


def _mostrar_texto_para_copiar(page, texto):
    """Fallback: muestra el texto en un diálogo seleccionable."""
    try:
        page.show_dialog(ft.AlertDialog(
            title=ft.Text("Copia manualmente"),
            content=ft.Column([
                ft.Text(
                    "No se pudo copiar automáticamente. "
                    "Mantén pulsado el texto para seleccionarlo:",
                    size=12, color=es.COLOR_TEXTO_SUAVE),
                ft.Container(height=8),
                ft.Container(
                    content=ft.Text(texto, size=11,
                                    color=es.COLOR_TEXTO,
                                    selectable=True,
                                    font_family="monospace"),
                    padding=10,
                    bgcolor=es.COLOR_SUPERFICIE_2,
                    border_radius=8,
                    height=300,
                ),
            ], tight=True, width=400, spacing=4,
                scroll=ft.ScrollMode.AUTO),
            actions=[
                ft.FilledButton(
                    "Cerrar",
                    on_click=lambda e: page.pop_dialog(),
                    style=es.estilo_boton_marca()),
            ],
            actions_alignment=ft.MainAxisAlignment.END,
        ))
    except Exception:
        pass


def panel_sugerencias(on_pick, alto_max=200):
    """
    Devuelve (panel, ocultar, rebuild) para usar debajo de un TextField.
      - panel: ft.Column que se muestra/oculta.
      - ocultar(): limpia y oculta el panel.
      - rebuild(items): llena con items (dicts con nombre, codigo, _uso).
    """
    panel = ft.Column(spacing=0, tight=True)
    panel.visible = False

    def ocultar():
        panel.controls.clear()
        panel.visible = False
        try:
            panel.update()
        except Exception:
            pass

    def rebuild(items):
        panel.controls.clear()
        if not items:
            panel.visible = False
            try:
                panel.update()
            except Exception:
                pass
            return
        for it in items:
            panel.controls.append(_fila_sugerencia(it, on_pick, ocultar))
        panel.visible = True
        try:
            panel.update()
        except Exception:
            pass

    return panel, ocultar, rebuild


def _fila_sugerencia(item, on_pick, ocultar):
    def click(e):
        on_pick(item)
        ocultar()

    nombre = item.get("nombre") or ""
    codigo = item.get("codigo") or ""
    uso = item.get("_uso")
    sub = codigo
    if uso is not None:
        sub = f"{codigo}  ·  {uso} mov." if codigo else f"{uso} mov."
    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.SEARCH, size=16,
                    color=es.COLOR_ACENTO),
            ft.Column([
                ft.Text(nombre, size=13,
                        color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(sub, size=10,
                        color=es.COLOR_TEXTO_SUAVE,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
            ], spacing=1, expand=True),
        ], spacing=8,
            vertical_alignment=ft.CrossAxisAlignment.CENTER),
        padding=ft.Padding.symmetric(horizontal=10, vertical=8),
        on_click=click,
        ink=True,
    )