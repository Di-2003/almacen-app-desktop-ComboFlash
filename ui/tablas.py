"""
Tablas del dashboard — versión final compatible con
flet-datatable2 1.0.4.

API verificada:
- DataTable2: heading_row_color, heading_row_height,
              data_row_height, column_spacing, divider_thickness,
              horizontal_lines, border_radius, ...
- DataColumn2: label, numeric, size (S/M/L), fixed_width
- DataRow2: cells, on_select_change, on_tap, specific_row_height
"""
import flet as ft
import flet_datatable2 as fdt
from ui import estilos as es
from ui.componentes import empty_state


def _sin_datos(texto: str) -> ft.Container:
    """Estado vacío en tono neutro (sin rojo de marca)."""
    return ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.TABLE_CHART_OUTLINED, size=32,
                    color=es.COLOR_TEXTO_TENUE),
            ft.Container(height=6),
            ft.Text("Sin filas", size=13,
                    color=es.COLOR_TEXTO_SUAVE,
                    weight=ft.FontWeight.W_600,
                    text_align=ft.TextAlign.CENTER),
            ft.Text(texto, size=11,
                    color=es.COLOR_TEXTO_TENUE,
                    text_align=ft.TextAlign.CENTER,
                    max_lines=3,
                    overflow=ft.TextOverflow.ELLIPSIS),
        ], spacing=2,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        alignment=ft.Alignment.CENTER,
        padding=20,
    )


def _cell(texto: str, size: int = 12, color: str = None,
          bold: bool = False) -> ft.DataCell:
    return ft.DataCell(
        ft.Text(texto, size=size,
                color=color or es.COLOR_TEXTO,
                weight=ft.FontWeight.BOLD if bold
                else ft.FontWeight.NORMAL,
                max_lines=2,
                overflow=ft.TextOverflow.ELLIPSIS),
    )


# ═══════════════════════════════════════════════════════════
# 1. TABLA — Stock crítico
# ═══════════════════════════════════════════════════════════

def tabla_stock_critico(app, productos: list[dict]) -> ft.Control:
    if not productos:
        return _sin_datos(
            "¡Genial! Ningún producto está en nivel crítico.")

    filas = []
    for p in productos:
        filas.append(
            fdt.DataRow2(
                cells=[
                    _cell(p["nombre"], bold=True),
                    _cell(p.get("codigo") or "—", size=11,
                          color=es.COLOR_ACENTO),
                    _cell(f"{float(p['stock']):g}",
                          color=es.COLOR_PELIGRO, bold=True),
                    _cell(f"${float(p['precio_unitario']):,.2f}"),
                ],
                on_tap=lambda e, filtro="critico":
                    app.abrir_lista(filtro, "Stock crítico"),
            )
        )

    return fdt.DataTable2(
        columns=[
            fdt.DataColumn2(
                label=ft.Text("Producto", size=11,
                              weight=ft.FontWeight.BOLD),
                size=fdt.DataColumnSize.L,
            ),
            fdt.DataColumn2(
                label=ft.Text("Código", size=11,
                              weight=ft.FontWeight.BOLD),
                size=fdt.DataColumnSize.S,
            ),
            fdt.DataColumn2(
                label=ft.Text("Stock", size=11,
                              weight=ft.FontWeight.BOLD),
                numeric=True,
                size=fdt.DataColumnSize.S,
            ),
            fdt.DataColumn2(
                label=ft.Text("Precio", size=11,
                              weight=ft.FontWeight.BOLD),
                numeric=True,
                size=fdt.DataColumnSize.M,
            ),
        ],
        rows=filas,
        heading_row_color=es.COLOR_PELIGRO_SUAVE,
        heading_row_height=38,
        data_row_height=48,
        column_spacing=14,
        divider_thickness=0.5,
        horizontal_lines=ft.BorderSide(0.5, es.COLOR_BORDE),
        border_radius=10,
        show_bottom_border=True,
        expand=True,
    )


# ═══════════════════════════════════════════════════════════
# 2. TABLA — Productos estancados
# ═══════════════════════════════════════════════════════════

def tabla_estancados(app, productos: list[dict],
                     dias: int = 30) -> ft.Control:
    if not productos:
        return _sin_datos(
            f"Todos los productos con stock han vendido "
            f"en los últimos {dias} días.")

    filas = []
    for p in productos:
        stock = float(p["stock"] or 0)
        costo = float(p["precio_costo"] or 0)
        inmovilizado = stock * costo

        filas.append(
            fdt.DataRow2(
                cells=[
                    _cell(p["nombre"], bold=True),
                    _cell(p.get("codigo") or "—", size=11,
                          color=es.COLOR_ACENTO),
                    _cell(f"{stock:g}"),
                    _cell(f"${inmovilizado:,.2f}",
                          color=es.COLOR_AMBAR, bold=True),
                ],
            )
        )

    return fdt.DataTable2(
        columns=[
            fdt.DataColumn2(
                label=ft.Text("Producto", size=11,
                              weight=ft.FontWeight.BOLD),
                size=fdt.DataColumnSize.L,
            ),
            fdt.DataColumn2(
                label=ft.Text("Código", size=11,
                              weight=ft.FontWeight.BOLD),
                size=fdt.DataColumnSize.S,
            ),
            fdt.DataColumn2(
                label=ft.Text("Stock", size=11,
                              weight=ft.FontWeight.BOLD),
                numeric=True,
                size=fdt.DataColumnSize.S,
            ),
            fdt.DataColumn2(
                label=ft.Text("Invertido", size=11,
                              weight=ft.FontWeight.BOLD),
                numeric=True,
                size=fdt.DataColumnSize.M,
            ),
        ],
        rows=filas,
        heading_row_color=es.COLOR_AMBAR_SUAVE,
        heading_row_height=38,
        data_row_height=48,
        column_spacing=14,
        divider_thickness=0.5,
        horizontal_lines=ft.BorderSide(0.5, es.COLOR_BORDE),
        border_radius=10,
        show_bottom_border=True,
        expand=True,
    )
    
