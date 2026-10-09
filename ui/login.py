"""
Login y primer arranque.
"""
from datetime import datetime
import flet as ft
from db import get_conn
from seguridad import verificar_password, crear_hash
from ui import estilos as es
from ui.componentes import snack, ruta_asset, imagen_opcional


def _logo(size=160):
    fallback = ft.Container(
        content=ft.Icon(ft.Icons.INVENTORY_2,
                        size=int(size * 0.55),
                        color=es.COLOR_ACENTO),
        width=size, height=size,
        alignment=ft.Alignment.CENTER,
    )
    return imagen_opcional(
        "icon.png", fallback,
        width=size, height=size,
    )


def _fondo_degradado(contenido: ft.Control,
                    imagen_bg: str | None = None) -> ft.Container:
    gradiente = ft.Container(
        expand=True,
        gradient=ft.LinearGradient(
            begin=ft.Alignment.TOP_CENTER,
            end=ft.Alignment.BOTTOM_CENTER,
            colors=es.GRADIENTE_FONDO,
        ),
    )

    fondo = gradiente
    if imagen_bg:
        fondo = imagen_opcional(imagen_bg, gradiente,
                                fit=ft.BoxFit.COVER)

    return ft.Container(
        content=ft.Stack(
            [
                fondo,
                ft.Container(
                    content=ft.Container(
                        content=contenido,
                        padding=ft.Padding.symmetric(
                            horizontal=20, vertical=20),
                        expand=True,
                        alignment=ft.Alignment.CENTER,
                    ),
                    expand=True,
                ),
            ],
        ),
        expand=True,
    )


def _estilo_textfield():
    return {
        **es.estilo_textfield(radio=12),
        "height": 56,
    }


def _caja_login(titulo, subtitulo: str, campos: list,
                boton_texto: str, boton_icono, on_click) -> ft.Container:
    if isinstance(titulo, ft.Text):
        titulo_widget = titulo
    else:
        titulo_widget = ft.Text(
            titulo, size=26, weight=ft.FontWeight.BOLD,
            text_align=ft.TextAlign.CENTER,
            color=es.COLOR_TEXTO)

    tarjeta = ft.Container(
        content=ft.Column(
            [
                ft.Row([_logo(160)],
                       alignment=ft.MainAxisAlignment.CENTER),
                ft.Container(height=6),
                titulo_widget,
                ft.Text(subtitulo, size=13,
                        color=es.COLOR_TEXTO_SUAVE,
                        text_align=ft.TextAlign.CENTER),
                ft.Container(height=24),
                *campos,
                ft.Container(height=14),
                ft.FilledButton(
                    boton_texto, icon=boton_icono,
                    on_click=on_click,
                    width=10000, height=52,
                    style=ft.ButtonStyle(
                        bgcolor=es.COLOR_ACENTO,
                        color="#ffffff",
                        shape=ft.RoundedRectangleBorder(
                            radius=ft.BorderRadius.all(12)),
                    ),
                ),
            ],
            spacing=12,
            horizontal_alignment=ft.CrossAxisAlignment.STRETCH,
        ),
        padding=28,
        bgcolor=es.COLOR_SUPERFICIE,
        border_radius=20,
        border=ft.Border.all(1, es.COLOR_BORDE),
        shadow=ft.BoxShadow(
            blur_radius=30, spread_radius=0,
            color=es.SOMBRA_CARD,
            offset=ft.Offset(0, 8),
        ),
    )
    return tarjeta


def vista_primer_arranque(app):
    page = app.page
    est = _estilo_textfield()

    tf_user = ft.TextField(
        label="Usuario", value="admin",
        prefix_icon=ft.Icons.PERSON,
        **est,
    )
    tf_pass = ft.TextField(
        label="Contraseña", password=True, can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK,
        **est,
    )
    tf_pass2 = ft.TextField(
        label="Repetir contraseña", password=True, can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK,
        **est,
    )
    tf_user.autofocus = True

    def crear(e):
        user = (tf_user.value or "").strip()
        p1 = tf_pass.value or ""
        p2 = tf_pass2.value or ""
        if not user:
            snack(page, "El usuario no puede estar vacío", "error")
            return
        if len(p1) < 4:
            snack(page, "Mínimo 4 caracteres", "error")
            return
        if p1 != p2:
            snack(page, "No coinciden", "error")
            return
        h, s = crear_hash(p1)
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO usuarios(username,password_hash,salt,"
                "rol,creado) VALUES(?,?,?,'admin',?)",
                (user, h, s,
                 datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        app.ir("/login")

    caja = _caja_login(
        titulo="Almacen",
        subtitulo="Crea tu administrador para comenzar",
        campos=[tf_user, tf_pass, tf_pass2],
        boton_texto="Crear administrador",
        boton_icono=ft.Icons.CHECK,
        on_click=crear,
    )

    return ft.View(
        route="/primer-arranque",
        controls=[_fondo_degradado(caja, imagen_bg="signin_bg.png")],
        bgcolor=es.COLOR_FONDO,
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )


def vista_login(app):
    page = app.page
    est = _estilo_textfield()

    titulo_login = ft.Text(
        "Almacen",
        size=26, weight=ft.FontWeight.BOLD,
        text_align=ft.TextAlign.CENTER,
        color=es.COLOR_TEXTO,
    )

    tf_user = ft.TextField(
        label="Usuario", prefix_icon=ft.Icons.PERSON,
        autofocus=True,
        **est,
    )
    tf_pass = ft.TextField(
        label="Contraseña", password=True, can_reveal_password=True,
        prefix_icon=ft.Icons.LOCK,
        **est,
    )

    def actualizar_titulo(e=None):
        u = (tf_user.value or "").strip()
        titulo_login.value = f"Almacen {u}" if u else "Almacen"
        try:
            titulo_login.update()
        except Exception:
            pass

    tf_user.on_change = actualizar_titulo

    def ingresar(e):
        user = (tf_user.value or "").strip()
        pwd = tf_pass.value or ""
        if not user or not pwd:
            snack(page, "Completa los campos", "error")
            return
        with get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM usuarios WHERE username=? AND activo=1",
                (user,)).fetchone()
        if row is None or not verificar_password(
                pwd, row["salt"], row["password_hash"]):
            snack(page, "Datos incorrectos", "error")
            tf_pass.value = ""
            page.update()
            return
        app.usuario = {"id": row["id"], "username": row["username"],
                    "rol": row["rol"]}
        app.ir("/principal")

    tf_pass.on_submit = ingresar

    caja = _caja_login(
        titulo=titulo_login,
        subtitulo="Inicia sesión para continuar",
        campos=[tf_user, tf_pass],
        boton_texto="Ingresar",
        boton_icono=ft.Icons.LOGIN,
        on_click=ingresar,
    )

    return ft.View(
        route="/login",
        controls=[_fondo_degradado(caja, imagen_bg="login_bg.png")],
        bgcolor=es.COLOR_FONDO,
        vertical_alignment=ft.MainAxisAlignment.CENTER,
        horizontal_alignment=ft.CrossAxisAlignment.CENTER,
    )