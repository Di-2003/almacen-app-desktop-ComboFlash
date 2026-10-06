import flet as ft
from ui import estilos as es
import os
from pathlib import Path


# ============================================================
# Rutas de assets
# ============================================================

def ruta_asset(nombre: str) -> str:
    base = os.environ.get("FLET_ASSETS_DIR")
    if base:
        return str(Path(base) / nombre)
    return f"recursos/{nombre}"


def imagen_opcional(nombre: str, fallback: ft.Control,
                    width=None, height=None,
                    fit=ft.BoxFit.CONTAIN) -> ft.Control:
    ruta = ruta_asset(nombre)
    try:
        if Path(ruta).exists():
            return ft.Image(src=ruta, fit=fit,
                            width=width, height=height)
    except Exception:
        pass
    return fallback


# ============================================================
# Chips y badges (solo puntos de color, sin texto)
# ============================================================

def chip_estado(color: str) -> ft.Container:
    """Círculo de color según estado. Sin texto."""
    return ft.Container(
        width=14, height=14,
        bgcolor=es.COLOR_ESTADO_TEXTO[color],
        border_radius=7,
        border=ft.Border.all(1, es.COLOR_ESTADO_BORDE[color]),
    )


def chip_inactivo() -> ft.Container:
    """Círculo gris para productos inactivos."""
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


# ============================================================
# Tarjetas
# ============================================================

def tarjeta_metrica(titulo, valor, subtitulo="",
                    color=None, on_tap=None):
    color = color or es.COLOR_ACENTO
    contenido = ft.Column(
        [
            ft.Row(
                [
                    ft.Container(width=8, height=8, bgcolor=color,
                                 border_radius=4),
                    ft.Text(titulo, size=11, color=es.COLOR_TEXTO_SUAVE,
                            weight=ft.FontWeight.W_600),
                ],
                spacing=6, tight=True,
            ),
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
    pc = float(prod.get("precio_costo", 0) or 0)
    pv = float(prod.get("precio_unitario", 0) or 0)
    stock_txt = inv.fmt_cantidad(prod["stock"])
    codigo = (prod.get("codigo") or "").strip()
    esta_activo = prod.get("activo", 1) == 1

    cabecera = ft.Row(
        [
            ft.Text(
                prod["nombre"],
                size=15,
                weight=ft.FontWeight.W_600,
                color=es.COLOR_TEXTO,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS,
                expand=True,
            ),
            badge(codigo, es.COLOR_ACENTO) if codigo
            else ft.Container(width=1),
        ],
        spacing=8,
        vertical_alignment=ft.CrossAxisAlignment.START,
    )

    def _dato(label, valor):
        return ft.Column(
            [
                ft.Text(label, size=10, color=es.COLOR_TEXTO_TENUE),
                ft.Text(valor, size=13, color=es.COLOR_TEXTO,
                        weight=ft.FontWeight.W_600),
            ],
            spacing=2,
        )

    fila_datos = ft.Row(
        [
            ft.Container(content=_dato("Stock", stock_txt),
                        expand=True),
            ft.Container(
                content=_dato("Costo", f"${inv.fmt_precio(pc)}"),
                expand=True),
            ft.Container(
                content=_dato("Venta", f"${inv.fmt_precio(pv)}"),
                expand=True),
        ],
        spacing=0,
    )

    chip_estado_ctrl = (chip_estado(color) if esta_activo
                        else chip_inactivo())

    return ft.Container(
        content=ft.Column(
            [
                ft.Row([
                    ft.Container(cabecera, expand=True),
                    chip_estado_ctrl,
                ], spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.START),
                ft.Container(height=8),
                fila_datos,
            ],
            spacing=0,
        ),
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
        "info":  (es.COLOR_INFO_SUAVE, es.COLOR_INFO),
        "ok":    (es.COLOR_EXITO_SUAVE, es.COLOR_EXITO),
        "warn":  (es.COLOR_AMBAR_SUAVE, es.COLOR_AMBAR),
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
        value=valor,
        hint_text=hint,
        border=es.borde_textfield_none(),
        filled=False,
        bgcolor="transparent",
        content_padding=ft.Padding.symmetric(horizontal=0, vertical=12),
        on_change=on_change,
        expand=True,
        text_size=14,
    )
    cont = ft.Container(
        content=ft.Row(
            [
                ft.Icon(ft.Icons.SEARCH,
                        color=es.COLOR_TEXTO_TENUE, size=20),
                tf,
            ],
            spacing=6,
            vertical_alignment=ft.CrossAxisAlignment.CENTER,
        ),
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
        content=ft.Column(
            [
                ft.Container(
                    content=ft.Icon(icono, size=36,
                                    color=es.COLOR_ACENTO),
                    bgcolor=es.COLOR_ACENTO_SUAVE,
                    padding=18,
                    border_radius=100,
                ),
                ft.Container(height=10),
                ft.Text(titulo, size=15,
                        weight=ft.FontWeight.W_600,
                        color=es.COLOR_TEXTO,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=2,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(subtitulo, size=12,
                        color=es.COLOR_TEXTO_SUAVE,
                        text_align=ft.TextAlign.CENTER,
                        max_lines=3,
                        overflow=ft.TextOverflow.ELLIPSIS)
                if subtitulo else ft.Container(height=1),
            ],
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
            tight=True,
        ),
        padding=24,
        alignment=ft.Alignment.CENTER,
    )


# ============================================================
# Bottom sheet
# ============================================================

def bottom_sheet(content: ft.Control,
                page: ft.Page | None = None,
                alto_max_pct: float = 0.85) -> ft.BottomSheet:
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

    col = ft.Column(
        [
            ft.Row(
                [ft.Container(width=40, height=4,
                              bgcolor=es.COLOR_BORDE_FUERTE,
                              border_radius=2)],
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            ft.Container(height=8),
            ft.Container(content=content, expand=True),
        ],
        tight=True,
        spacing=0,
        scroll=ft.ScrollMode.AUTO,
    )

    cont = ft.Container(
        content=col,
        padding=ft.Padding.only(left=16, top=10, right=16, bottom=20),
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=ft.BorderRadius.only(top_left=20, top_right=20),
    )
    if alto:
        cont.height = alto

    return ft.BottomSheet(content=cont)


# ============================================================
# Snack flotante
# ============================================================

def snack(page, texto, tipo="info"):
    colores = {
        "info":  "#374151",
        "ok":    "#16a34a",
        "error": "#dc2626",
        "warn":  "#ca8a04",
    }

    snack_bar = ft.SnackBar(
        content=ft.Text(texto, color="white", size=13),
        bgcolor=colores.get(tipo, "#374151"),
        duration=15000,
        behavior=ft.SnackBarBehavior.FLOATING,
        show_close_icon=True,
        close_icon_color="white",
    )

    try:
        page.open(snack_bar)
    except Exception:
        try:
            page.show_dialog(snack_bar)
        except Exception:
            pass


# ============================================================
# Cerrar diálogo + refrescar (SIN colgar)
# ============================================================
#
# Problema: cuando llamas a app.refrescar() inmediatamente después
# de cerrar un diálogo, Flet no alcanza a procesar el cierre y la
# ventana se queda colgada.
#
# Solución: cerrar el diálogo primero, hacer page.update(), y
# luego ejecutar el callback en un task diferido.
# ============================================================

def cerrar_dialogo(page, control=None, on_close=None):
    """
    Cierra un diálogo/bottom sheet.

    - `control`: el diálogo a cerrar (opcional, se refuerza el cierre).
    - `on_close`: callback opcional que se ejecuta DESPUÉS del cierre,
      en un task diferido. Ideal para `app.refrescar`.
    """
    # 1. Marcar como cerrado
    if control is not None:
        try:
            control.open = False
        except Exception:
            pass

    # 2. Intentar page.pop_dialog
    try:
        page.pop_dialog()
    except Exception:
        pass

    # 3. Intentar page.close (por si existe)
    if control is not None:
        try:
            page.close(control)
        except Exception:
            pass

    # 4. Forzar update
    try:
        page.update()
    except Exception:
        pass

    # 5. Ejecutar callback en task diferido (evita el cuelgue)
    if on_close is not None:
        async def _deferred():
            import asyncio
            try:
                await asyncio.sleep(0.08)
            except Exception:
                pass
            try:
                on_close()
            except Exception:
                pass

        try:
            page.run_task(_deferred)
        except Exception:
            # Fallback si run_task no está disponible
            try:
                on_close()
            except Exception:
                pass


def cursor_al_final(e):
    tf = e.control
    try:
        texto = tf.value or ""
        tf.selection = ft.TextSelection(
            base_offset=len(texto),
            extent_offset=len(texto),
        )
        tf.update()
    except Exception:
        pass


def mounted(ctrl) -> bool:
    try:
        _ = ctrl.page
        return True
    except Exception:
        return False