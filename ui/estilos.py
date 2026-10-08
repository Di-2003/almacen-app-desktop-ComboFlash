# ============================================================
# Paletas Almacén Raidel — 5 combinaciones × claro/oscuro
# ============================================================

import warnings
import flet as ft

warnings.filterwarnings("ignore", category=DeprecationWarning)


# ---------- Marca (no cambia con paleta) ----------

COLOR_MARCA_NEGRO       = "#0a0a0a"
COLOR_MARCA_NEGRO_SUAVE = "#1a1a1a"

COLOR_PELIGRO = "#dc2626"
COLOR_EXITO   = "#16a34a"
COLOR_AMBAR   = "#ca8a04"
COLOR_INFO    = "#0284c7"

COLOR_VERDE    = "#22c55e"
COLOR_AMARILLO = "#eab308"
COLOR_ROJO     = "#ef4444"

ORDEN_COLOR = {"rojo": 0, "amarillo": 1, "verde": 2}


# ---------- Paletas (solo cambia el acento) ----------

PALETAS = {
    "dorado": {
        "nombre": "Negro + Dorado",
        "acento_dark":        "#d4af37",
        "acento_light":       "#a8862a",
        "acento_hover_dark":  "#f0d97a",
        "acento_hover_light": "#8a6a1c",
        "acento_suave_dark":  "#2a2008",
        "acento_suave_light": "#fdf6e3",
    },
    "azul": {
        "nombre": "Azul corporativo",
        "acento_dark":        "#3b82f6",
        "acento_light":       "#2563eb",
        "acento_hover_dark":  "#60a5fa",
        "acento_hover_light": "#1d4ed8",
        "acento_suave_dark":  "#0c1e3d",
        "acento_suave_light": "#dbeafe",
    },
    "verde": {
        "nombre": "Verde natural",
        "acento_dark":        "#22c55e",
        "acento_light":       "#16a34a",
        "acento_hover_dark":  "#4ade80",
        "acento_hover_light": "#15803d",
        "acento_suave_dark":  "#052e16",
        "acento_suave_light": "#dcfce7",
    },
    "rojo": {
        "nombre": "Rojo energía",
        "acento_dark":        "#ef4444",
        "acento_light":       "#dc2626",
        "acento_hover_dark":  "#f87171",
        "acento_hover_light": "#b91c1c",
        "acento_suave_dark":  "#450a0a",
        "acento_suave_light": "#fee2e2",
    },
    "purpura": {
        "nombre": "Púrpura moderno",
        "acento_dark":        "#a855f7",
        "acento_light":       "#9333ea",
        "acento_hover_dark":  "#c084fc",
        "acento_hover_light": "#7e22ce",
        "acento_suave_dark":  "#2e1065",
        "acento_suave_light": "#f3e8ff",
    },
}

PALETAS_ORDEN = ["dorado", "azul", "verde", "rojo", "purpura"]


# ---------- Neutros (independientes de la paleta) ----------

_NEUTROS_OSCURO = {
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
    "SOMBRA_CARD":  "#00000099",
    "SOMBRA_SUAVE": "#00000066",
}

_NEUTROS_CLARO = {
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
    "SOMBRA_CARD":  "#0000001a",
    "SOMBRA_SUAVE": "#0000000f",
}


# ---------- Estado ----------

_MODO_ACTUAL   = "oscuro"
_PALETA_ACTUAL = "dorado"


def modo_actual() -> str:
    return _MODO_ACTUAL


def paleta_actual() -> str:
    return _PALETA_ACTUAL


def es_oscuro() -> bool:
    return _MODO_ACTUAL == "oscuro"


def aplicar_tema(modo: str = None, paleta: str = None) -> None:
    """Aplica la combinación paleta + modo. Retro-compatible:
    aplicar_tema('oscuro') sigue funcionando."""
    global _MODO_ACTUAL, _PALETA_ACTUAL
    if paleta is not None and paleta in PALETAS:
        _PALETA_ACTUAL = paleta
    if modo is not None and modo in ("claro", "oscuro"):
        _MODO_ACTUAL = modo

    p = PALETAS[_PALETA_ACTUAL]
    suf = "dark" if _MODO_ACTUAL == "oscuro" else "light"
    neutros = _NEUTROS_OSCURO if _MODO_ACTUAL == "oscuro" else _NEUTROS_CLARO

    for k, v in neutros.items():
        globals()[k] = v

    globals()["COLOR_ACENTO"]       = p[f"acento_{suf}"]
    globals()["COLOR_ACENTO_HOVER"] = p[f"acento_hover_{suf}"]
    globals()["COLOR_ACENTO_SUAVE"] = p[f"acento_suave_{suf}"]

    globals()["GRADIENTE_FONDO"] = (
        [_NEUTROS_OSCURO["COLOR_FONDO"], p["acento_suave_dark"],
         _NEUTROS_OSCURO["COLOR_FONDO"]]
        if _MODO_ACTUAL == "oscuro"
        else [_NEUTROS_CLARO["COLOR_FONDO"], p["acento_suave_light"],
              _NEUTROS_CLARO["COLOR_FONDO"]]
    )


# Compatibilidad: aplicar paleta por defecto al importar
aplicar_tema("oscuro", "dorado")


# ============================================================
# Helpers TextField
# ============================================================

_FALLBACK_BORDE  = "#3a3a3a"
_FALLBACK_ACENTO = "#d4af37"


def borde_textfield(radio: int = 12, color=None, color_foco=None) -> dict:
    color = color or globals().get("COLOR_BORDE_FUERTE") or _FALLBACK_BORDE
    color_foco = (color_foco or globals().get("COLOR_ACENTO")
                  or _FALLBACK_ACENTO)

    outline_cls = getattr(ft, "OutlineInputBorder", None)
    side_cls    = getattr(ft, "BorderSide", None)
    cs_cls      = getattr(ft, "ControlState", None)

    if outline_cls is not None and side_cls is not None:
        if cs_cls is not None:
            try:
                return {"border": {
                    cs_cls.DEFAULT: outline_cls(
                        border_radius=radio,
                        border_side=side_cls(1, color)),
                    cs_cls.FOCUSED: outline_cls(
                        border_radius=radio,
                        border_side=side_cls(2, color_foco)),
                }}
            except Exception:
                pass
        try:
            return {"border": outline_cls(
                border_radius=radio, border_side=side_cls(1, color))}
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
    base = dict(borde_textfield(radio, color, color_foco))
    foco = color_foco or globals().get("COLOR_ACENTO") or _FALLBACK_ACENTO
    base["cursor_color"] = foco
    base["selection_color"] = ft.Colors.with_opacity(0.4, foco)
    base["filled"] = False
    return base


def borde_textfield_none():
    none_cls = getattr(ft, "NoInputBorder", None)
    if none_cls is not None:
        try:
            return none_cls()
        except Exception:
            pass
    outline_cls = getattr(ft, "OutlineInputBorder", None)
    side_cls = getattr(ft, "BorderSide", None)
    if outline_cls is not None and side_cls is not None:
        try:
            return outline_cls(border_side=side_cls(0, "transparent"))
        except Exception:
            pass
    try:
        return ft.InputBorder.NONE
    except Exception:
        return None


def estilo_boton_marca(bgcolor=None, color_texto=None,
                        radio: int = 10) -> ft.ButtonStyle:
    bgcolor = bgcolor or globals().get("COLOR_ACENTO") or _FALLBACK_ACENTO
    if color_texto is None:
        color_texto = "#ffffff"
    return ft.ButtonStyle(
        bgcolor=bgcolor, color=color_texto,
        shape=ft.RoundedRectangleBorder(
            radius=ft.BorderRadius.all(radio)),
    )


# ============================================================
# Monedas
# ============================================================

MONEDAS_INFO = {
    "CUP": {"simbolo": "$",    "etiqueta": "CUP"},
    "USD": {"simbolo": "USD$", "etiqueta": "USD"},
    "EUR": {"simbolo": "€",    "etiqueta": "EUR"},
}


def simbolo_moneda(codigo: str) -> str:
    return MONEDAS_INFO.get(codigo, MONEDAS_INFO["CUP"])["simbolo"]


def etiqueta_moneda(codigo: str) -> str:
    return MONEDAS_INFO.get(codigo, MONEDAS_INFO["CUP"])["etiqueta"]


def texto_moneda(codigo: str) -> str:
    return MONEDAS_INFO.get(codigo, MONEDAS_INFO["CUP"])["simbolo"]