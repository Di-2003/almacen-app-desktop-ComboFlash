"""
Generación del Excel completo (móvil, en memoria).

Hojas:
  - Una por local activo (Almacén, Centro, Vedado…): productos + totales.
  - Movimientos (global): ENTRADA / SALIDA / BAJA / TRASPASO_* agrupados
    por día, con cierre diario (rebajas y ventas). AJUSTE y UMBRAL se
    omiten.
  - Ventas_<Local> para TODOS los locales (activos e históricos):
    solo SALIDA con motivo "Venta", cierre por día y total del período
    (no "del año": los datos pueden abarcar varios años).
  - VentasGenerales: resumen mensual (Mes | Venta Mes | Acumulado) de
    TODOS los meses con datos, sin limitarse al año en curso.

Todos los valores monetarios se redondean a 2 decimales antes de
escribirse, para que el dato guardado coincida con lo que se ve
(el number_format solo afecta a la visualización).
"""
import io
from datetime import datetime
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from db import get_conn, GENERAL_ID
import locales as loc
import inventario as inv


COLOR_HEADER_BG = "FF263238"
COLOR_HEADER_FG = "FFFFFFFF"
COLOR_TITULO    = "FF37474F"
COLOR_TOTAL_BG  = "FFECEFF1"
COLOR_MERMA     = "FFC00000"

BORDE_FINO = Border(
    left=Side(style="thin", color="FFB0BEC5"),
    right=Side(style="thin", color="FFB0BEC5"),
    top=Side(style="thin", color="FFB0BEC5"),
    bottom=Side(style="thin", color="FFB0BEC5"),
)

NOMBRES_MES = [
    "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
    "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre",
    "Diciembre",
]


# ============================================================
# API pública
# ============================================================

def generar_excel_bytes() -> bytes:
    wb = Workbook()
    usados = set()
    primera = True

    # 1. Hojas por local ACTIVO
    for local in loc.listar_locales(solo_activos=True):
        nombre = _sanitizar(local["nombre"], usados)
        if primera:
            ws = wb.active
            ws.title = nombre
            primera = False
        else:
            ws = wb.create_sheet(nombre)
        _hoja_productos_local(ws, local)

    # 2. Movimientos global
    _hoja_movimientos(wb.create_sheet(_sanitizar("Movimientos", usados)))

    # 3. Ventas_<Local> para TODOS los locales (activos + cerrados)
    for local in loc.listar_locales(solo_activos=False):
        nombre = _sanitizar(f"Ventas_{local['nombre']}", usados)
        _hoja_ventas_local(wb.create_sheet(nombre), local)

    # 4. VentasGenerales (histórico completo)
    _hoja_ventas_generales(
        wb.create_sheet(_sanitizar("VentasGenerales", usados)))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ============================================================
# Helpers
# ============================================================

def _r2(x) -> float:
    """Redondea a 2 decimales para no guardar ruido flotante."""
    try:
        return round(float(x or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _sanitizar(nombre: str, usados: set) -> str:
    prohibidos = set(':\\/?*[]')
    limpio = "".join(c for c in (nombre or "")
                     if c not in prohibidos).strip() or "Hoja"
    limpio = limpio[:31]
    base = limpio
    cont = 1
    while limpio.lower() in usados:
        sufijo = f"_{cont}"
        limpio = base[:31 - len(sufijo)] + sufijo
        cont += 1
    usados.add(limpio.lower())
    return limpio


def _solo_fecha(t: str | None) -> str:
    return (t or "").split(" ")[0]


def _encabezado(ws, fila: int, textos: list):
    for col, txt in enumerate(textos, 1):
        c = ws.cell(row=fila, column=col, value=txt)
        c.font = Font(bold=True, color=COLOR_HEADER_FG, size=10)
        c.fill = PatternFill("solid", fgColor=COLOR_HEADER_BG)
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = BORDE_FINO
    ws.row_dimensions[fila].height = 26


def _anchos(ws, anchos: list):
    for i, w in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _titulo_hoja(ws, col_fin: int, texto: str):
    ws["A1"] = texto
    ws["A1"].font = Font(bold=True, size=12, color=COLOR_TITULO)
    ws.merge_cells(
        start_row=1, start_column=1, end_row=1, end_column=col_fin)
    ws.row_dimensions[1].height = 24


def _rango_fechas_ventas(local_id=None) -> tuple[str | None, str | None]:
    """Devuelve (min, max) fecha de SALIDAS con motivo 'Venta'."""
    sql = ("SELECT MIN(fecha) AS mn, MAX(fecha) AS mx "
           "FROM movimientos "
           "WHERE tipo='SALIDA' "
           "  AND LOWER(TRIM(COALESCE(motivo,'')))='venta'")
    params: list = []
    if local_id is not None:
        sql += " AND local_id=?"
        params.append(local_id)
    with get_conn() as conn:
        row = conn.execute(sql, tuple(params)).fetchone()
    if row and row["mn"]:
        return _solo_fecha(row["mn"]), _solo_fecha(row["mx"])
    return None, None


def _cierre_dia(ws, fila: int, etiqueta: str,
                rebajas: float, venta: float,
                ncols: int, col_rebaja: int, col_venta: int,
                col_merma: int | None = None,
                merma: float = 0.0):
    c = ws.cell(row=fila, column=1, value=etiqueta)
    c.font = Font(bold=True, color=COLOR_TITULO)
    c.alignment = Alignment(horizontal="left", vertical="center",
                            indent=1)

    relleno = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
    for col in range(1, ncols + 1):
        ws.cell(row=fila, column=col).border = BORDE_FINO
        ws.cell(row=fila, column=col).fill = relleno

    fin_merge = max(1, col_rebaja - 1)
    if fin_merge >= 2:
        ws.merge_cells(
            start_row=fila, start_column=1,
            end_row=fila, end_column=fin_merge)

    c = ws.cell(row=fila, column=col_rebaja, value=_r2(rebajas))
    c.font = Font(bold=True)
    c.alignment = Alignment(horizontal="right", vertical="center")
    c.number_format = '#,##0.00'

    c = ws.cell(row=fila, column=col_venta, value=_r2(venta))
    c.font = Font(bold=True)
    c.alignment = Alignment(horizontal="right", vertical="center")
    c.number_format = '#,##0.00'

    if col_merma is not None:
        c = ws.cell(row=fila, column=col_merma, value=_r2(merma))
        c.font = Font(bold=True, color=COLOR_MERMA)
        c.alignment = Alignment(horizontal="right", vertical="center")
        c.number_format = '#,##0.00'


# ============================================================
# Hoja por local: productos + resumen + TOTALES
# ============================================================

def _hoja_productos_local(ws, local: dict):
    _titulo_hoja(
        ws, 8,
        f"{local['nombre']} — "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Código", "Producto", "Stock",
        "Precio Costo", "Costo Total",
        "Precio Unitario", "Venta Total", "Margen",
    ])

    productos = inv.listar_productos(local["id"], solo_activos=True)

    inv_total = venta_total = margen_total = 0.0

    for i, p in enumerate(productos):
        fila = FILA_HEADER + 1 + i
        stock = float(p["stock"] or 0)
        pc = float(p.get("precio_costo", 0) or 0)
        pv = float(p.get("precio_unitario", 0) or 0)
        pc_tot = pc * stock
        pv_tot = pv * stock
        margen = pv_tot - pc_tot

        inv_total += pc_tot
        venta_total += pv_tot
        margen_total += margen

        valores = [
            p.get("codigo") or "",
            p["nombre"],
            stock,
            _r2(pc), _r2(pc_tot), _r2(pv), _r2(pv_tot), _r2(margen),
        ]
        for col, val in enumerate(valores, 1):
            c = ws.cell(row=fila, column=col, value=val)
            c.border = BORDE_FINO
            if col in (1, 3):
                c.alignment = Alignment(horizontal="center",
                                        vertical="center")
            elif col >= 4:
                c.alignment = Alignment(horizontal="right",
                                        vertical="center")
                c.number_format = '#,##0.00'
            else:
                c.alignment = Alignment(horizontal="left",
                                        vertical="center", indent=1)

    # Fila totales
    fila_tot = FILA_HEADER + 1 + len(productos)
    c = ws.cell(row=fila_tot, column=1, value="TOTALES")
    c.font = Font(bold=True)
    c.alignment = Alignment(horizontal="left", vertical="center",
                            indent=1)
    for col in (2, 3, 4):
        ws.cell(row=fila_tot, column=col, value="").border = BORDE_FINO
    for col, val in [(5, inv_total), (7, venta_total),
                     (8, margen_total)]:
        c = ws.cell(row=fila_tot, column=col, value=_r2(val))
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="right",
                                vertical="center")
        c.number_format = '#,##0.00'
        c.border = BORDE_FINO
    ws.cell(row=fila_tot, column=6, value="").border = BORDE_FINO

    relleno = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
    for col in range(1, 9):
        ws.cell(row=fila_tot, column=col).fill = relleno

    # Resumen arriba
    ws["A2"] = (
        f"Invertido: ${inv_total:,.2f}   |   "
        f"Venta: ${venta_total:,.2f}   |   "
        f"Margen: ${margen_total:,.2f}"
    )
    ws["A2"].font = Font(bold=True, size=10, color=COLOR_TITULO)
    ws.merge_cells("A2:H2")
    ws.row_dimensions[2].height = 20

    _anchos(ws, [14, 32, 10, 14, 16, 16, 16, 14])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"


# ============================================================
# Hoja Movimientos (global)
# ============================================================

def _hoja_movimientos(ws):
    _titulo_hoja(
        ws, 11,
        f"Movimientos — "
        f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Tipo", "Código", "Producto", "Cantidad",
        "Precio Unit.", "Rebaja U.", "Total Venta",
        "Motivo", "Local", "Fecha", "Total Merma",
    ])

    with get_conn() as conn:
        filas = conn.execute(
            "SELECT m.fecha, m.tipo, m.cantidad, m.motivo, m.rebaja, "
            "       m.precio_unitario_momento, m.detalle, "
            "       p.nombre AS producto, p.codigo AS codigo, "
            "       l.nombre AS local "
            "FROM movimientos m "
            "JOIN productos p ON p.id=m.producto_id "
            "JOIN locales   l ON l.id=m.local_id "
            "WHERE m.tipo IN ('ENTRADA','SALIDA','BAJA',"
            "                 'TRASPASO_SALIDA','TRASPASO_ENTRADA') "
            "ORDER BY m.fecha ASC, m.id ASC"
        ).fetchall()

    movs = [dict(r) for r in filas]
    por_dia: dict = {}
    for m in movs:
        por_dia.setdefault(_solo_fecha(m["fecha"]), []).append(m)

    total_merma = total_rebajas = 0.0
    fila = FILA_HEADER

    for dia in sorted(por_dia.keys()):
        rebajas_dia = venta_dia = merma_dia = 0.0
        for m in por_dia[dia]:
            fila += 1
            cant = float(m["cantidad"] or 0)
            reb = float(m["rebaja"] or 0)
            pu = float(m["precio_unitario_momento"] or 0)
            es_salida = m["tipo"] == "SALIDA"
            es_baja = m["tipo"] == "BAJA"
            motivo_lower = (m["motivo"] or "").strip().lower()
            es_venta = es_salida and motivo_lower == "venta"
            es_merma_salida = es_salida and not es_venta

            total_venta = ""
            col_merma = ""

            if es_venta:
                total_venta = _r2((pu - reb) * cant)
                rebajas_dia += reb * cant
                venta_dia += total_venta
            elif es_baja:
                col_merma = _r2((pu - reb) * cant)
                merma_dia += col_merma
            elif es_merma_salida:
                col_merma = _r2((pu - reb) * cant)
                merma_dia += col_merma

            valores = [
                m["tipo"],
                m.get("codigo") or "",
                m["producto"],
                cant,
                _r2(pu) if (es_salida or es_baja) else "",
                _r2(reb) if es_venta else "",
                total_venta,
                m["motivo"] or "",
                m["local"],
                m["fecha"],          # ← fecha completa con hora
                col_merma,
            ]
            for col, val in enumerate(valores, 1):
                c = ws.cell(row=fila, column=col, value=val)
                c.border = BORDE_FINO
                if es_baja or es_merma_salida:
                    c.font = Font(color=COLOR_MERMA)
                if col in (1, 2, 4, 8, 9, 10):
                    c.alignment = Alignment(horizontal="center",
                                            vertical="center")
                elif col in (5, 6, 7, 11):
                    c.alignment = Alignment(horizontal="right",
                                            vertical="center")
                    c.number_format = '#,##0.00'
                else:
                    c.alignment = Alignment(horizontal="left",
                                            vertical="center", indent=1)

        total_merma += merma_dia
        total_rebajas += rebajas_dia

        fila += 1
        _cierre_dia(
            ws, fila, f"TOTAL DEL DÍA — {dia}",
            rebajas_dia, venta_dia,
            ncols=11, col_rebaja=6, col_venta=7,
            col_merma=11, merma=merma_dia,
        )
        fila += 1  # fila en blanco

    # Resumen arriba
    ws["A2"] = (
        f"Rebajas (acumulado): ${_r2(total_rebajas):,.2f}   |   "
        f"Merma (acumulado): ${_r2(total_merma):,.2f}"
    )
    ws["A2"].font = Font(bold=True, size=10, color=COLOR_MERMA)
    ws.merge_cells("A2:K2")
    ws.row_dimensions[2].height = 20

    _anchos(ws, [16, 12, 30, 10, 12, 10, 14, 18, 16, 20, 14])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"


# ============================================================
# Hoja Ventas_<Local>
# ============================================================

def _hoja_ventas_local(ws, local: dict):
    mn, mx = _rango_fechas_ventas(local["id"])
    if mn and mx:
        subtitulo = f"{mn} → {mx}"
    else:
        subtitulo = datetime.now().strftime('%Y-%m-%d %H:%M')

    _titulo_hoja(
        ws, 7,
        f"Ventas — {local['nombre']} — {subtitulo}")

    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Código", "Producto", "Cantidad",
        "Precio Unit.", "Rebaja U.", "Total Venta", "Fecha",
    ])

    with get_conn() as conn:
        filas = conn.execute(
            "SELECT m.fecha, m.cantidad, m.rebaja, "
            "       m.precio_unitario_momento, "
            "       p.nombre AS producto, p.codigo AS codigo "
            "FROM movimientos m "
            "JOIN productos p ON p.id=m.producto_id "
            "WHERE m.local_id=? "
            "  AND m.tipo='SALIDA' "
            "  AND LOWER(TRIM(COALESCE(m.motivo,'')))='venta' "
            "ORDER BY m.fecha ASC, m.id ASC",
            (local["id"],),
        ).fetchall()

    movs = [dict(r) for r in filas]
    fila = FILA_HEADER

    if not movs:
        fila += 1
        c = ws.cell(row=fila, column=1,
                    value="Sin ventas registradas en este local.")
        c.font = Font(italic=True, color="FF888888")
        c.alignment = Alignment(horizontal="left",
                                vertical="center", indent=1)
        ws.merge_cells(start_row=fila, start_column=1,
                       end_row=fila, end_column=7)
        fila += 1
        _cierre_dia(
            ws, fila, "TOTAL DEL PERÍODO",
            0.0, 0.0,
            ncols=7, col_rebaja=5, col_venta=6,
        )
        _anchos(ws, [12, 32, 10, 12, 10, 14, 20])
        return

    por_dia: dict = {}
    for m in movs:
        por_dia.setdefault(_solo_fecha(m["fecha"]), []).append(m)

    reb_periodo = venta_periodo = 0.0
    for dia in sorted(por_dia.keys()):
        reb_dia = venta_dia = 0.0
        for m in por_dia[dia]:
            fila += 1
            cant = float(m["cantidad"] or 0)
            reb = float(m["rebaja"] or 0)
            pu = float(m["precio_unitario_momento"] or 0)
            total = _r2((pu - reb) * cant)
            reb_dia += reb * cant
            venta_dia += total

            valores = [
                m.get("codigo") or "",
                m["producto"],
                cant, _r2(pu), _r2(reb), total, m["fecha"],
            ]
            for col, val in enumerate(valores, 1):
                c = ws.cell(row=fila, column=col, value=val)
                c.border = BORDE_FINO
                if col in (1, 3):
                    c.alignment = Alignment(horizontal="center",
                                            vertical="center")
                elif col in (4, 5, 6):
                    c.alignment = Alignment(horizontal="right",
                                            vertical="center")
                    c.number_format = '#,##0.00'
                elif col == 7:
                    c.alignment = Alignment(horizontal="center",
                                            vertical="center")
                else:
                    c.alignment = Alignment(horizontal="left",
                                            vertical="center", indent=1)

        reb_periodo += reb_dia
        venta_periodo += venta_dia
        fila += 1
        _cierre_dia(
            ws, fila, f"TOTAL DEL DÍA — {dia}",
            reb_dia, venta_dia,
            ncols=7, col_rebaja=5, col_venta=6,
        )
        fila += 1

    fila += 1
    _cierre_dia(
        ws, fila, "TOTAL DEL PERÍODO",
        reb_periodo, venta_periodo,
        ncols=7, col_rebaja=5, col_venta=6,
    )

    _anchos(ws, [12, 32, 10, 12, 10, 14, 20])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"


# ============================================================
# Hoja VentasGenerales (resumen mensual — histórico completo)
# ============================================================

def _hoja_ventas_generales(ws):
    ventas = _ventas_por_mes_historico()

    if ventas:
        claves = sorted(ventas.keys())
        anio_ini, mes_ini = claves[0]
        anio_fin, mes_fin = claves[-1]
        rango = (f"{NOMBRES_MES[mes_ini-1]} {anio_ini} → "
                 f"{NOMBRES_MES[mes_fin-1]} {anio_fin}")
    else:
        rango = datetime.now().strftime("%Y-%m-%d")

    _titulo_hoja(ws, 3, f"Ventas Generales — {rango}")

    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Mes", "Venta Mes", "Acumulado",
    ])

    if not ventas:
        fila = FILA_HEADER + 1
        c = ws.cell(row=fila, column=1,
                    value="Sin ventas registradas.")
        c.font = Font(italic=True, color="FF888888")
        c.alignment = Alignment(horizontal="left",
                                vertical="center", indent=1)
        ws.merge_cells(start_row=fila, start_column=1,
                       end_row=fila, end_column=3)
        _anchos(ws, [26, 16, 16])
        return

    fila = FILA_HEADER
    acum = 0.0
    for (anio, mes) in sorted(ventas.keys()):
        v = ventas[(anio, mes)]
        acum += v
        fila += 1
        c = ws.cell(row=fila, column=1,
                    value=f"{NOMBRES_MES[mes-1]} {anio}")
        c.border = BORDE_FINO
        c.alignment = Alignment(horizontal="left", vertical="center",
                                indent=1)

        c = ws.cell(row=fila, column=2, value=_r2(v))
        c.border = BORDE_FINO
        c.alignment = Alignment(horizontal="right",
                                vertical="center")
        c.number_format = '#,##0.00'

        c = ws.cell(row=fila, column=3, value=_r2(acum))
        c.border = BORDE_FINO
        c.alignment = Alignment(horizontal="right",
                                vertical="center")
        c.number_format = '#,##0.00'

    # Fila total
    fila += 1
    c = ws.cell(row=fila, column=1, value="TOTAL DEL PERÍODO")
    c.font = Font(bold=True, color=COLOR_TITULO)
    c.alignment = Alignment(horizontal="left", vertical="center",
                            indent=1)
    total = sum(ventas.values())
    for col in (2, 3):
        c = ws.cell(row=fila, column=col, value=_r2(total))
        c.font = Font(bold=True)
        c.alignment = Alignment(horizontal="right", vertical="center")
        c.number_format = '#,##0.00'

    relleno = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
    for col in range(1, 4):
        ws.cell(row=fila, column=col).fill = relleno
        ws.cell(row=fila, column=col).border = BORDE_FINO

    _anchos(ws, [26, 16, 16])


def _ventas_por_mes_historico() -> dict:
    """
    Devuelve {(anio, mes): total} para TODOS los meses con ventas,
    sin limitarse al año actual.
    """
    with get_conn() as conn:
        filas = conn.execute(
            "SELECT CAST(strftime('%Y', fecha) AS INTEGER) AS anio, "
            "       CAST(strftime('%m', fecha) AS INTEGER) AS mes, "
            "       SUM((precio_unitario_momento - rebaja) * cantidad) "
            "       AS venta "
            "FROM movimientos "
            "WHERE tipo='SALIDA' "
            "  AND LOWER(TRIM(COALESCE(motivo,'')))='venta' "
            "GROUP BY anio, mes "
            "ORDER BY anio, mes"
        ).fetchall()
    return {
        (int(r["anio"]), int(r["mes"])): float(r["venta"] or 0.0)
        for r in filas
    }