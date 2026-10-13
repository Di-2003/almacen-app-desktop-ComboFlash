"""
Gráficos del dashboard — compatible con flet-charts 1.0.4.
"""
import flet as ft
import flet_charts as fch
from ui import estilos as es


def _fmt_corto(v: float) -> str:
    v = float(v or 0)
    if abs(v) >= 1_000_000:
        return f"{v/1_000_000:.1f}M"
    if abs(v) >= 1000:
        return f"{v/1000:.1f}k"
    return f"{v:.0f}"


def _sin_datos(texto: str) -> ft.Container:
    """Estado vacío neutro para gráficos sin datos."""
    return ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.INSERT_CHART_OUTLINED, size=32,
                    color=es.COLOR_TEXTO_TENUE),
            ft.Container(height=6),
            ft.Text("Sin datos", size=13,
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
        height=200,
    )


# ═══════════════════════════════════════════════════════════
# 1. LÍNEA — Evolución de ventas
# ═══════════════════════════════════════════════════════════

def grafico_linea_ventas(datos: list[tuple[str, float]]) -> ft.Control:
    if not datos or all(t <= 0.01 for _, t in datos):
        return _sin_datos("Aún no hay ventas en el período.")

    puntos = [
        fch.LineChartDataPoint(x=i, y=total)
        for i, (_, total) in enumerate(datos)
    ]

    max_y = max((t for _, t in datos), default=100)
    max_y = 100 if max_y < 100 else max_y * 1.15

    paso = max(1, len(datos) // 6)
    etiquetas_x = [
        fch.ChartAxisLabel(
            value=i,
            label=ft.Text(dia[5:], size=9,
                          color=es.COLOR_TEXTO_TENUE),
        )
        for i, (dia, _) in enumerate(datos)
        if i % paso == 0 or i == len(datos) - 1
    ]
    etiquetas_y = [
        fch.ChartAxisLabel(
            value=max_y * i / 4,
            label=ft.Text(_fmt_corto(max_y * i / 4), size=9,
                          color=es.COLOR_TEXTO_TENUE),
        )
        for i in range(5)
    ]

    return fch.LineChart(
        data_series=[
            fch.LineChartData(
                points=puntos,
                color=es.COLOR_ACENTO,
                stroke_width=3,
                curved=True,
                rounded_stroke_cap=True,
                below_line_gradient=ft.LinearGradient(
                    begin=ft.Alignment.TOP_CENTER,
                    end=ft.Alignment.BOTTOM_CENTER,
                    colors=[
                        ft.Colors.with_opacity(0.35, es.COLOR_ACENTO),
                        ft.Colors.with_opacity(0.0, es.COLOR_ACENTO),
                    ],
                ),
                point=True,
            )
        ],
        min_x=0,
        max_x=max(1, len(datos) - 1),
        min_y=0,
        max_y=max_y,
        left_axis=fch.ChartAxis(
            title=ft.Text("CUP", size=10,
                          color=es.COLOR_TEXTO_TENUE),
            title_size=30,
            labels=etiquetas_y,
            label_size=44,
        ),
        bottom_axis=fch.ChartAxis(
            labels=etiquetas_x,
            label_size=26,
        ),
        interactive=True,
        expand=True,
        height=240,
    )


# ═══════════════════════════════════════════════════════════
# 2. PIE — Distribución por método de pago
# ═══════════════════════════════════════════════════════════

_COLORES_PIE = [
    "#16a34a", "#0284c7", "#ca8a04", "#dc2626",
    "#ff4757", "#8b5cf6", "#0891b2", "#f97316",
]


def grafico_pie_metodos(datos: list[dict]) -> ft.Control:
    if not datos:
        return _sin_datos("Aún no hay cobros en el período.")

    total_gral = sum(d["total"] for d in datos) or 1.0

    secciones = []
    leyenda = []
    for i, d in enumerate(datos):
        color = _COLORES_PIE[i % len(_COLORES_PIE)]
        pct = d["total"] / total_gral * 100
        secciones.append(
            fch.PieChartSection(
                value=d["total"],
                color=color,
                radius=52,
                title=f"{pct:.0f}%" if pct >= 8 else "",
                title_style=ft.TextStyle(
                    size=12, color="white",
                    weight=ft.FontWeight.BOLD),
            )
        )
        leyenda.append(
            ft.Row([
                ft.Container(width=10, height=10, bgcolor=color,
                             border_radius=5),
                ft.Text(d["metodo"], size=11,
                        color=es.COLOR_TEXTO, expand=True,
                        max_lines=1,
                        overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(f"${d['total']:,.0f}", size=11,
                        color=es.COLOR_TEXTO_SUAVE,
                        weight=ft.FontWeight.W_600),
            ], spacing=8)
        )

    chart = fch.PieChart(
        sections=secciones,
        sections_space=2,
        center_space_radius=42,
        expand=True,
        height=180,
    )

    return ft.Column([
        chart,
        ft.Container(height=8),
        ft.Column(leyenda, spacing=4),
    ], spacing=0, tight=True)


# ═══════════════════════════════════════════════════════════
# 3. BARRAS — Top productos
# ═══════════════════════════════════════════════════════════

def grafico_barras_top(datos: list[dict]) -> ft.Control:
    if not datos:
        return _sin_datos("Sin ventas en el período.")

    max_y = max((d["cantidad"] for d in datos), default=1)
    max_y = max_y * 1.15 if max_y > 0 else 1

    grupos = []
    etiquetas_x = []
    for i, d in enumerate(datos):
        grupos.append(
            fch.BarChartGroup(
                x=i,
                rods=[
                    fch.BarChartRod(
                        from_y=0,
                        to_y=d["cantidad"],
                        color=es.COLOR_ACENTO,
                        width=22,
                        border_radius=4,
                    )
                ],
            )
        )
        nombre_corto = (d["nombre"][:12] + "…"
                        if len(d["nombre"]) > 12 else d["nombre"])
        etiquetas_x.append(
            fch.ChartAxisLabel(
                value=i,
                label=ft.Text(nombre_corto, size=9,
                              color=es.COLOR_TEXTO_TENUE),
            )
        )

    etiquetas_y = [
        fch.ChartAxisLabel(
            value=max_y * i / 4,
            label=ft.Text(f"{max_y * i / 4:.0f}", size=9,
                          color=es.COLOR_TEXTO_TENUE),
        )
        for i in range(5)
    ]

    return fch.BarChart(
        groups=grupos,
        group_spacing=12,
        min_y=0,
        max_y=max_y,
        left_axis=fch.ChartAxis(
            # FIX: esto son UNIDADES, no CUP
            title=ft.Text("Unidades", size=10,
                          color=es.COLOR_TEXTO_TENUE),
            title_size=30,
            labels=etiquetas_y,
            label_size=36,
        ),
        bottom_axis=fch.ChartAxis(
            labels=etiquetas_x,
            label_size=60,
        ),
        interactive=True,
        expand=True,
        height=260,
    )
    
