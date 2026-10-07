"""
Dashboard con métricas de período (calendario) y estado actual.
Todas las tarjetas de stock son tocables: llevan a /lista-productos.
"""
from datetime import datetime
import flet as ft
from db import get_conn, GENERAL_ID
import inventario as inv
import locales as loc
import categorias as cats
import metricas as met
from ui import estilos as es
from ui.componentes import tarjeta_metrica, empty_state
from ui.principal import barra_navegacion, _chip_local


def _seccion(titulo):
    return ft.Row([
        ft.Container(width=4, height=18, bgcolor=es.COLOR_ACENTO,
                     border_radius=2),
        ft.Text(titulo, size=14, weight=ft.FontWeight.BOLD,
                color=es.COLOR_TEXTO),
    ], spacing=8)


def _card(control):
    return ft.Container(
        content=control, padding=16,
        bgcolor=es.COLOR_SUPERFICIE,
        border=ft.Border.all(1, es.COLOR_BORDE),
        border_radius=16,
    )


def _usd(cup):
    tasa = inv.get_tasa_usd()
    return (cup / tasa) if tasa > 0 else 0.0


def vista_dashboard(app):
    periodo = getattr(app, "periodo_dashboard", "mes")
    m = met.resumen_periodo(app.local_id, periodo)

    ingresado = m["ingresado"]
    vendido = m["vendido"]
    ganancia = m["ganancia"]
    pct_gan = m["pct_ganancia"]
    entradas = {"n": m["n_entradas"], "cantidad": m["cant_entradas"]}
    ventas = {"n": m["n_ventas"], "cantidad": m["cant_ventas"]}

    # ─── Estado del inventario (hoy) ───
    t = inv.totales_local(app.local_id)
    invertido = t["invertido"]
    venta_pot = t["venta_total"]
    margen_pot = t["diferencia"]
    pct_pot = (margen_pot / invertido * 100) if invertido > 0 else 0.0

    # ─── Stock stats ───
    sp = _stats_productos(app.local_id)
    n_inactivos = len(inv.listar_productos_inactivos(app.local_id))

    # ─── Productos por categoría ───
    por_cat = cats.contar_productos_por_categoria(app.local_id)
    cats_activas = cats.listar_categorias(solo_activas=True)
    sin_cat = por_cat.get(None, 0)

    # ═══════════ CHIPS DE PERÍODO ═══════════
    def chip_periodo(texto, valor):
        activo = (periodo == valor)

        def _click(e):
            app.periodo_dashboard = valor
            app.refrescar()

        return ft.Container(
            content=ft.Text(texto, size=12,
                            color=(es.COLOR_MARCA_NEGRO if activo
                                   else es.COLOR_TEXTO_SUAVE),
                            weight=ft.FontWeight.BOLD),
            bgcolor=(es.COLOR_ACENTO if activo else es.COLOR_SUPERFICIE),
            border=ft.Border.all(1,
                                 es.COLOR_ACENTO if activo
                                 else es.COLOR_BORDE),
            padding=ft.Padding.symmetric(horizontal=14, vertical=8),
            border_radius=20,
            on_click=_click,
            ink=True,
        )

    chips = ft.Row([
        chip_periodo("Hoy", "hoy"),
        chip_periodo("Semana", "semana"),
        chip_periodo("Mes", "mes"),
        chip_periodo("Año", "anio"),
        chip_periodo("Total", "total"),
    ], spacing=6, scroll=ft.ScrollMode.AUTO)

    # ═══════════ SECCIÓN ACTIVIDAD ═══════════
    def card_dinero(titulo, valor_cup, color):
        return ft.Container(
            content=tarjeta_metrica(
                titulo, f"${valor_cup:,.2f}",
                f"≈ USD$ {_usd(valor_cup):,.2f}",
                color=color),
            expand=True)

    color_pct = (es.COLOR_VERDE if pct_gan >= 30
                 else es.COLOR_AMARILLO if pct_gan >= 15
                 else es.COLOR_ROJO)
    color_pct_pot = (es.COLOR_VERDE if pct_pot >= 30
                     else es.COLOR_AMARILLO if pct_pot >= 15
                     else es.COLOR_ROJO)

    act1 = ft.Row([
        card_dinero("Ingresado", ingresado, es.COLOR_INFO),
        card_dinero("Vendido", vendido, es.COLOR_EXITO),
    ], spacing=10)
    act2 = ft.Row([
        card_dinero("Ganancia", ganancia, es.COLOR_ACENTO),
        ft.Container(content=tarjeta_metrica(
            "% Ganancia", f"{pct_gan:.1f}%",
            "≥30% OK · 15-30% revisar",
            color=color_pct), expand=True),
    ], spacing=10)
    act3 = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "Entradas", str(entradas["n"]),
            f"{inv.fmt_cantidad(entradas['cantidad'])} u",
            color=es.COLOR_INFO), expand=True),
        ft.Container(content=tarjeta_metrica(
            "Ventas", str(ventas["n"]),
            f"{inv.fmt_cantidad(ventas['cantidad'])} u",
            color=es.COLOR_EXITO), expand=True),
    ], spacing=10)

    # ═══════════ SECCIÓN ESTADO ACTUAL ═══════════
    est1 = ft.Row([
        card_dinero("Invertido", invertido, es.COLOR_TEXTO_SUAVE),
        card_dinero("Venta potencial", venta_pot, es.COLOR_ACENTO),
    ], spacing=10)
    est2 = ft.Row([
        card_dinero("Margen potencial", margen_pot, es.COLOR_ACENTO),
        ft.Container(content=tarjeta_metrica(
            "% potencial", f"{pct_pot:.1f}%",
            "sobre invertido",
            color=color_pct_pot), expand=True),
    ], spacing=10)

    # ═══════════ SECCIÓN STOCK (TOCABLES) ═══════════
    def card_stock(titulo, valor, color, filtro):
        def _tocar(e):
            app.abrir_lista(filtro, titulo)
        return ft.Container(
            content=ft.Column([
                ft.Text(titulo, size=11, color=color,
                        weight=ft.FontWeight.BOLD,
                        text_align=ft.TextAlign.CENTER),
                ft.Text(str(valor), size=20,
                        weight=ft.FontWeight.BOLD,
                        color=es.COLOR_TEXTO,
                        text_align=ft.TextAlign.CENTER),
            ], spacing=2,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(vertical=12),
            bgcolor=es.COLOR_SUPERFICIE,
            border=ft.Border.all(1, color),
            border_radius=12,
            on_click=_tocar,
            ink=True,
            expand=True,
        )

    stock_row1 = ft.Row([
        card_stock("Verde", sp["verde"], es.COLOR_VERDE, "verde"),
        card_stock("Amarillo", sp["amarillo"], es.COLOR_AMARILLO, "amarillo"),
        card_stock("Crítico", sp["rojo"], es.COLOR_ROJO, "critico"),
    ], spacing=8)
    stock_row2 = ft.Row([
        card_stock("Stock 0", sp["stock_cero"], es.COLOR_TEXTO_TENUE,
                   "stock0"),
        card_stock("Inactivos", n_inactivos, es.COLOR_TEXTO_SUAVE,
                   "inactivos"),
    ], spacing=8)

    # ═══════════ SECCIÓN POR TIPO ═══════════
    def card_categoria(nombre, n, cat_id, color=es.COLOR_ACENTO):
        def _tocar(e):
            if cat_id is None:
                app.filtro_tipo = None
            else:
                app.filtro_tipo = cat_id
            app.ir("/principal")
        return ft.Container(
            content=ft.Row([
                ft.Container(width=4, height=30, bgcolor=color,
                             border_radius=2),
                ft.Text(nombre, size=13, color=es.COLOR_TEXTO,
                        expand=True),
                ft.Container(
                    content=ft.Text(str(n), size=12,
                                    color=es.COLOR_MARCA_NEGRO,
                                    weight=ft.FontWeight.BOLD),
                    bgcolor=es.COLOR_ACENTO,
                    padding=ft.Padding.symmetric(horizontal=10,
                                                 vertical=4),
                    border_radius=12),
            ], spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER),
            padding=ft.Padding.symmetric(horizontal=12, vertical=10),
            bgcolor=es.COLOR_SUPERFICIE_2,
            border_radius=10,
            on_click=_tocar,
            ink=True,
        )

    cat_cards = []
    for c in cats_activas:
        n = por_cat.get(c["id"], 0)
        cat_cards.append(card_categoria(c["nombre"], n, c["id"]))
    if sin_cat > 0:
        cat_cards.append(card_categoria("Sin categoría", sin_cat, None,
                                         es.COLOR_TEXTO_TENUE))

    if cat_cards:
        contenido_cat = ft.Column(cat_cards, spacing=8)
    else:
        contenido_cat = empty_state(
            ft.Icons.CATEGORY_OUTLINED, "Sin tipos",
            "Crea tipos desde el menú lateral.")

    contenido = ft.Container(
        content=ft.Column(controls=[
            _seccion("Período"),
            chips,
            ft.Container(height=12),
            _seccion("Actividad del período"),
            act1, act2, act3,
            ft.Container(height=12),
            _seccion("Estado del inventario (hoy)"),
            est1, est2,
            ft.Container(height=12),
            _seccion("Stock (tocables)"),
            stock_row1, stock_row2,
            ft.Container(height=12),
            _seccion("Por tipo de producto"),
            _card(contenido_cat),
            ft.Container(height=30),
        ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
        padding=ft.Padding.all(14),
        expand=True,
    )

    return ft.View(
        route="/dashboard",
        controls=[contenido],
        appbar=ft.AppBar(
            title=ft.Row([_chip_local(app)], spacing=8),
            bgcolor=es.COLOR_SUPERFICIE, elevation=0),
        navigation_bar=barra_navegacion(app, 1),
        bgcolor=es.COLOR_FONDO,
    )


def _stats_productos(local_id):
    prods = inv.listar_productos(local_id, solo_activos=True)
    total = len(prods)
    sc = v = a = r = 0
    for p in prods:
        s = float(p["stock"] or 0)
        if s == 0:
            sc += 1
        c = inv.color_de_producto(p)
        if c == "verde":
            v += 1
        elif c == "amarillo":
            a += 1
        else:
            r += 1
    return {"total": total, "stock_cero": sc,
            "verde": v, "amarillo": a, "rojo": r}