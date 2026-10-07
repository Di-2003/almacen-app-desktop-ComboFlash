"""
Dashboard con métricas del local. Incluye margen en CUP y USD.
"""
from datetime import datetime, timedelta
import flet as ft
from db import get_conn, GENERAL_ID
import inventario as inv
import locales as loc
from ui import estilos as es
from ui.componentes import tarjeta_metrica, empty_state, mounted
from ui.principal import barra_navegacion


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


def vista_dashboard(app):
    sp = _stats_productos(app.local_id)
    t = inv.totales_local(app.local_id)
    sm = _stats_movimientos(app.local_id)
    tc = inv.totales_por_concepto(app.local_id)
    top = _top_productos(app.local_id)
    ultimos = _ultimos_movimientos(app.local_id, 8)

    def abrir_lista(filtro):
        def _hacer(e):
            _abrir_lista_productos(app, filtro)
        return _hacer

    grid1 = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "Activos", str(sp["total"]), f"{sp['stock_cero']} sin stock",
            color=es.COLOR_TEXTO_SUAVE,
            on_tap=abrir_lista("todos")), expand=True),
        ft.Container(content=tarjeta_metrica(
            "Stock 0", str(sp["stock_cero"]), "reponer",
            color=es.COLOR_TEXTO_TENUE,
            on_tap=abrir_lista("stock_cero")), expand=True),
    ], spacing=10)
    grid2 = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "En verde", str(sp["verde"]), "saludables",
            color=es.COLOR_VERDE,
            on_tap=abrir_lista("verde")), expand=True),
        ft.Container(content=tarjeta_metrica(
            "Amarillo", str(sp["amarillo"]), "por revisar",
            color=es.COLOR_AMARILLO,
            on_tap=abrir_lista("amarillo")), expand=True),
    ], spacing=10)
    grid3 = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "Crítico", str(sp["rojo"]), "requiere acción",
            color=es.COLOR_ROJO,
            on_tap=abrir_lista("rojo")), expand=True),
    ], spacing=10)

    invertido = t["invertido"]
    venta = t["venta_total"]
    margen = t["diferencia"]
    pct = (margen / invertido * 100) if invertido > 0 else 0.0
    acento_pct = (es.COLOR_VERDE if pct >= 30
                  else es.COLOR_AMARILLO if pct >= 15
                  else es.COLOR_ROJO)

    # Conversión a USD usando la tasa actual
    tasa_usd = inv.get_tasa_usd()
    def usd(cup):
        return (cup / tasa_usd) if tasa_usd > 0 else 0.0

    dinero = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "Invertido", f"${invertido:,.2f}",
            f"≈ USD$ {usd(invertido):,.2f}",
            color=es.COLOR_TEXTO_SUAVE), expand=True),
        ft.Container(content=tarjeta_metrica(
            "Venta", f"${venta:,.2f}",
            f"≈ USD$ {usd(venta):,.2f}",
            color=es.COLOR_ACENTO), expand=True),
    ], spacing=10)
    dinero2 = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "Margen", f"${margen:,.2f}",
            f"≈ USD$ {usd(margen):,.2f}",
            color=es.COLOR_ACENTO), expand=True),
        ft.Container(content=tarjeta_metrica(
            "% Ganancia", f"{pct:.1f}%",
            "≥30% OK · 15-30% revisar",
            color=acento_pct), expand=True),
    ], spacing=10)

    act = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "Hoy", str(sm["hoy"]), "movs",
            color=es.COLOR_ACENTO), expand=True),
        ft.Container(content=tarjeta_metrica(
            "7 días", str(sm["semana"]), "movs",
            color=es.COLOR_ACENTO), expand=True),
    ], spacing=10)
    act2 = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "30 días", str(sm["mes"]), "movs",
            color=es.COLOR_ACENTO), expand=True),
        ft.Container(content=tarjeta_metrica(
            "Total", str(sm["total"]), "movs",
            color=es.COLOR_ACENTO), expand=True),
    ], spacing=10)

    conc1 = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "Ventas", str(tc["ventas"]["n"]),
            f"${tc['ventas']['monto']:,.2f} · "
            f"≈ USD$ {usd(tc['ventas']['monto']):,.2f}",
            color=es.COLOR_EXITO), expand=True),
        ft.Container(content=tarjeta_metrica(
            "Entradas", str(tc["entradas"]["n"]),
            f"{inv.fmt_cantidad(tc['entradas']['cantidad'])} u",
            color=es.COLOR_INFO), expand=True),
    ], spacing=10)
    conc2 = ft.Row([
        ft.Container(content=tarjeta_metrica(
            "Otras salidas", str(tc["otras_salidas"]["n"]),
            f"{inv.fmt_cantidad(tc['otras_salidas']['cantidad'])} u",
            color=es.COLOR_AMBAR), expand=True),
        ft.Container(content=tarjeta_metrica(
            "Bajas", str(tc["bajas"]["n"]),
            f"{inv.fmt_cantidad(tc['bajas']['cantidad'])} u",
            color=es.COLOR_PELIGRO), expand=True),
    ], spacing=10)

    if top:
        medallas = ["🥇", "🥈", "🥉", "4.", "5."]
        max_m = max(d["n"] for d in top) or 1
        filas = []
        for i, d in enumerate(top):
            frac = d["n"] / max_m
            filas.append(ft.Column([
                ft.Row([
                    ft.Text(medallas[i] if i < 3 else f"{i+1}.", size=14),
                    ft.Text(d["producto"], size=13, expand=True,
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            color=es.COLOR_TEXTO),
                    ft.Text(str(d["n"]), size=13,
                            weight=ft.FontWeight.BOLD,
                            color=es.COLOR_ACENTO),
                ], spacing=8),
                ft.Container(
                    content=ft.Container(
                        width=int(frac * 260), height=4,
                        bgcolor=es.COLOR_ACENTO, border_radius=2),
                    bgcolor=es.COLOR_ACENTO_SUAVE,
                    border_radius=2, height=4),
            ], spacing=6))
        contenido_top = ft.Column(filas, spacing=12)
    else:
        contenido_top = empty_state(ft.Icons.BAR_CHART, "Sin datos",
                                     "Sin movimientos en 30 días.")

    if ultimos:
        filas_ult = []
        for d in ultimos:
            c, ic = _color_tipo(d["tipo"])
            filas_ult.append(ft.Container(
                content=ft.Row([
                    ft.Container(
                        content=ft.Icon(ic, color="white", size=16),
                        bgcolor=c, padding=8, border_radius=10),
                    ft.Column([
                        ft.Text(d["producto"], size=13,
                                weight=ft.FontWeight.W_600,
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                                color=es.COLOR_TEXTO),
                        ft.Text(f"{d['fecha'][:10]}  ·  {d['tipo']}",
                                size=11, color=es.COLOR_TEXTO_SUAVE),
                    ], spacing=1, expand=True),
                    ft.Text(inv.fmt_cantidad(d["cantidad"]),
                            size=13, weight=ft.FontWeight.BOLD,
                            color=es.COLOR_TEXTO),
                ], spacing=10,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER),
                padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=10))
        contenido_ult = ft.Column(filas_ult, spacing=8)
    else:
        contenido_ult = empty_state(ft.Icons.HISTORY, "Sin movimientos",
                                     "Los movimientos aparecerán aquí.")

    contenido = ft.Container(
        content=ft.Column(controls=[
            _seccion("Estado del inventario"),
            grid1, grid2, grid3,
            ft.Container(height=12),
            _seccion("Dinero"),
            dinero, dinero2,
            ft.Container(height=12),
            _seccion("Actividad"),
            act, act2,
            ft.Container(height=12),
            _seccion("Movimientos por concepto"),
            conc1, conc2,
            ft.Container(height=12),
            _seccion("Top 5 (30 días)"),
            _card(contenido_top),
            ft.Container(height=12),
            _seccion("Últimos movimientos"),
            contenido_ult,
            ft.Container(height=30),
        ], spacing=10, scroll=ft.ScrollMode.AUTO, expand=True),
        padding=ft.Padding.all(14),
        expand=True,
    )

    return ft.View(
        route="/dashboard",
        controls=[contenido],
        appbar=ft.AppBar(
            title=ft.Text(
                f"Métricas — {loc.nombre_local(app.local_id)}",
                size=15, color=es.COLOR_TEXTO),
            bgcolor=es.COLOR_SUPERFICIE, elevation=0),
        navigation_bar=barra_navegacion(app, 1),
        bgcolor=es.COLOR_FONDO,
    )


def _color_tipo(tipo):
    m = {
        "ENTRADA": (es.COLOR_EXITO, ft.Icons.ADD_CIRCLE),
        "SALIDA": (es.COLOR_PELIGRO, ft.Icons.REMOVE_CIRCLE),
        "BAJA": (es.COLOR_TEXTO_SUAVE, ft.Icons.DELETE_OUTLINE),
        "TRASPASO_SALIDA": (es.COLOR_INFO, ft.Icons.LOGOUT),
        "TRASPASO_ENTRADA": (es.COLOR_INFO, ft.Icons.LOGIN),
        "AJUSTE": (es.COLOR_AMBAR, ft.Icons.ATTACH_MONEY),
        "UMBRAL": (es.COLOR_AMBAR, ft.Icons.TUNE),
    }
    return m.get(tipo, (es.COLOR_TEXTO_SUAVE, ft.Icons.CIRCLE))


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


def _stats_movimientos(local_id):
    ahora = datetime.now()
    hoy = ahora.strftime("%Y-%m-%d 00:00:00")
    h7 = (ahora - timedelta(days=7)).strftime("%Y-%m-%d 00:00:00")
    h30 = (ahora - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
    filtro = ""
    params_base = []
    if local_id != GENERAL_ID:
        filtro = " AND local_id=?"
        params_base = [local_id]
    with get_conn() as conn:
        def c(desde=None):
            sql = ("SELECT COUNT(*) AS n FROM movimientos "
                   "WHERE tipo IN ('ENTRADA','SALIDA')")
            params = list(params_base)
            if desde:
                sql += " AND fecha >= ?"
                params.append(desde)
            sql += filtro
            return conn.execute(sql, tuple(params)).fetchone()["n"]
        return {"hoy": c(hoy), "semana": c(h7), "mes": c(h30), "total": c()}


def _top_productos(local_id):
    h30 = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d 00:00:00")
    filtro = ""
    params = [h30]
    if local_id != GENERAL_ID:
        filtro = " AND m.local_id=?"
        params.append(local_id)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT p.nombre AS producto, COUNT(*) AS n "
            "FROM movimientos m JOIN productos p ON p.id=m.producto_id "
            "WHERE m.tipo IN ('ENTRADA','SALIDA') AND m.fecha >= ?"
            + filtro +
            " GROUP BY p.id ORDER BY n DESC LIMIT 5",
            tuple(params)).fetchall()
    return [dict(r) for r in rows]


def _ultimos_movimientos(local_id, n):
    filtro = ""
    params = []
    if local_id != GENERAL_ID:
        filtro = " AND m.local_id=?"
        params.append(local_id)
    params.append(n)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT m.fecha, m.tipo, p.nombre AS producto, "
            "m.cantidad, m.motivo, m.usuario "
            "FROM movimientos m JOIN productos p ON p.id=m.producto_id "
            "WHERE m.tipo IN ('ENTRADA','SALIDA','BAJA',"
            "                 'TRASPASO_SALIDA','TRASPASO_ENTRADA')"
            + filtro +
            " ORDER BY m.fecha DESC, m.id DESC LIMIT ?",
            tuple(params)).fetchall()
    return [dict(r) for r in rows]


def _abrir_lista_productos(app, filtro):
    page = app.page
    if filtro == "todos":
        productos = inv.listar_productos(app.local_id, solo_activos=True)
        titulo = "Productos activos"
    elif filtro == "stock_cero":
        productos = inv.productos_stock_cero(app.local_id)
        titulo = "Stock 0"
    elif filtro == "verde":
        productos = inv.productos_por_color(app.local_id, "verde")
        titulo = "En verde"
    elif filtro == "amarillo":
        productos = inv.productos_por_color(app.local_id, "amarillo")
        titulo = "En amarillo"
    elif filtro == "rojo":
        productos = inv.productos_por_color(app.local_id, "rojo")
        titulo = "En crítico"
    else:
        return
    lst = ft.Column(spacing=8, scroll=ft.ScrollMode.AUTO, expand=True)
    if productos:
        for p in productos:
            mc = p.get("moneda_costo") or "CUP"
            lst.controls.append(ft.Container(
                content=ft.Column([
                    ft.Text(p["nombre"], size=14,
                            weight=ft.FontWeight.W_600,
                            color=es.COLOR_TEXTO, max_lines=2,
                            overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(height=4),
                    ft.Row([
                        ft.Text(p.get("codigo") or "—", size=11,
                                color=es.COLOR_ACENTO,
                                weight=ft.FontWeight.W_600),
                        ft.Text("·", size=11, color=es.COLOR_TEXTO_TENUE),
                        ft.Text(f"Stock {inv.fmt_cantidad(p['stock'])}",
                                size=11, color=es.COLOR_TEXTO_SUAVE),
                        ft.Text("·", size=11, color=es.COLOR_TEXTO_TENUE),
                        ft.Text(mc, size=11, color=es.COLOR_TEXTO_TENUE),
                    ], spacing=6, tight=True),
                ], spacing=0),
                padding=12, bgcolor=es.COLOR_SUPERFICIE_2,
                border_radius=10))
    else:
        lst.controls.append(empty_state(ft.Icons.INBOX_OUTLINED,
                                          "Nada por aquí",
                                          "No hay productos."))
    page.show_dialog(ft.AlertDialog(
        title=ft.Text(f"{titulo}  ({len(productos)})",
                      size=16, color=es.COLOR_TEXTO),
        content=ft.Container(content=lst, width=340, expand=True),
        actions=[ft.TextButton("Cerrar",
                                on_click=lambda e: page.pop_dialog())],
        actions_alignment=ft.MainAxisAlignment.END,
    ))