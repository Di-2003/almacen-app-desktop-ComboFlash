import flet as ft
from db import get_conn
import locales as loc
from ui.login import vista_login, vista_primer_arranque
from ui.principal import vista_principal
from ui.dashboard import vista_dashboard
from ui.movimientos import vista_movimientos
from ui.perfil import vista_perfil
from ui.umbrales import vista_umbrales
from ui.admin_usuarios import vista_usuarios
from ui.admin_locales import vista_admin_locales


class AlmacenApp:
    def __init__(self, page):
        self.page = page
        self.usuario = None
        self.local_id = None
        self.filtro = ""
        self.ver_inactivos = False

    def iniciar(self):
        self.page.on_route_change = self._on_route_change
        with get_conn() as conn:
            hay = conn.execute(
                "SELECT 1 FROM usuarios LIMIT 1"
            ).fetchone()
        ruta = "/primer-arranque" if not hay else "/login"
        self.page.run_task(self.page.push_route, ruta)

    def _on_route_change(self, e):
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

    def cambiar_local(self, local_id: int):
        self.local_id = local_id
        self.filtro = ""
        self.ver_inactivos = False
        loc.set_local_actual(self.usuario["username"], local_id)
        self.refrescar()

    def ir(self, ruta):
        self.page.run_task(self.page.push_route, ruta)

    def refrescar(self):
        self._construir_vista(self.page.route)

    def cerrar_sesion(self):
        self.usuario = None
        self.local_id = None
        self.filtro = ""
        self.ver_inactivos = False
        self.ir("/login")