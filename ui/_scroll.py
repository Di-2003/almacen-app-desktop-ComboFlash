"""
Helper para preservar la posición de scroll entre navegaciones.

Solo se restaura el scroll cuando vuelves DESDE UNA VISTA HIJA
(p. ej. Perfil → Clientes → Perfil). Si navegas entre vistas
"principales" (Inicio ↔ Perfil ↔ Dashboard), el scroll arranca
en el top como en cualquier app.
"""
import flet as ft


def columna_scroll(ruta: str, app, controls: list, **kwargs) -> ft.Column:
    """Column scrolleable que memoriza su posición."""
    key = f"scroll__{ruta.strip('/')}"

    def _on_scroll(e):
        try:
            offset = getattr(e, "pixels", None)
            if offset is None:
                offset = getattr(e, "scroll_offset", None)
            if offset is None:
                offset = 0
            app._scroll_positions[ruta] = float(offset)
        except Exception:
            pass

    col = ft.Column(
        controls=controls,
        scroll=ft.ScrollMode.AUTO,
        key=key,
        on_scroll=_on_scroll,
        expand=True,
        **kwargs,
    )

    if not hasattr(app, "_scroll_targets"):
        app._scroll_targets = {}
    app._scroll_targets[ruta] = col

    return col


def programar_restauracion(app, ruta: str) -> None:
    """
    Restaura el scroll de `ruta` sin delay perceptible.
    Solo se llama cuando la navegación lo amerita (lo decide app.py).
    """
    offset = getattr(app, "_scroll_positions", {}).get(ruta, 0)
    if offset <= 0:
        return

    async def _restore():
        import asyncio
        # Un solo tick para que el árbol se monte — sin salto visible
        await asyncio.sleep(0)
        try:
            target = getattr(app, "_scroll_targets", {}).get(ruta)
            if target is not None:
                await target.scroll_to(offset=offset, duration=0)
        except Exception as ex:
            print(f"[scroll] error restaurando {ruta}: {ex}")

    try:
        app.page.run_task(_restore)
    except Exception:
        pass