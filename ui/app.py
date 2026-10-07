import flet as ft
from db import get_conn
import locales as loc
from ui import estilos as es
from ui.login import vista_login, vista_primer_arranque
from ui.principal import vista_principal
from ui.dashboard import vista_dashboard
from ui.movimientos import vista_movimientos
from ui.perfil import vista_perfil
from ui.umbrales import vista_umbrales
from ui.admin_usuarios import vista_usuarios
from ui.admin_locales import vista_admin_locales
from ui.lista_productos import vista_lista_productos


class AlmacenApp:
    def __init__(self, page):
        self.page = page
        self.usuario = None
        self.local_id = None
        self.filtro = ""
        self.filtro_tipo = None
        self.lista_titulo = ""
        self.lista_filtro = "todos"
        self.periodo_dashboard = "mes"
        self._drawer_overlay = None

    def iniciar(self):
        self.page.on_route_change = self._on_route_change
        with get_conn() as conn:
            hay = conn.execute(
                "SELECT 1 FROM usuarios LIMIT 1"
            ).fetchone()
        ruta = "/primer-arranque" if not hay else "/login"
        self.page.run_task(self.page.push_route, ruta)

    def _on_route_change(self, e):
        self.cerrar_drawer()
        self._construir_vista(self.page.route)

    def _construir_vista(self, ruta):
        self.page.views.clear()

        if ruta == "/primer-arranque":
            self.page.views.append(vista_primer_arranque(self))
        elif ruta == "/login" or not self.usuario:
            self.page.views.append(vista_login(self))
        else:
            self._asegurar_local()
            rol = self.usuario["rol"]

            if ruta == "/principal":
                self.page.views.append(vista_principal(self))
            elif ruta == "/dashboard":
                self.page.views.append(vista_dashboard(self))
            elif ruta == "/movimientos":
                self.page.views.append(vista_movimientos(self))
            elif ruta == "/perfil":
                self.page.views.append(vista_perfil(self))
            elif ruta == "/lista-productos":
                self.page.views.append(vista_lista_productos(self))
            elif ruta == "/umbrales":
                if rol not in ("admin", "almacen"):
                    self.page.views.append(vista_perfil(self))
                else:
                    self.page.views.append(vista_umbrales(self))
            elif ruta == "/usuarios":
                if rol != "admin":
                    self.page.views.append(vista_perfil(self))
                else:
                    self.page.views.append(vista_usuarios(self))
            elif ruta == "/admin-locales":
                if rol != "admin":
                    self.page.views.append(vista_perfil(self))
                else:
                    self.page.views.append(vista_admin_locales(self))
            else:
                self.page.views.append(vista_principal(self))

        self.page.update()

    def _asegurar_local(self):
        if self.local_id is None:
            self.local_id = loc.get_local_actual(self.usuario["username"])

    def es_general(self) -> bool:
        from db import GENERAL_ID
        return self.local_id == GENERAL_ID

    # ============ DRAWER (Stack + barrier manual) ============

    def abrir_drawer(self):
        from ui.drawer import construir_drawer_panel
        self.cerrar_drawer()

        # Panel lateral
        panel_content = construir_drawer_panel(self)

        panel = ft.Container(
            content=panel_content,
            width=280,
            bgcolor=es.COLOR_SUPERFICIE,
            expand=True,
        )

        # Barrier transparente (captura clicks fuera del panel)
        barrier = ft.Container(
            bgcolor="#90000000",
            expand=True,
            on_click=lambda e: self.cerrar_drawer(),
        )

        # Stack: barrier abajo, panel encima alineado a la izquierda
        overlay = ft.Stack(
            [
                barrier,
                ft.Row(
                    [panel, ft.Container(expand=True)],
                    spacing=0,
                    expand=True,
                    vertical_alignment=ft.CrossAxisAlignment.START,
                ),
            ],
            expand=True,
        )

        self._drawer_overlay = overlay
        try:
            self.page.overlay.append(overlay)
            self.page.update()
        except Exception as ex:
            print(f"[DRAWER] error al abrir: {ex}")

    def cerrar_drawer(self):
        if self._drawer_overlay is None:
            return
        try:
            if self._drawer_overlay in self.page.overlay:
                self.page.overlay.remove(self._drawer_overlay)
        except Exception:
            pass
        try:
            self.page.update()
        except Exception:
            pass
        self._drawer_overlay = None

    # ============ NAVEGACIÓN ============

    def cambiar_local(self, local_id: int):
        import inventario as inv
        inv.invalidar_cache()
        self.local_id = local_id
        self.filtro = ""
        self.filtro_tipo = None
        loc.set_local_actual(self.usuario["username"], local_id)
        self.refrescar()

    def set_filtro_tipo(self, categoria_id):
        self.filtro_tipo = categoria_id
        self.refrescar()

    def abrir_lista(self, filtro: str, titulo: str):
        self.lista_filtro = filtro
        self.lista_titulo = titulo
        self.ir("/lista-productos")

    def ir(self, ruta):
        self.page.run_task(self.page.push_route, ruta)

    def refrescar(self):
        self._construir_vista(self.page.route)

    def cerrar_sesion(self):
        import inventario as inv
        inv.invalidar_cache()
        self.usuario = None
        self.local_id = None
        self.filtro = ""
        self.filtro_tipo = None
        self.periodo_dashboard = "mes"
        self.ir("/login")