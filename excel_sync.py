"""
Excel sync v4.4 — Almacén Combos Flash.

FIXES v3 → v4:
  #1  Ventas (histórico + diario): excluir Fondo CUP/USD.
  #2  Ventas histórico: TOTAL DEL PERÍODO incluye Cantidad total.
  #3  Movs histórico: "Merma" solo BAJA y SALIDA con motivo Merma.
  #4  Salidas: "Error" ya no se clasifica como Merma.
  #5  Salidas: total mermas refleja solo mermas reales.
  #6  Diario: distinguir visualmente BAJA Error vs Merma.
  #7  Movs histórico: TOTAL DEL DÍA incluye cantidad total.

FIXES v4 → v4.1:
  #11 Movs histórico: excluir Fondos del total de ventas.
  #12 Salidas: excluir Fondos del listado VENTAS.
  #13 Salidas: OTRAS incluye TODO lo que no sea ENTRADA ni venta.
  #14 Movs histórico: Precio U. vacío cuando es 0.
  #15 Movs histórico: pintar en rojo TODA merma (SALIDA o BAJA).
  #16 _es_merma solo acepta BAJA/SALIDA.

FIXES v4.1 → v4.2:
  #17 Excluir movs de órdenes anuladas en todas las consultas.
  #18 Salidas: barras de título con fondo fuerte (texto blanco).
  #19 Tabla "Fondos CUP/USD" con saldo acumulado.

FIXES v4.2 → v4.3:
  #20 Quitar tabla de fondos redundante:
      - _hoja_productos_local  (duplicaba Movs_Almacén)
      - _hoja_ventas_local     (duplicaba Movs_Almacén)
      - _hoja_ventas_dia_local (duplicaba diario.Resumen)
      Se mantiene solo en:
      - inventario.Resumen     (consolidado histórico)
      - inventario.Movs_{Local} (histórico por local)
      - diario.Resumen         (día, todos los locales)

FIXES v4.3 → v4.4:
  #21 auto_filter con rango explícito (antes usaba `fila - 3`
      que quedaba desfasado al añadir la tabla de fondos):
      - inventario.Resumen        → A3:F{total_resumen}
      - inventario.Movs_{Local}   → A3:I{total_periodo}
      - diario.Resumen            → A3:J{total_general}
      Ahora el filtro cubre header + datos + total, sin
      arrastrar filas en blanco ni la tabla de fondos.
"""
import io
from datetime import datetime

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from db import get_conn, GENERAL_ID
import locales as loc


# ══════════════════════════════════════════════════════════
# COLORES / ESTILOS
# ══════════════════════════════════════════════════════════
COLOR_HEADER_BG  = "FF263238"
COLOR_HEADER_FG  = "FFFFFFFF"
COLOR_TITULO     = "FF37474F"
COLOR_TOTAL_BG   = "FFECEFF1"
COLOR_DIA_BG     = "FFFFF9C4"
COLOR_MERMA      = "FFC00000"
COLOR_ENTRADA_BG = "FFE3F2FD"
COLOR_SALIDA_BG  = "FFFFF3E0"
COLOR_MERMA_BG   = "FFFFEBEE"
COLOR_ALERTA_BG  = "FFFFF59D"

# FIX #18: colores fuertes para las barras de título de _hoja_3_tablas
COLOR_TITULO_ENTRADA = "FF0284C7"   # azul fuerte
COLOR_TITULO_VENTAS  = "FFD97706"   # ámbar fuerte
COLOR_TITULO_OTRAS   = "FFDC2626"   # rojo fuerte

# FIX #19: color de la cabecera de la tabla de fondos
COLOR_TITULO_FONDOS  = "FF0F766E"   # teal fuerte

BORDE_FINO = Border(
    left=Side(style="thin", color="FFB0BEC5"),
    right=Side(style="thin", color="FFB0BEC5"),
    top=Side(style="thin", color="FFB0BEC5"),
    bottom=Side(style="thin", color="FFB0BEC5"),
)

_FONT_HEADER      = Font(bold=True, color=COLOR_HEADER_FG, size=10)
_FONT_TITULO      = Font(bold=True, size=12, color=COLOR_TITULO)
_FONT_BOLD        = Font(bold=True)
_FONT_BOLD_TITULO = Font(bold=True, color=COLOR_TITULO)
_FONT_ITALIC_GREY = Font(italic=True, color="FF888888")
_FONT_MERMA       = Font(color=COLOR_MERMA)
_FONT_ENTRADA     = Font(color="FF0284C7", bold=True)
_FONT_SALIDA      = Font(color="FFDC2626", bold=True)

_FILL_HEADER  = PatternFill("solid", fgColor=COLOR_HEADER_BG)
_FILL_TOTAL   = PatternFill("solid", fgColor=COLOR_TOTAL_BG)
_FILL_DIA     = PatternFill("solid", fgColor=COLOR_DIA_BG)
_FILL_ENTRADA = PatternFill("solid", fgColor=COLOR_ENTRADA_BG)
_FILL_SALIDA  = PatternFill("solid", fgColor=COLOR_SALIDA_BG)
_FILL_MERMA   = PatternFill("solid", fgColor=COLOR_MERMA_BG)
_FILL_ALERTA  = PatternFill("solid", fgColor=COLOR_ALERTA_BG)

_FILL_TITULO_ENTRADA = PatternFill("solid", fgColor=COLOR_TITULO_ENTRADA)
_FILL_TITULO_VENTAS  = PatternFill("solid", fgColor=COLOR_TITULO_VENTAS)
_FILL_TITULO_OTRAS   = PatternFill("solid", fgColor=COLOR_TITULO_OTRAS)
_FILL_TITULO_FONDOS  = PatternFill("solid", fgColor=COLOR_TITULO_FONDOS)

_ALIGN_CENTER = Alignment(horizontal="center", vertical="center")
_ALIGN_RIGHT  = Alignment(horizontal="right", vertical="center")
_ALIGN_LEFT   = Alignment(horizontal="left", vertical="center", indent=1)

_NUM_2DEC = '#,##0.00'


# ══════════════════════════════════════════════════════════
# CLASIFICACIÓN
# ══════════════════════════════════════════════════════════
VENTA_MOTIVOS = ("combos", "venta")
_SQL_VENTA = "LOWER(TRIM(COALESCE(m.motivo,''))) IN ('combos','venta')"
_SQL_NO_FONDO = "LOWER(COALESCE(p.nombre,'')) NOT LIKE 'fondo%'"
_SQL_NO_ANULADA = (
    "NOT EXISTS (SELECT 1 FROM ordenes_venta o "
    "WHERE o.estado='anulada' "
    "AND m.detalle = 'Ticket ' || o.numero_ticket)"
)


def _es_venta(motivo) -> bool:
    return (motivo or "").strip().lower() in VENTA_MOTIVOS


def _es_merma(motivo, tipo=None) -> bool:
    if tipo not in ("BAJA", "SALIDA"):
        return False
    m = (motivo or "").strip().lower()
    if m == "error":
        return False
    if m == "merma":
        return True
    if tipo == "BAJA":
        return True
    return False


def _es_fondo(nombre) -> bool:
    return (nombre or "").strip().lower().startswith("fondo")


# ══════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════
def _r2(x):
    try:
        return round(float(x or 0), 2)
    except (TypeError, ValueError):
        return 0.0


def _sanitizar(nombre, usados):
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


def _solo_fecha(t):
    return (t or "").split(" ")[0]


def _solo_hora(t):
    partes = (t or "").split(" ")
    return partes[1][:8] if len(partes) > 1 else ""


def _encabezado(ws, fila, textos):
    for col, txt in enumerate(textos, 1):
        c = ws.cell(row=fila, column=col, value=txt)
        c.font = _FONT_HEADER
        c.fill = _FILL_HEADER
        c.alignment = _ALIGN_CENTER
        c.border = BORDE_FINO
    ws.row_dimensions[fila].height = 26


def _anchos(ws, anchos):
    for i, w in enumerate(anchos, 1):
        ws.column_dimensions[get_column_letter(i)].width = w


def _titulo_hoja(ws, col_fin, texto):
    ws["A1"] = texto
    ws["A1"].font = _FONT_TITULO
    ws.merge_cells(start_row=1, start_column=1, end_row=1,
                   end_column=col_fin)
    ws.row_dimensions[1].height = 24


def _pintar_rango(ws, fila, col_ini, col_fin, fill):
    for col in range(col_ini, col_fin + 1):
        c = ws.cell(row=fila, column=col)
        c.border = BORDE_FINO
        c.fill = fill


def _fila_total(ws, fila, etiqueta, valores, col_ini, col_fin,
                fill, col_etiqueta=None):
    if col_etiqueta is None:
        col_etiqueta = col_ini
    c = ws.cell(row=fila, column=col_etiqueta, value=etiqueta)
    c.font = _FONT_BOLD_TITULO
    c.alignment = _ALIGN_LEFT
    _pintar_rango(ws, fila, col_ini, col_fin, fill)
    for col, (val, fmt) in valores.items():
        if col < col_ini or col > col_fin:
            continue
        cc = ws.cell(row=fila, column=col, value=val)
        cc.font = _FONT_BOLD
        cc.alignment = _ALIGN_RIGHT
        if fmt:
            cc.number_format = fmt


# ══════════════════════════════════════════════════════════
# CARGA DE DATOS
# ══════════════════════════════════════════════════════════
def _cargar_productos_local(local_id) -> list[dict]:
    with get_conn() as conn:
        filas = conn.execute(
            "SELECT * FROM productos WHERE local_id=? AND activo=1 "
            "ORDER BY "
            "CASE WHEN codigo IS NULL OR codigo='' THEN 1 ELSE 0 END, "
            "codigo COLLATE NOCASE, nombre COLLATE NOCASE",
            (local_id,)).fetchall()
    return [dict(r) for r in filas]


def _cargar_movs_local(local_id) -> list[dict]:
    with get_conn() as conn:
        filas = conn.execute(
            "SELECT m.fecha, m.tipo, m.cantidad, m.motivo, m.rebaja, "
            "       m.precio_unitario_momento, m.precio_costo_momento, "
            "       m.usuario, m.detalle, "
            "       p.nombre AS producto, p.codigo AS codigo "
            "FROM movimientos m "
            "JOIN productos p ON p.id=m.producto_id "
            "WHERE m.local_id=? "
            "AND m.tipo IN ('ENTRADA','SALIDA','BAJA') "
            f"AND {_SQL_NO_ANULADA} "
            "ORDER BY m.fecha ASC, m.id ASC",
            (local_id,)).fetchall()
    return [dict(r) for r in filas]


def _cargar_ventas_local(local_id) -> list[dict]:
    with get_conn() as conn:
        filas = conn.execute(
            "SELECT m.fecha, m.cantidad, m.rebaja, "
            "       m.precio_unitario_momento, "
            "       p.nombre AS producto, p.codigo AS codigo "
            "FROM movimientos m "
            "JOIN productos p ON p.id=m.producto_id "
            "WHERE m.local_id=? "
            "AND m.tipo='SALIDA' "
            f"AND {_SQL_VENTA} "
            f"AND {_SQL_NO_FONDO} "
            f"AND {_SQL_NO_ANULADA} "
            "ORDER BY m.fecha ASC, m.id ASC",
            (local_id,)).fetchall()
    return [dict(r) for r in filas]


def _cargar_movs_fondos(local_id=None, desde=None, hasta=None) -> list[dict]:
    sql = ("SELECT m.fecha, m.tipo, m.cantidad, m.motivo, m.usuario, "
           "       p.nombre AS producto "
           "FROM movimientos m "
           "JOIN productos p ON p.id=m.producto_id "
           "WHERE LOWER(p.nombre) LIKE 'fondo%' "
           "AND m.tipo IN ('ENTRADA','SALIDA')")
    params = []
    if local_id is not None and local_id != GENERAL_ID:
        sql += " AND m.local_id=?"
        params.append(local_id)
    if desde:
        sql += " AND m.fecha >= ?"
        params.append(desde)
    if hasta:
        sql += " AND m.fecha < ?"
        params.append(hasta)
    sql += " ORDER BY m.fecha ASC, m.id ASC"
    with get_conn() as conn:
        return [dict(r) for r in
                conn.execute(sql, tuple(params)).fetchall()]


# ══════════════════════════════════════════════════════════
# TABLA DE FONDOS (solo se usa donde NO es redundante)
# ══════════════════════════════════════════════════════════
def _escribir_tabla_fondos(ws, fila_ini, movs, titulo,
                            col_ini=1, col_fin=7,
                            etiqueta_saldo="Saldo"):
    """
    Escribe una tabla con:
      Fecha | Fondo | Tipo | Cantidad | Motivo | Usuario | <etiqueta_saldo>
    `etiqueta_saldo` permite poner "Neto del día" para tablas diarias
    en vez de "Saldo" (que en tablas diarias puede confundir).
    Devuelve la fila siguiente tras la tabla.
    """
    # Barra de título
    c = ws.cell(row=fila_ini, column=col_ini, value=titulo)
    c.font = _FONT_HEADER
    ws.merge_cells(start_row=fila_ini, start_column=col_ini,
                   end_row=fila_ini, end_column=col_fin)
    for col in range(col_ini, col_fin + 1):
        cc = ws.cell(row=fila_ini, column=col)
        cc.fill = _FILL_TITULO_FONDOS
        cc.border = BORDE_FINO
        cc.alignment = _ALIGN_CENTER
    ws.row_dimensions[fila_ini].height = 22
    fila = fila_ini + 1

    # Encabezados
    encabezados = ["Fecha", "Fondo", "Tipo", "Cantidad",
                   "Motivo", "Usuario", etiqueta_saldo]
    for i, txt in enumerate(encabezados):
        cc = ws.cell(row=fila, column=col_ini + i, value=txt)
        cc.font = _FONT_HEADER
        cc.fill = _FILL_HEADER
        cc.alignment = _ALIGN_CENTER
        cc.border = BORDE_FINO
    ws.row_dimensions[fila].height = 22
    fila += 1

    if not movs:
        cc = ws.cell(row=fila, column=col_ini,
                     value="Sin movimientos de fondos en el período.")
        cc.font = _FONT_ITALIC_GREY
        ws.merge_cells(start_row=fila, start_column=col_ini,
                       end_row=fila, end_column=col_fin)
        return fila + 2

    saldos = {}
    for m in movs:
        fondo = m["producto"]
        cant = float(m["cantidad"] or 0)
        if m["tipo"] == "ENTRADA":
            saldos[fondo] = saldos.get(fondo, 0.0) + cant
            fuente = _FONT_ENTRADA
        else:
            saldos[fondo] = saldos.get(fondo, 0.0) - cant
            fuente = _FONT_SALIDA

        vals = [
            m["fecha"], fondo, m["tipo"], cant,
            m["motivo"] or "", m["usuario"], saldos[fondo],
        ]
        for i, v in enumerate(vals):
            cc = ws.cell(row=fila, column=col_ini + i, value=v)
            cc.border = BORDE_FINO
            cc.font = fuente
            if i in (0, 1, 2, 5):
                cc.alignment = _ALIGN_CENTER
            elif i in (3, 6):
                cc.alignment = _ALIGN_RIGHT
                cc.number_format = _NUM_2DEC
            else:
                cc.alignment = _ALIGN_LEFT
        fila += 1

    # Fila resumen por fondo
    fila += 1
    for fondo, saldo in sorted(saldos.items()):
        cc = ws.cell(row=fila, column=col_ini,
                     value=f"{etiqueta_saldo} {fondo}")
        cc.font = _FONT_BOLD_TITULO
        cc.alignment = _ALIGN_LEFT
        cc2 = ws.cell(row=fila, column=col_ini + 6, value=saldo)
        cc2.font = _FONT_BOLD
        cc2.alignment = _ALIGN_RIGHT
        cc2.number_format = _NUM_2DEC
        for col in range(col_ini, col_fin + 1):
            ws.cell(row=fila, column=col).border = BORDE_FINO
            ws.cell(row=fila, column=col).fill = _FILL_TOTAL
        fila += 1

    return fila + 1


# ══════════════════════════════════════════════════════════
# HOJA: RESUMEN DEL INVENTARIO
# ══════════════════════════════════════════════════════════
def _hoja_resumen_inventario(ws, locales):
    _titulo_hoja(ws, 6,
                 f"Resumen del inventario — "
                 f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Local", "Invertido (CUP)", "Venta potencial (CUP)",
        "Margen (CUP)", "Margen %", "Nº Productos",
    ])

    fila = FILA_HEADER
    tot_inv = tot_ven = tot_mar = 0.0
    tot_prod = 0

    for local in locales:
        fila += 1
        prod = _cargar_productos_local(local["id"])
        inv_t = sum(float(p["precio_costo"] or 0)
                    * float(p["stock"] or 0) for p in prod)
        ven_t = sum(float(p["precio_unitario"] or 0)
                    * float(p["stock"] or 0) for p in prod)
        mar_t = ven_t - inv_t
        mar_pct = (mar_t / inv_t * 100) if inv_t > 0 else 0.0
        n = len(prod)
        tot_inv += inv_t; tot_ven += ven_t; tot_mar += mar_t; tot_prod += n

        valores = [local["nombre"], _r2(inv_t), _r2(ven_t),
                   _r2(mar_t), _r2(mar_pct), n]
        for col, val in enumerate(valores, 1):
            c = ws.cell(row=fila, column=col, value=val)
            c.border = BORDE_FINO
            if col == 1:
                c.alignment = _ALIGN_LEFT
            elif col == 6:
                c.alignment = _ALIGN_CENTER
            else:
                c.alignment = _ALIGN_RIGHT
                c.number_format = _NUM_2DEC

    fila += 1
    tot_pct = (tot_mar / tot_inv * 100) if tot_inv > 0 else 0.0
    _fila_total(ws, fila, "TOTAL", {
        2: (_r2(tot_inv), _NUM_2DEC),
        3: (_r2(tot_ven), _NUM_2DEC),
        4: (_r2(tot_mar), _NUM_2DEC),
        5: (_r2(tot_pct), _NUM_2DEC),
        6: (tot_prod, None),
    }, col_ini=1, col_fin=6, fill=_FILL_TOTAL)

    # FIX #21: guardo la fila del total ANTES de escribir la tabla de
    # fondos, para que el auto_filter apunte al rango correcto.
    fila_total_resumen = fila

    # Tabla de fondos consolidada (único sitio histórico global)
    fila += 2
    movs_fondos = _cargar_movs_fondos(local_id=None)
    _escribir_tabla_fondos(
        ws, fila, movs_fondos,
        "FONDOS CUP/USD — Histórico consolidado",
        col_ini=1, col_fin=7, etiqueta_saldo="Saldo")

    _anchos(ws, [26, 16, 20, 16, 12, 12, 16])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"
    # FIX #21: rango explícito, cubre header + data + TOTAL.
    ws.auto_filter.ref = f"A{FILA_HEADER}:F{fila_total_resumen}"


# ══════════════════════════════════════════════════════════
# HOJA: PRODUCTOS DEL LOCAL
# ══════════════════════════════════════════════════════════
def _hoja_productos_local(ws, local, productos):
    _titulo_hoja(ws, 10,
                 f"{local['nombre']} — "
                 f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")
    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Código", "Producto", "Stock", "Moneda",
        "Costo CUP", "Precio Venta CUP",
        "Costo Total", "Venta Total", "Margen", "Margen %",
    ])

    inv_total = venta_total = margen_total = 0.0
    fila = FILA_HEADER
    n_alerta = 0

    for p in productos:
        fila += 1
        stock = float(p["stock"] or 0)
        pc_cup = float(p.get("precio_costo", 0) or 0)
        pu_cup = float(p.get("precio_unitario", 0) or 0)
        mc = (p.get("moneda_costo") or "CUP").upper()
        mv = (p.get("moneda_venta") or "CUP").upper()
        pc_tot = pc_cup * stock
        pv_tot = pu_cup * stock
        margen = pv_tot - pc_tot
        margen_pct = (margen / pc_tot * 100) if pc_tot > 0 else 0.0

        alerta = (pc_cup > 0.001 and pu_cup < 0.001)
        if alerta:
            n_alerta += 1

        inv_total += pc_tot; venta_total += pv_tot; margen_total += margen
        moneda_txt = f"{mc}/{mv}" if mc != mv else mc

        valores = [
            p.get("codigo") or "", p["nombre"], stock, moneda_txt,
            _r2(pc_cup), _r2(pu_cup), _r2(pc_tot), _r2(pv_tot),
            _r2(margen), _r2(margen_pct),
        ]
        for col, val in enumerate(valores, 1):
            c = ws.cell(row=fila, column=col, value=val)
            c.border = BORDE_FINO
            if alerta:
                c.fill = _FILL_ALERTA
            if col in (1, 3, 4):
                c.alignment = _ALIGN_CENTER
            elif col >= 5:
                c.alignment = _ALIGN_RIGHT
                c.number_format = _NUM_2DEC
            else:
                c.alignment = _ALIGN_LEFT

    fila_tot = fila + 1
    _fila_total(ws, fila_tot, "TOTALES", {
        7: (_r2(inv_total), _NUM_2DEC),
        8: (_r2(venta_total), _NUM_2DEC),
        9: (_r2(margen_total), _NUM_2DEC),
    }, col_ini=1, col_fin=10, fill=_FILL_TOTAL)

    ws["A2"] = (f"Invertido: ${inv_total:,.2f}   |   "
                f"Venta: ${venta_total:,.2f}   |   "
                f"Margen: ${margen_total:,.2f}"
                + (f"   |   ⚠️ {n_alerta} sin precio de venta"
                   if n_alerta else ""))
    ws["A2"].font = Font(bold=True, size=10,
                         color=(COLOR_MERMA if n_alerta else COLOR_TITULO))
    ws.merge_cells("A2:J2")
    ws.row_dimensions[2].height = 20

    # FIX #20: sin tabla de fondos (redundante con Movs_Almacén)
    _anchos(ws, [14, 32, 10, 12, 14, 16, 14, 14, 14, 10])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"
    ws.auto_filter.ref = f"A{FILA_HEADER}:J{fila}"


# ══════════════════════════════════════════════════════════
# HOJA: MOVS HISTÓRICOS DEL LOCAL
# ══════════════════════════════════════════════════════════
def _hoja_movs_local(ws, local, movs):
    _titulo_hoja(ws, 9, f"Movimientos — {local['nombre']} (Histórico)")
    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Tipo", "Código", "Producto", "Cantidad",
        "Precio U.", "Rebaja U.", "Total Venta",
        "Motivo", "Fecha",
    ])

    if not movs:
        fila = FILA_HEADER + 1
        c = ws.cell(row=fila, column=1,
                    value="Sin movimientos registrados.")
        c.font = _FONT_ITALIC_GREY
        ws.merge_cells(start_row=fila, start_column=1,
                       end_row=fila, end_column=9)
        _anchos(ws, [14, 12, 32, 10, 12, 10, 14, 18, 20])
        return

    por_dia = {}
    for m in movs:
        por_dia.setdefault(_solo_fecha(m["fecha"]), []).append(m)

    fila = FILA_HEADER
    tot_reb = tot_venta = tot_merma = 0.0
    tot_qty_v = 0.0

    for dia in sorted(por_dia.keys()):
        reb_dia = venta_dia = merma_dia = qty_v_dia = 0.0
        n_dia = 0
        for m in por_dia[dia]:
            fila += 1
            n_dia += 1
            cant = float(m["cantidad"] or 0)
            pu = float(m["precio_unitario_momento"] or 0)
            reb = float(m["rebaja"] or 0)
            es_baja = m["tipo"] == "BAJA"
            es_merma = _es_merma(m["motivo"], m["tipo"])
            es_error = (m["motivo"] or "").strip().lower() == "error"
            es_venta = (
                m["tipo"] == "SALIDA"
                and _es_venta(m["motivo"])
                and not _es_fondo(m["producto"])
            )

            total_venta = ""
            if es_venta:
                total_venta = _r2((pu - reb) * cant)
                reb_dia += reb * cant
                venta_dia += total_venta
                qty_v_dia += cant
            elif es_merma:
                merma_dia += _r2((pu - reb) * cant)

            valores = [
                m["tipo"], m.get("codigo") or "", m["producto"], cant,
                _r2(pu) if (pu and m["tipo"] in ("SALIDA", "BAJA")) else "",
                _r2(reb) if es_venta else "",
                total_venta, m["motivo"] or "", m["fecha"],
            ]
            for col, val in enumerate(valores, 1):
                c = ws.cell(row=fila, column=col, value=val)
                c.border = BORDE_FINO
                if es_merma:
                    c.font = _FONT_MERMA
                elif es_error:
                    c.font = _FONT_ITALIC_GREY
                if col in (1, 2, 4, 9):
                    c.alignment = _ALIGN_CENTER
                elif col in (5, 6, 7):
                    c.alignment = _ALIGN_RIGHT
                    if val != "":
                        c.number_format = _NUM_2DEC
                else:
                    c.alignment = _ALIGN_LEFT

        tot_reb += reb_dia
        tot_venta += venta_dia
        tot_merma += merma_dia
        tot_qty_v += qty_v_dia

        fila += 1
        _fila_total(
            ws, fila,
            f"TOTAL DEL DÍA — {dia} ({n_dia} movs)",
            valores={
                4: (qty_v_dia if qty_v_dia else "", None),
                6: (_r2(reb_dia), _NUM_2DEC),
                7: (_r2(venta_dia), _NUM_2DEC),
                8: (f"Merma: ${_r2(merma_dia):,.2f}", None),
            },
            col_ini=1, col_fin=9, fill=_FILL_DIA)
        fila += 1

    fila += 1
    _fila_total(
        ws, fila, "TOTAL DEL PERÍODO",
        valores={
            4: (tot_qty_v if tot_qty_v else "", None),
            6: (_r2(tot_reb), _NUM_2DEC),
            7: (_r2(tot_venta), _NUM_2DEC),
            8: (f"Merma: ${_r2(tot_merma):,.2f}", None),
        },
        col_ini=1, col_fin=9, fill=_FILL_TOTAL)

    # FIX #21: guardo la fila del TOTAL DEL PERÍODO antes de los fondos
    fila_total_periodo = fila

    # Tabla de fondos del local (único sitio histórico por local)
    fila += 2
    movs_fondos = _cargar_movs_fondos(local_id=local["id"])
    _escribir_tabla_fondos(
        ws, fila, movs_fondos,
        f"FONDOS CUP/USD — {local['nombre']} (Histórico)",
        col_ini=1, col_fin=7, etiqueta_saldo="Saldo")

    _anchos(ws, [14, 12, 32, 10, 14, 12, 14, 18, 20])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"
    # FIX #21: filtro solo hasta el TOTAL DEL PERÍODO, sin arrastrar
    # filas en blanco ni la tabla de fondos.
    ws.auto_filter.ref = f"A{FILA_HEADER}:I{fila_total_periodo}"


# ══════════════════════════════════════════════════════════
# HOJA: VENTAS HISTÓRICAS DEL LOCAL
# ══════════════════════════════════════════════════════════
def _hoja_ventas_local(ws, local, movs):
    _titulo_hoja(ws, 7, f"Ventas — {local['nombre']} (Combos)")
    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Código", "Producto", "Cantidad",
        "Precio U.", "Rebaja U.", "Total Venta", "Fecha",
    ])

    if not movs:
        fila = FILA_HEADER + 1
        c = ws.cell(row=fila, column=1,
                    value="Sin ventas registradas.")
        c.font = _FONT_ITALIC_GREY
        ws.merge_cells(start_row=fila, start_column=1,
                       end_row=fila, end_column=7)
        _anchos(ws, [12, 32, 10, 12, 10, 14, 20])
        return

    por_dia = {}
    for m in movs:
        por_dia.setdefault(_solo_fecha(m["fecha"]), []).append(m)

    fila = FILA_HEADER
    reb_total = venta_total = qty_total = 0.0

    for dia in sorted(por_dia.keys()):
        reb_dia = venta_dia = qty_dia = 0.0
        for m in por_dia[dia]:
            fila += 1
            cant = float(m["cantidad"] or 0)
            reb = float(m["rebaja"] or 0)
            pu = float(m["precio_unitario_momento"] or 0)
            total = _r2((pu - reb) * cant)
            reb_dia += reb * cant
            venta_dia += total
            qty_dia += cant

            valores = [m.get("codigo") or "", m["producto"], cant,
                       _r2(pu), _r2(reb), total, m["fecha"]]
            for col, val in enumerate(valores, 1):
                c = ws.cell(row=fila, column=col, value=val)
                c.border = BORDE_FINO
                if col in (1, 3, 7):
                    c.alignment = _ALIGN_CENTER
                elif col in (4, 5, 6):
                    c.alignment = _ALIGN_RIGHT
                    c.number_format = _NUM_2DEC
                else:
                    c.alignment = _ALIGN_LEFT

        reb_total += reb_dia
        venta_total += venta_dia
        qty_total += qty_dia
        fila += 1
        _fila_total(
            ws, fila,
            f"TOTAL DEL DÍA — {dia}",
            valores={
                3: (qty_dia, None),
                5: (_r2(reb_dia), _NUM_2DEC),
                6: (_r2(venta_dia), _NUM_2DEC),
                7: (dia, None),
            },
            col_ini=1, col_fin=7, fill=_FILL_DIA)
        fila += 1

    fila += 1
    _fila_total(
        ws, fila, "TOTAL DEL PERÍODO",
        valores={
            3: (qty_total, None),
            5: (_r2(reb_total), _NUM_2DEC),
            6: (_r2(venta_total), _NUM_2DEC),
        },
        col_ini=1, col_fin=7, fill=_FILL_TOTAL)

    # FIX #20: sin tabla de fondos (redundante con Movs_Almacén)
    _anchos(ws, [12, 32, 10, 12, 10, 14, 20])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"
    ws.auto_filter.ref = f"A{FILA_HEADER}:G{fila}"


# ══════════════════════════════════════════════════════════
# EXPORT 1: INVENTARIO COMPLETO
# ══════════════════════════════════════════════════════════
def generar_excel_bytes() -> bytes:
    wb = Workbook()
    usados = set()
    locales_activos = loc.listar_locales(solo_activos=True)

    ws_res = wb.active
    ws_res.title = _sanitizar("Resumen", usados)
    _hoja_resumen_inventario(ws_res, locales_activos)

    for local in locales_activos:
        ws_p = wb.create_sheet(_sanitizar(local["nombre"], usados))
        _hoja_productos_local(ws_p, local,
                              _cargar_productos_local(local["id"]))

        ws_m = wb.create_sheet(
            _sanitizar(f"Movs_{local['nombre']}", usados))
        _hoja_movs_local(ws_m, local, _cargar_movs_local(local["id"]))

        ws_v = wb.create_sheet(
            _sanitizar(f"Ventas_{local['nombre']}", usados))
        _hoja_ventas_local(ws_v, local,
                           _cargar_ventas_local(local["id"]))

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ══════════════════════════════════════════════════════════
# EXPORT 2: DIARIO
# ══════════════════════════════════════════════════════════
def generar_excel_diario() -> bytes:
    hoy = datetime.now().strftime("%Y-%m-%d")
    locales_activos = loc.listar_locales(solo_activos=True)

    wb = Workbook()
    usados = set()

    ws_res = wb.active
    ws_res.title = _sanitizar("Resumen", usados)
    _hoja_movs_dia_general(ws_res, hoy)

    for local in locales_activos:
        ws = wb.create_sheet(_sanitizar(local["nombre"], usados))
        _hoja_ventas_dia_local(ws, local, hoy)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _hoja_movs_dia_general(ws, hoy):
    _titulo_hoja(ws, 10,
                 f"Movimientos del día — {hoy} — Todos los locales")
    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Hora", "Local", "Tipo", "Código", "Producto",
        "Cantidad", "Precio U.", "Rebaja U.", "Total Venta", "Motivo",
    ])

    with get_conn() as conn:
        filas = conn.execute(
            "SELECT m.fecha, m.tipo, m.cantidad, m.motivo, m.rebaja, "
            "       m.precio_unitario_momento, "
            "       p.nombre AS producto, p.codigo AS codigo, "
            "       l.nombre AS local "
            "FROM movimientos m "
            "JOIN productos p ON p.id=m.producto_id "
            "JOIN locales l ON l.id=m.local_id "
            "WHERE DATE(m.fecha)=? "
            "AND m.tipo IN ('ENTRADA','SALIDA','BAJA') "
            f"AND {_SQL_NO_ANULADA} "
            "ORDER BY l.nombre COLLATE NOCASE, m.fecha ASC, m.id ASC",
            (hoy,)).fetchall()
    movs = [dict(r) for r in filas]

    if not movs:
        fila = FILA_HEADER + 1
        c = ws.cell(row=fila, column=1,
                    value="Sin movimientos registrados hoy.")
        c.font = _FONT_ITALIC_GREY
        ws.merge_cells(start_row=fila, start_column=1,
                    end_row=fila, end_column=10)
        _anchos(ws, [10, 16, 12, 12, 30, 10, 12, 12, 14, 22])
        return

    por_local = {}
    for m in movs:
        por_local.setdefault(m["local"], []).append(m)

    fila = FILA_HEADER
    tot_reb_g = tot_venta_g = tot_merma_g = 0.0
    tot_e_g = tot_v_g = tot_b_g = tot_o_g = 0

    for local_nombre in sorted(por_local.keys()):
        reb_loc = venta_loc = merma_loc = 0.0
        n_e = n_v = n_b = n_o = 0

        for m in por_local[local_nombre]:
            fila += 1
            cant = float(m["cantidad"] or 0)
            pu = float(m["precio_unitario_momento"] or 0)
            reb = float(m["rebaja"] or 0)
            es_venta = (m["tipo"] == "SALIDA"
                        and _es_venta(m["motivo"])
                        and not _es_fondo(m["producto"]))
            es_baja = m["tipo"] == "BAJA"
            es_merma_real = _es_merma(m["motivo"], m["tipo"])
            es_error = (m["motivo"] or "").strip().lower() == "error"

            total_venta = ""

            if m["tipo"] == "ENTRADA":
                n_e += 1
            elif es_venta:
                total_venta = _r2((pu - reb) * cant)
                reb_loc += reb * cant
                venta_loc += total_venta
                n_v += 1
            elif es_merma_real:
                merma_loc += _r2((pu - reb) * cant)
                if es_baja:
                    n_b += 1
                else:
                    n_o += 1
            elif es_baja:
                n_b += 1
            else:
                n_o += 1

            valores = [
                _solo_hora(m["fecha"]), m["local"], m["tipo"],
                m.get("codigo") or "", m["producto"], cant,
                _r2(pu) if pu else "",
                _r2(reb) if es_venta else "",
                total_venta, m["motivo"] or "",
            ]
            for col, val in enumerate(valores, 1):
                c = ws.cell(row=fila, column=col, value=val)
                c.border = BORDE_FINO
                if es_merma_real:
                    c.font = _FONT_MERMA
                elif es_error:
                    c.font = _FONT_ITALIC_GREY
                if col in (1, 2, 3, 4, 6):
                    c.alignment = _ALIGN_CENTER
                elif col in (7, 8, 9):
                    c.alignment = _ALIGN_RIGHT
                    if val != "":
                        c.number_format = _NUM_2DEC
                else:
                    c.alignment = _ALIGN_LEFT

        fila += 1
        etiqueta = (f"TOTAL {local_nombre} — {hoy}  ·  "
                    f"{n_e + n_v + n_b + n_o} movs "
                    f"(E:{n_e} V:{n_v} B:{n_b} O:{n_o})")
        _fila_total(ws, fila, etiqueta, {
            8: (_r2(reb_loc), _NUM_2DEC),
            9: (_r2(venta_loc), _NUM_2DEC),
            10: (f"Merma: ${_r2(merma_loc):,.2f}", None),
        }, col_ini=1, col_fin=10, fill=_FILL_DIA)
        fila += 1

        tot_reb_g += reb_loc
        tot_venta_g += venta_loc
        tot_merma_g += merma_loc
        tot_e_g += n_e
        tot_v_g += n_v
        tot_b_g += n_b
        tot_o_g += n_o

    fila += 1
    etiqueta_g = (f"TOTAL GENERAL — {hoy}  ·  "
                  f"{tot_e_g + tot_v_g + tot_b_g + tot_o_g} movs "
                  f"(E:{tot_e_g} V:{tot_v_g} B:{tot_b_g} O:{tot_o_g})")
    _fila_total(ws, fila, etiqueta_g, {
        8: (_r2(tot_reb_g), _NUM_2DEC),
        9: (_r2(tot_venta_g), _NUM_2DEC),
        10: (f"Merma: ${_r2(tot_merma_g):,.2f}", None),
    }, col_ini=1, col_fin=10, fill=_FILL_TOTAL)

    # FIX #21: guardo la fila del TOTAL GENERAL antes de los fondos
    fila_total_general = fila

    # Tabla de fondos del día (único sitio diario, todos los locales)
    fila += 2
    movs_fondos = _cargar_movs_fondos(
        local_id=None, desde=hoy + " 00:00:00",
        hasta=hoy + " 23:59:59")
    _escribir_tabla_fondos(
        ws, fila, movs_fondos,
        f"FONDOS CUP/USD — Día {hoy} (todos los locales)",
        col_ini=1, col_fin=7, etiqueta_saldo="Neto del día")

    _anchos(ws, [10, 16, 12, 12, 30, 10, 12, 12, 14, 22])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"
    # FIX #21: filtro solo hasta el TOTAL GENERAL, sin arrastrar
    # filas en blanco ni la tabla de fondos.
    ws.auto_filter.ref = f"A{FILA_HEADER}:J{fila_total_general}"


def _hoja_ventas_dia_local(ws, local, hoy):
    _titulo_hoja(ws, 7,
                 f"Ventas del día — {local['nombre']} — {hoy}")
    FILA_HEADER = 3
    _encabezado(ws, FILA_HEADER, [
        "Código", "Producto", "Cantidad",
        "Precio U.", "Rebaja U.", "Total Venta", "Hora",
    ])

    with get_conn() as conn:
        filas = conn.execute(
            "SELECT m.fecha, m.cantidad, m.rebaja, "
            "       m.precio_unitario_momento, "
            "       p.nombre AS producto, p.codigo AS codigo "
            "FROM movimientos m "
            "JOIN productos p ON p.id=m.producto_id "
            "WHERE m.local_id=? AND DATE(m.fecha)=? "
            "AND m.tipo='SALIDA' "
            f"AND {_SQL_VENTA} "
            f"AND {_SQL_NO_FONDO} "
            f"AND {_SQL_NO_ANULADA} "
            "ORDER BY m.fecha ASC, m.id ASC",
            (local["id"], hoy)).fetchall()
    ventas = [dict(r) for r in filas]

    if not ventas:
        fila = FILA_HEADER + 1
        c = ws.cell(row=fila, column=1,
                    value="Sin ventas registradas hoy.")
        c.font = _FONT_ITALIC_GREY
        ws.merge_cells(start_row=fila, start_column=1,
                       end_row=fila, end_column=7)
        _anchos(ws, [12, 32, 10, 12, 10, 14, 10])
        return

    fila = FILA_HEADER
    reb_total = venta_total = qty_total = 0.0
    for m in ventas:
        fila += 1
        cant = float(m["cantidad"] or 0)
        reb = float(m["rebaja"] or 0)
        pu = float(m["precio_unitario_momento"] or 0)
        total = _r2((pu - reb) * cant)
        reb_total += reb * cant
        venta_total += total
        qty_total += cant

        valores = [m.get("codigo") or "", m["producto"], cant,
                   _r2(pu), _r2(reb), total, _solo_hora(m["fecha"])]
        for col, val in enumerate(valores, 1):
            c = ws.cell(row=fila, column=col, value=val)
            c.border = BORDE_FINO
            if col in (1, 3, 7):
                c.alignment = _ALIGN_CENTER
            elif col in (4, 5, 6):
                c.alignment = _ALIGN_RIGHT
                c.number_format = _NUM_2DEC
            else:
                c.alignment = _ALIGN_LEFT

    fila += 1
    _fila_total(
        ws, fila, f"TOTAL DEL DÍA ({len(ventas)} items)",
        valores={
            3: (qty_total, None),
            5: (_r2(reb_total), _NUM_2DEC),
            6: (_r2(venta_total), _NUM_2DEC),
        },
        col_ini=1, col_fin=7, fill=_FILL_TOTAL)

    # FIX #20: sin tabla de fondos (redundante con diario.Resumen)
    _anchos(ws, [12, 32, 10, 12, 10, 14, 10])
    ws.freeze_panes = f"A{FILA_HEADER + 1}"
    ws.auto_filter.ref = f"A{FILA_HEADER}:G{fila}"


# ══════════════════════════════════════════════════════════
# EXPORT 3: SALIDAS DEL DÍA (3 tablas lado a lado por local)
# ══════════════════════════════════════════════════════════
def generar_excel_salidas_hoy(local_id=None) -> bytes:
    hoy = datetime.now().strftime("%Y-%m-%d")
    if local_id is not None and local_id != GENERAL_ID:
        local = loc.obtener_local(local_id)
        if local is None:
            raise ValueError("Local no encontrado")
        locales = [local]
    else:
        locales = loc.listar_locales(solo_activos=True)

    if not locales:
        raise ValueError("No hay locales activos")

    wb = Workbook()
    usados = set()
    primera = True
    for local in locales:
        ws = wb.active if primera else wb.create_sheet()
        primera = False
        ws.title = _sanitizar(local["nombre"], usados)
        _hoja_3_tablas(ws, local, hoy)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _hoja_3_tablas(ws, local, hoy):
    _titulo_hoja(ws, 19,
                 f"{local['nombre']} — Movimientos del día {hoy}")

    TITULO_ROW = 3
    HEADER_ROW = 4
    DATA_ROW   = 5

    with get_conn() as conn:
        filas = conn.execute(
            "SELECT m.fecha, m.tipo, m.cantidad, m.motivo, m.rebaja, "
            "       m.precio_unitario_momento, m.precio_costo_momento, "
            "       p.nombre AS producto, p.codigo AS codigo "
            "FROM movimientos m "
            "JOIN productos p ON p.id=m.producto_id "
            "WHERE m.local_id=? AND DATE(m.fecha)=? "
            "AND m.tipo IN ('ENTRADA','SALIDA','BAJA') "
            f"AND {_SQL_NO_ANULADA} "
            "ORDER BY m.fecha ASC, m.id ASC",
            (local["id"], hoy)).fetchall()
    movs = [dict(r) for r in filas]

    entradas = [m for m in movs if m["tipo"] == "ENTRADA"]
    ventas = [
        m for m in movs
        if m["tipo"] == "SALIDA"
        and _es_venta(m["motivo"])
        and not _es_fondo(m["producto"])
    ]
    ventas_ids = {id(m) for m in ventas}
    otras = [
        m for m in movs
        if m["tipo"] != "ENTRADA" and id(m) not in ventas_ids
    ]

    titulos = [
        (1, 5, "ENTRADAS", _FILL_TITULO_ENTRADA),
        (7, 12, "VENTAS (Combos)", _FILL_TITULO_VENTAS),
        (14, 19, "OTRAS SALIDAS (mermas, movs varios)", _FILL_TITULO_OTRAS),
    ]
    for (start, end, titulo, fill) in titulos:
        ws.cell(row=TITULO_ROW, column=start, value=titulo)
        ws.merge_cells(start_row=TITULO_ROW, start_column=start,
                       end_row=TITULO_ROW, end_column=end)
        for c in range(start, end + 1):
            cell = ws.cell(row=TITULO_ROW, column=c)
            cell.font = _FONT_HEADER
            cell.fill = fill
            cell.alignment = _ALIGN_CENTER
            cell.border = BORDE_FINO
        ws.row_dimensions[TITULO_ROW].height = 22

    h1 = ["Código", "Producto", "Cant.", "Costo U.", "Hora"]
    h2 = ["Código", "Producto", "Cant.", "Precio U.",
          "Rebaja U.", "Total Venta"]
    h3 = ["Código", "Producto", "Cant.", "Motivo", "Tipo", "Monto (CUP)"]
    for start, hs in [(1, h1), (7, h2), (14, h3)]:
        for i, txt in enumerate(hs):
            c = ws.cell(row=HEADER_ROW, column=start + i, value=txt)
            c.font = _FONT_HEADER
            c.fill = _FILL_HEADER
            c.alignment = _ALIGN_CENTER
            c.border = BORDE_FINO

    # Tabla 1: ENTRADAS
    f_ent = DATA_ROW
    sum_prods = 0.0
    n_fondos = 0
    for m in entradas:
        es_fondo = _es_fondo(m["producto"])
        vals = [m.get("codigo") or "", m["producto"],
                float(m["cantidad"] or 0),
                _r2(m["precio_costo_momento"] or 0),
                _solo_hora(m["fecha"])[:5]]
        for i, v in enumerate(vals):
            c = ws.cell(row=f_ent, column=1 + i, value=v)
            c.border = BORDE_FINO
            if i in (0, 2, 4):
                c.alignment = _ALIGN_CENTER
            elif i == 3:
                c.alignment = _ALIGN_RIGHT
                c.number_format = _NUM_2DEC
            else:
                c.alignment = _ALIGN_LEFT
        if es_fondo:
            n_fondos += 1
        else:
            sum_prods += float(m["cantidad"] or 0)
        f_ent += 1

    f_ent += 1
    etiq_ent = f"TOTAL — {len(entradas)} movs"
    if n_fondos:
        etiq_ent += f" ({n_fondos} fondo{'s' if n_fondos > 1 else ''})"
    _fila_total(ws, f_ent, etiq_ent, {
        3: (sum_prods, None),
    }, col_ini=1, col_fin=5, fill=_FILL_TOTAL)

    # Tabla 2: VENTAS
    f_ven = DATA_ROW
    reb_total = venta_total = qty_total = 0.0
    for m in ventas:
        cant = float(m["cantidad"] or 0)
        pu = float(m["precio_unitario_momento"] or 0)
        reb = float(m["rebaja"] or 0)
        total = _r2((pu - reb) * cant)
        reb_total += reb * cant
        venta_total += total
        qty_total += cant
        vals = [m.get("codigo") or "", m["producto"], cant,
                _r2(pu), _r2(reb), total]
        for i, v in enumerate(vals):
            c = ws.cell(row=f_ven, column=7 + i, value=v)
            c.border = BORDE_FINO
            if i in (0, 2):
                c.alignment = _ALIGN_CENTER
            elif i in (3, 4, 5):
                c.alignment = _ALIGN_RIGHT
                c.number_format = _NUM_2DEC
            else:
                c.alignment = _ALIGN_LEFT
        f_ven += 1

    f_ven += 1
    _fila_total(ws, f_ven, f"TOTAL — {len(ventas)} items", {
        9: (qty_total, None),
        11: (_r2(reb_total), _NUM_2DEC),
        12: (_r2(venta_total), _NUM_2DEC),
    }, col_ini=7, col_fin=12, fill=_FILL_TOTAL)

    # Tabla 3: OTRAS SALIDAS
    f_otr = DATA_ROW
    merma_total = 0.0
    merma_rows = 0
    error_rows = 0
    for m in otras:
        cant = float(m["cantidad"] or 0)
        pu = float(m["precio_unitario_momento"] or 0)
        reb = float(m["rebaja"] or 0)
        monto = _r2((pu - reb) * cant)
        motivo = (m["motivo"] or "").strip().lower()
        if motivo == "error":
            tipo_txt = "Error"
            error_rows += 1
        elif _es_merma(m["motivo"], m["tipo"]):
            tipo_txt = "Merma"
            merma_total += monto
            merma_rows += 1
        else:
            tipo_txt = "Movimiento"
        vals = [m.get("codigo") or "", m["producto"], cant,
                m["motivo"] or "", tipo_txt, monto]
        for i, v in enumerate(vals):
            c = ws.cell(row=f_otr, column=14 + i, value=v)
            c.border = BORDE_FINO
            if i in (0, 2, 4):
                c.alignment = _ALIGN_CENTER
                if i == 4:
                    if tipo_txt == "Merma":
                        c.font = _FONT_MERMA
                    elif tipo_txt == "Error":
                        c.font = _FONT_ITALIC_GREY
            elif i == 5:
                c.alignment = _ALIGN_RIGHT
                c.number_format = _NUM_2DEC
                if tipo_txt == "Merma" and monto:
                    c.font = _FONT_MERMA
            else:
                c.alignment = _ALIGN_LEFT
        f_otr += 1

    f_otr += 1
    etiq_otr = f"TOTAL — {len(otras)} movs"
    partes = []
    if merma_rows:
        partes.append(f"{merma_rows} mermas")
    if error_rows:
        partes.append(f"{error_rows} errores")
    if partes:
        etiq_otr += "  ·  " + " · ".join(partes)
    _fila_total(ws, f_otr, etiq_otr,
                valores={19: (_r2(merma_total), _NUM_2DEC)},
                col_ini=14, col_fin=19, fill=_FILL_TOTAL)

    _anchos(ws, [
        12, 26, 8, 12, 8,
        3,
        12, 26, 8, 12, 10, 14,
        3,
        12, 26, 8, 16, 12, 12,
    ])

    ws.freeze_panes = f"A{DATA_ROW}"