# ============================================================
# Paleta Almacén Raidel (móvil) — Negro + Dorado
# ============================================================
#
# Todos los colores se acceden como `es.COLOR_X`. Para cambiar de
# tema en runtime, se llama a `es.aplicar_tema("oscuro"|"claro")`.
# ============================================================

import warnings
import flet as ft

# Flet 1.0.3 emite DeprecationWarning al usar propiedades viejas
# (border_radius, border_color, InputBorder.*). Estos helpers las
# usan como fallback cuando la API nueva no está disponible. Como
# no podemos migrar a la API nueva sin romper compatibilidad,
# silenciamos los avisos a nivel de módulo.
warnings.filterwarnings("ignore", category=DeprecationWarning)


# ---------- Colores de marca (no cambian con el tema) ----------

COLOR_MARCA_DORADO          = "#d4af37"
COLOR_MARCA_DORADO_CLARO    = "#f0d97a"
COLOR_MARCA_DORADO_OSCURO   = "#a8862a"
COLOR_MARCA_DORADO_SUAVE    = "#fdf6e3"
COLOR_MARCA_NEGRO           = "#0a0a0a"
COLOR_MARCA_NEGRO_SUAVE     = "#1a1a1a"

COLOR_PELIGRO = "#dc2626"
COLOR_EXITO   = "#16a34a"
COLOR_AMBAR   = "#ca8a04"
COLOR_INFO    = "#0284c7"

COLOR_VERDE    = "#22c55e"
COLOR_AMARILLO = "#eab308"
COLOR_ROJO     = "#ef4444"

ORDEN_COLOR = {"rojo": 0, "amarillo": 1, "verde": 2}


# ---------- Paletas ----------

_PALETA_OSCURO = {
    "COLOR_FONDO":         "#0a0a0a",
    "COLOR_SUPERFICIE":    "#141414",
    "COLOR_SUPERFICIE_2":  "#1e1e1e",
    "COLOR_BORDE":         "#2a2a2a",
    "COLOR_BORDE_FUERTE":  "#3a3a3a",
    "COLOR_TEXTO":         "#f5f5f5",
    "COLOR_TEXTO_SUAVE":   "#a3a3a3",
    "COLOR_TEXTO_TENUE":   "#6b6b6b",
    "COLOR_PELIGRO_SUAVE": "#450a0a",
    "COLOR_EXITO_SUAVE":   "#052e16",
    "COLOR_AMBAR_SUAVE":   "#422006",
    "COLOR_INFO_SUAVE":    "#082f49",
    "COLOR_ESTADO_FONDO": {
        "verde":    "#052e16",
        "amarillo": "#422006",
        "rojo":     "#450a0a",
    },
    "COLOR_ESTADO_TEXTO": {
        "verde":    "#86efac",
        "amarillo": "#fde68a",
        "rojo":     "#fca5a5",
    },
    "COLOR_ESTADO_BORDE": {
        "verde":    "#166534",
        "amarillo": "#854d0e",
        "rojo":     "#991b1b",
    },
    "SOMBRA_CARD":         "#00000099",
    "SOMBRA_SUAVE":        "#00000066",
    "GRADIENTE_FONDO":     ["#0a0a0a", "#1a1408", "#2a1f08"],
    "COLOR_ACENTO":        COLOR_MARCA_DORADO,
    "COLOR_ACENTO_HOVER":  COLOR_MARCA_DORADO_CLARO,
    "COLOR_ACENTO_SUAVE":  "#2a2008",
}

_PALETA_CLARO = {
    "COLOR_FONDO":         "#fafaf7",
    "COLOR_SUPERFICIE":    "#ffffff",
    "COLOR_SUPERFICIE_2":  "#f5f4ef",
    "COLOR_BORDE":         "#e5e3dc",
    "COLOR_BORDE_FUERTE":  "#c9c5b8",
    "COLOR_TEXTO":         "#0a0a0a",
    "COLOR_TEXTO_SUAVE":   "#57534e",
    "COLOR_TEXTO_TENUE":   "#a8a29e",
    "COLOR_PELIGRO_SUAVE": "#fee2e2",
    "COLOR_EXITO_SUAVE":   "#dcfce7",
    "COLOR_AMBAR_SUAVE":   "#fef9c3",
    "COLOR_INFO_SUAVE":    "#e0f2fe",
    "COLOR_ESTADO_FONDO": {
        "verde":    "#dcfce7",
        "amarillo": "#fef3c7",
        "rojo":     "#fee2e2",
    },
    "COLOR_ESTADO_TEXTO": {
        "verde":    "#166534",
        "amarillo": "#854d0e",
        "rojo":     "#991b1b",
    },
    "COLOR_ESTADO_BORDE": {
        "verde":    "#86efac",
        "amarillo": "#fde68a",
        "rojo":     "#fca5a5",
    },
    "SOMBRA_CARD":         "#0000001a",
    "SOMBRA_SUAVE":        "#0000000f",
    "GRADIENTE_FONDO":     ["#fafaf7", "#f5edd5", "#e8d9a8"],
    "COLOR_ACENTO":        COLOR_MARCA_DORADO_OSCURO,
    "COLOR_ACENTO_HOVER":  "#8a6a1c",
    "COLOR_ACENTO_SUAVE":  COLOR_MARCA_DORADO_SUAVE,
}


# ---------- Estado del tema ----------

_MODO_ACTUAL = "oscuro"


def modo_actual() -> str:
    return _MODO_ACTUAL


def es_oscuro() -> bool:
    return _MODO_ACTUAL == "oscuro"


def aplicar_tema(modo: str) -> None:
    """Cambia la paleta global y reasigna los colores del módulo."""
    global _MODO_ACTUAL
    if modo not in ("claro", "oscuro"):
        modo = "oscuro"
    _MODO_ACTUAL = modo
    paleta = _PALETA_OSCURO if modo == "oscuro" else _PALETA_CLARO
    for nombre, valor in paleta.items():
        globals()[nombre] = valor


aplicar_tema("oscuro")


# ============================================================
# Helpers de compatibilidad para TextField
# ============================================================
#
# Estrategia: intentar la API nueva (OutlineInputBorder) y, si
# falla, caer a la API vieja. Los DeprecationWarning ya están
# silenciados arriba, así que aunque usemos la API vieja no
# aparece ruido en consola.
# ============================================================

_FALLBACK_BORDE  = "#3a3a3a"
_FALLBACK_ACENTO = "#d4af37"


def borde_textfield(radio: int = 12, color=None, color_foco=None) -> dict:
    """kwargs de borde para TextField y Dropdown. Solo borde.

    No incluye cursor_color ni selection_color porque Dropdown los
    rechaza en Flet 1.0.3.
    """
    color = color or globals().get("COLOR_BORDE_FUERTE") or _FALLBACK_BORDE
    color_foco = (color_foco
                  or globals().get("COLOR_ACENTO")
                  or _FALLBACK_ACENTO)

    outline_cls = getattr(ft, "OutlineInputBorder", None)
    side_cls    = getattr(ft, "BorderSide", None)
    cs_cls      = getattr(ft, "ControlState", None)

    if outline_cls is not None and side_cls is not None:
        if cs_cls is not None:
            try:
                return {
                    "border": {
                        cs_cls.DEFAULT: outline_cls(
                            border_radius=radio,
                            border_side=side_cls(1, color),
                        ),
                        cs_cls.FOCUSED: outline_cls(
                            border_radius=radio,
                            border_side=side_cls(2, color_foco),
                        ),
                    },
                }
            except Exception:
                pass

        try:
            return {
                "border": outline_cls(
                    border_radius=radio,
                    border_side=side_cls(1, color),
                ),
            }
        except Exception:
            pass

        try:
            return {"border": outline_cls(border_radius=radio)}
        except Exception:
            pass

    return {
        "border_color": color,
        "focused_border_color": color_foco,
        "border_radius": radio,
        "border_width": 1,
        "focused_border_width": 2,
    }

def estilo_textfield(radio: int = 12, color=None, color_foco=None) -> dict:
    """kwargs completos para TextField: borde + cursor + selection.

    Úsalo solo con ft.TextField (no con Dropdown).
    """
    base = dict(borde_textfield(radio, color, color_foco))
    foco = (color_foco
            or globals().get("COLOR_ACENTO")
            or _FALLBACK_ACENTO)
    base["cursor_color"] = foco
    base["selection_color"] = ft.Colors.with_opacity(0.4, foco)
    base["filled"] = False
    return base


def borde_textfield_none():
    """Valor para TextField sin borde."""
    none_cls = getattr(ft, "NoInputBorder", None)
    if none_cls is not None:
        try:
            return none_cls()
        except Exception:
            pass

    outline_cls = getattr(ft, "OutlineInputBorder", None)
    side_cls    = getattr(ft, "BorderSide", None)
    if outline_cls is not None and side_cls is not None:
        try:
            return outline_cls(border_side=side_cls(0, "transparent"))
        except Exception:
            pass

    # Fallback API vieja
    try:
        return ft.InputBorder.NONE
    except Exception:
        return None


# ============================================================
# Helper de estilo para botones con la marca
# ============================================================

def estilo_boton_marca(bgcolor=None, color_texto=None,
                    radio: int = 10) -> ft.ButtonStyle:
    """ButtonStyle dorado de marca (o el color indicado)."""
    bgcolor = bgcolor or globals().get("COLOR_ACENTO") or _FALLBACK_ACENTO
    if color_texto is None:
        color_texto = COLOR_MARCA_NEGRO
    return ft.ButtonStyle(
        bgcolor=bgcolor,
        color=color_texto,
        shape=ft.RoundedRectangleBorder(
            radius=ft.BorderRadius.all(radio)),
    )
    
