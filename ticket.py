"""
Generación de tickets: PDF 80mm (térmico) + PNG (WhatsApp).
fpdf2 + Pillow.
"""
import io
import warnings
warnings.filterwarnings("ignore", module=r"fpdf\..*")
warnings.filterwarnings("ignore", category=DeprecationWarning)

from datetime import datetime
from fpdf import FPDF
from PIL import Image, ImageDraw, ImageFont

from rutas import RAIZ
from configuracion_negocio import get_todos_negocio
import ventas


TICKETS_DIR = RAIZ / "tickets"

def _asegurar_dir():
    TICKETS_DIR.mkdir(parents=True, exist_ok=True)


def _fmt(v) -> str:
    try:
        return f"{float(v):,.2f}"
    except (TypeError, ValueError):
        return "0.00"


def _fmt_cant(v) -> str:
    f = float(v)
    if f.is_integer():
        return str(int(f))
    return f"{f:g}"


# ── PDF 80 mm ──

def generar_ticket_pdf(orden_id, ancho_mm=80, alto_mm=250) -> bytes:
    orden = ventas.obtener_orden(orden_id)
    if orden is None:
        raise ValueError("Orden no encontrada")
    neg = get_todos_negocio()

    pdf = FPDF(unit="mm", format=(ancho_mm, alto_mm))
    pdf.add_page()
    pdf.set_auto_page_break(False)
    pdf.set_margins(3, 3, 3)

    # Encabezado
    pdf.set_font("Helvetica", "B", size=11)
    pdf.cell(0, 5, neg.get("nombre") or "Almacén", ln=1, align="C")
    pdf.set_font("Helvetica", size=7)
    if neg.get("direccion"):
        pdf.cell(0, 3, neg["direccion"], ln=1, align="C")
    if neg.get("telefono"):
        pdf.cell(0, 3, f"Tel: {neg['telefono']}", ln=1, align="C")
    if neg.get("nit"):
        pdf.cell(0, 3, f"NIT: {neg['nit']}", ln=1, align="C")
    pdf.ln(1)

    pdf.set_font("Helvetica", "B", size=9)
    pdf.cell(0, 4, f"TICKET {orden['numero_ticket']}", ln=1, align="C")
    pdf.set_font("Helvetica", size=7)
    pdf.cell(0, 3, orden["fecha"], ln=1, align="C")
    pdf.cell(0, 3, f"Local: {orden['local_nombre']}", ln=1, align="C")
    if orden.get("cliente_nombre"):
        pdf.cell(0, 3, f"Cliente: {orden['cliente_nombre']}",
                 ln=1, align="C")
    pdf.cell(0, 3, f"Vendedor: {orden['usuario']}", ln=1, align="C")
    pdf.ln(1)
    pdf.cell(0, 1, "-" * 40, ln=1, align="C")
    pdf.ln(0.5)

    # Items
    pdf.set_font("Helvetica", size=7)
    for it in orden["items"]:
        pdf.cell(0, 3, it["nombre"][:34], ln=1)
        linea = (f"  {_fmt_cant(it['cantidad'])} x "
                 f"{_fmt(it['precio_unitario'])}")
        pdf.cell(0, 3, linea, ln=0)
        pdf.cell(0, 3, _fmt(it["importe"]), ln=1, align="R")
        if float(it["rebaja"] or 0) > 0.001:
            pdf.cell(0, 3, f"  Desc/u: -{_fmt(it['rebaja'])}", ln=1)

    pdf.ln(1)
    pdf.cell(0, 1, "-" * 40, ln=1, align="C")
    pdf.ln(0.5)

    pdf.set_font("Helvetica", size=8)
    pdf.cell(0, 3, f"Subtotal: {_fmt(orden['subtotal'])} CUP",
             ln=1, align="R")
    if float(orden["descuento_global"] or 0) > 0:
        pdf.cell(0, 3,
                 f"Descuento: -{_fmt(orden['descuento_global'])} CUP",
                 ln=1, align="R")
    pdf.set_font("Helvetica", "B", size=10)
    pdf.cell(0, 5, f"TOTAL: {_fmt(orden['total'])} CUP",
             ln=1, align="R")
    pdf.ln(1)

    # Pagos
    pdf.set_font("Helvetica", size=7)
    for p in orden["pagos"]:
        pdf.cell(0, 3,
                 f"{p['metodo']}: {_fmt(p['monto'])} {p['moneda']}",
                 ln=1)
        if p["moneda"] != "CUP":
            pdf.cell(0, 3,
                     f"  = {_fmt(p['monto_cup'])} CUP "
                     f"(x{p['tasa']:.2f})", ln=1)

    # Vuelto + saldo pendiente
    if float(orden["vuelto_cup"] or 0) > 0.01:
        pdf.set_font("Helvetica", "B", size=8)
        pdf.cell(0, 4, f"VUELTO: {_fmt(orden['vuelto_cup'])} CUP",
                 ln=1, align="R")
    if float(orden["saldo_pendiente"] or 0) > 0.01:
        pdf.set_font("Helvetica", "B", size=9)
        pdf.cell(0, 5,
                 f"SALDO PENDIENTE: "
                 f"{_fmt(orden['saldo_pendiente'])} CUP",
                 ln=1, align="R")

    pdf.ln(2)
    pdf.set_font("Helvetica", "I", size=7)
    pdf.cell(0, 3, neg.get("eslogan") or "¡Gracias por su compra!",
             ln=1, align="C")

    out = pdf.output(dest="S")
    if isinstance(out, str):
        return out.encode("latin-1")
    return bytes(out)


# ── PNG ──

def generar_ticket_png(orden_id, ancho=440) -> bytes:
    orden = ventas.obtener_orden(orden_id)
    if orden is None:
        raise ValueError("Orden no encontrada")
    neg = get_todos_negocio()

    # Canvas alto inicial, recortamos al final
    alto = 1200
    img = Image.new("RGB", (ancho, alto), "white")
    draw = ImageDraw.Draw(img)

    try:
        f_b = ImageFont.truetype("DejaVuSans-Bold.ttf", 16)
        f = ImageFont.truetype("DejaVuSans.ttf", 12)
        f_s = ImageFont.truetype("DejaVuSans.ttf", 11)
    except Exception:
        f_b = ImageFont.load_default()
        f = ImageFont.load_default()
        f_s = ImageFont.load_default()

    y = 12

    def texto(t, font=None, align="left"):
        nonlocal y
        font = font or f
        bbox = draw.textbbox((0, 0), t, font=font)
        w = bbox[2] - bbox[0]
        h = bbox[3] - bbox[1]
        if align == "center":
            x = (ancho - w) // 2
        elif align == "right":
            x = ancho - w - 12
        else:
            x = 12
        draw.text((x, y), t, font=font, fill="black")
        y += h + 6

    texto(neg.get("nombre") or "Almacén", f_b, "center")
    if neg.get("direccion"):
        texto(neg["direccion"], f_s, "center")
    if neg.get("telefono"):
        texto(f"Tel: {neg['telefono']}", f_s, "center")
    if neg.get("nit"):
        texto(f"NIT: {neg['nit']}", f_s, "center")
    y += 4
    texto(f"TICKET {orden['numero_ticket']}", f_b, "center")
    texto(orden["fecha"], f_s, "center")
    texto(f"Local: {orden['local_nombre']}", f_s, "center")
    if orden.get("cliente_nombre"):
        texto(f"Cliente: {orden['cliente_nombre']}", f_s, "center")
    texto(f"Vendedor: {orden['usuario']}", f_s, "center")
    y += 4
    draw.line([(12, y), (ancho - 12, y)], fill="black")
    y += 6

    for it in orden["items"]:
        texto(it["nombre"][:36], f)
        linea = (f"{_fmt_cant(it['cantidad'])} x "
                 f"{_fmt(it['precio_unitario'])}")
        bbox = draw.textbbox((0, 0), _fmt(it["importe"]), font=f_s)
        w = bbox[2] - bbox[0]
        draw.text((18, y), linea, font=f_s, fill="black")
        draw.text((ancho - w - 12, y), _fmt(it["importe"]),
                  font=f_s, fill="black")
        y += 18
        if float(it["rebaja"] or 0) > 0.001:
            draw.text((18, y), f"  Desc/u: -{_fmt(it['rebaja'])}",
                      font=f_s, fill="#666666")
            y += 16

    y += 4
    draw.line([(12, y), (ancho - 12, y)], fill="black")
    y += 6

    texto(f"Subtotal: {_fmt(orden['subtotal'])} CUP", f_s, "right")
    if float(orden["descuento_global"] or 0) > 0:
        texto(f"Desc: -{_fmt(orden['descuento_global'])} CUP",
              f_s, "right")
    texto(f"TOTAL: {_fmt(orden['total'])} CUP", f_b, "right")
    y += 6

    for p in orden["pagos"]:
        texto(f"{p['metodo']}: {_fmt(p['monto'])} {p['moneda']}", f_s)
        if p["moneda"] != "CUP":
            texto(f"  = {_fmt(p['monto_cup'])} CUP (x{p['tasa']:.2f})",
                  f_s)

    if float(orden["vuelto_cup"] or 0) > 0.01:
        texto(f"VUELTO: {_fmt(orden['vuelto_cup'])} CUP", f_b, "right")
    if float(orden["saldo_pendiente"] or 0) > 0.01:
        texto(f"SALDO PENDIENTE: "
              f"{_fmt(orden['saldo_pendiente'])} CUP", f_b, "right")

    y += 6
    texto(neg.get("eslogan") or "¡Gracias por su compra!",
          f_s, "center")

    # Recortar
    img = img.crop((0, 0, ancho, min(alto, y + 20)))

    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


# ── Guardado en disco ──

def guardar_ticket(orden_id, formato="pdf") -> str:
    _asegurar_dir()
    if formato == "pdf":
        data = generar_ticket_pdf(orden_id)
        ext = "pdf"
    else:
        data = generar_ticket_png(orden_id)
        ext = "png"
    orden = ventas.obtener_orden(orden_id)
    nombre = f"{orden['numero_ticket']}.{ext}"
    ruta = TICKETS_DIR / nombre
    with open(ruta, "wb") as f:
        f.write(data)
    return str(ruta)


def texto_plano_ticket(orden_id) -> str:
    orden = ventas.obtener_orden(orden_id)
    if orden is None:
        return ""
    neg = get_todos_negocio()
    lineas = [neg.get("nombre") or "Almacén"]
    if neg.get("direccion"):
        lineas.append(neg["direccion"])
    if neg.get("telefono"):
        lineas.append(f"Tel: {neg['telefono']}")
    lineas += ["", f"TICKET {orden['numero_ticket']}",
               orden["fecha"], f"Local: {orden['local_nombre']}"]
    if orden.get("cliente_nombre"):
        lineas.append(f"Cliente: {orden['cliente_nombre']}")
    lineas.append(f"Vendedor: {orden['usuario']}")
    lineas.append("-" * 32)
    for it in orden["items"]:
        lineas.append(it["nombre"])
        lineas.append(
            f"  {_fmt_cant(it['cantidad'])} x "
            f"{_fmt(it['precio_unitario'])} = {_fmt(it['importe'])}")
    lineas.append("-" * 32)
    lineas.append(f"Subtotal: {_fmt(orden['subtotal'])} CUP")
    if float(orden["descuento_global"] or 0) > 0:
        lineas.append(f"Desc: -{_fmt(orden['descuento_global'])} CUP")
    lineas.append(f"TOTAL: {_fmt(orden['total'])} CUP")
    for p in orden["pagos"]:
        lineas.append(f"{p['metodo']}: {_fmt(p['monto'])} {p['moneda']}")
    if float(orden["vuelto_cup"] or 0) > 0.01:
        lineas.append(f"VUELTO: {_fmt(orden['vuelto_cup'])} CUP")
    if float(orden["saldo_pendiente"] or 0) > 0.01:
        lineas.append(
            f"SALDO PENDIENTE: {_fmt(orden['saldo_pendiente'])} CUP")
    lineas += ["", neg.get("eslogan") or "¡Gracias por su compra!"]
    return "\n".join(lineas)