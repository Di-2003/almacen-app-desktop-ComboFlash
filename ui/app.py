import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", category=UserWarning, module=r"flet\..*")

import flet as ft
from db import get_conn, get_pref
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
from ui.admin_categorias import vista_admin_categorias
from ui.lista_productos import vista_lista_productos
from ui.pos import vista_pos
from ui.clientes import vista_clientes
from ui.caja import vista_caja
from ui.ordenes import vista_ordenes
from ui.config_negocio import vista_config_negocio
from ui.gastos import vista_gastos
from ui.proveedores import vista_proveedores
from ui._scroll import programar_restauracion


# ============================================================
# Mapa de "vistas hijas": ruta_hija → ruta_padre
# Se usa para decidir si al volver atrás se mantiene el scroll.
# ============================================================
_PADRES = {
    "/clientes":         "/perfil",
    "/caja":             "/perfil",
    "/ordenes":          "/perfil",
    "/proveedores":      "/perfil",
    "/gastos":           "/perfil",
    "/admin-categorias": "/perfil",
    "/admin-locales":    "/perfil",
    "/usuarios":         "/perfil",
    "/umbrales":         "/perfil",
    "/config-negocio":   "/perfil",
    "/lista-productos":  "/dashboard",
}


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
        self._carrito_pos = None

        # Scroll: ruta actual y posiciones guardadas
        self._ruta_actual = None
        self._scroll_positions = {}
        self._scroll_targets = {}

    def iniciar(self):
        try:
            modo = get_pref("tema") or "claro"
        except Exception:
            modo = "claro"
        es.aplicar_tema(modo=modo)

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
        # ── Decidir si mantener scroll de la vista destino ──
        anterior = self._ruta_actual
        self._ruta_actual = ruta

        # Solo mantenemos scroll si venimos DIRECTAMENTE de una
        # vista hija de la ruta actual (botón atrás "real").
        viene_de_hijo = (
            anterior is not None
            and _PADRES.get(anterior) == ruta
        )

        if not viene_de_hijo:
            # Navegación "normal": empezar desde el top.
            self._scroll_positions[ruta] = 0

        # ── Construir la vista ──
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
            elif ruta == "/pos":
                if rol not in ("admin", "almacen"):
                    self.page.views.append(vista_principal(self))
                else:
                    self.page.views.append(vista_pos(self))
            elif ruta == "/dashboard":
                self.page.views.append(vista_dashboard(self))
            elif ruta == "/movimientos":
                self.page.views.append(vista_movimientos(self))
            elif ruta == "/perfil":
                self.page.views.append(vista_perfil(self))
            elif ruta == "/lista-productos":
                self.page.views.append(vista_lista_productos(self))
            elif ruta == "/clientes":
                self.page.views.append(vista_clientes(self))
            elif ruta == "/caja":
                self.page.views.append(vista_caja(self))
            elif ruta == "/ordenes":
                self.page.views.append(vista_ordenes(self))
            elif ruta == "/gastos":
                if rol not in ("admin", "almacen"):
                    self.page.views.append(vista_perfil(self))
                else:
                    self.page.views.append(vista_gastos(self))
            elif ruta == "/proveedores":
                if rol not in ("admin", "almacen"):
                    self.page.views.append(vista_perfil(self))
                else:
                    self.page.views.append(vista_proveedores(self))
            elif ruta == "/config-negocio":
                if rol not in ("admin", "almacen"):
                    self.page.views.append(vista_perfil(self))
                else:
                    self.page.views.append(vista_config_negocio(self))
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
            elif ruta == "/admin-categorias":
                if rol not in ("admin", "almacen"):
                    self.page.views.append(vista_perfil(self))
                else:
                    self.page.views.append(vista_admin_categorias(self))
            else:
                self.page.views.append(vista_principal(self))

        self.page.update()

        # Restaurar scroll si corresponde
        programar_restauracion(self, ruta)

    def _asegurar_local(self):
        if self.local_id is None:
            self.local_id = loc.get_local_actual(self.usuario["username"])

    def es_general(self) -> bool:
        from db import GENERAL_ID
        return self.local_id == GENERAL_ID

    # ============ DRAWER ============

    def abrir_drawer(self):
        from ui.drawer import construir_drawer_panel
        self.cerrar_drawer()

        panel_content = construir_drawer_panel(self)

        # ── Barrier (fondo oscuro) ──
        # Cubre TODA la pantalla, incluida la navigation bar.
        # Click aquí → cerrar drawer.
        barrier = ft.Container(
            bgcolor="#90000000",
            left=0, top=0, right=0, bottom=0,
            on_click=lambda e: self.cerrar_drawer(),
        )

        # ── Panel lateral ──
        # Anclado arriba Y abajo → llega hasta el borde inferior
        # de la pantalla, sin dejar el corte que se veía antes
        # entre la barra de navegación y el panel.
        panel = ft.Container(
            content=panel_content,
            left=0, top=0, bottom=0,
            width=280,
            bgcolor=es.COLOR_SUPERFICIE,
            # Sombra fuerte a la derecha para dar profundidad
            shadow=ft.BoxShadow(
                blur_radius=24, spread_radius=0,
                color="#00000077",
                offset=ft.Offset(6, 0),
            ),
            # Borde derecho tenue que refuerza la separación
            border=ft.Border(
                right=ft.BorderSide(1, "#00000022"),
            ),
        )

        overlay = ft.Stack(
            [barrier, panel],
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
        if self._carrito_pos and self._carrito_pos["items"]:
            self._carrito_pos = None
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
        self._carrito_pos = None
        self._scroll_positions = {}
        self._scroll_targets = {}
        self._ruta_actual = None
        self.ir("/login")