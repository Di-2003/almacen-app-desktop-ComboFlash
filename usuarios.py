"""
Gestión de usuarios. Todas las operaciones de administración exigen
rol admin. Validación en la capa de negocio.
"""
from datetime import datetime
from db import get_conn
from seguridad import crear_hash, verificar_password


class PasswordIncorrecta(Exception):
    pass


class UsuarioYaExiste(Exception):
    pass


def _es_admin(solicitante) -> bool:
    if isinstance(solicitante, dict):
        return solicitante.get("rol") == "admin"
    return False


def _verificar_admin(solicitante) -> None:
    if not _es_admin(solicitante):
        raise PermissionError(
            "Se requiere rol admin para esta operación."
        )


def obtener_usuario(usuario_id: int) -> dict | None:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE id=?", (usuario_id,)
        ).fetchone()
        return dict(row) if row else None


def actualizar_perfil(usuario_id: int,
                      nuevo_username: str,
                      password_actual: str,
                      nuevo_password: str | None = None) -> dict:
    """Actualiza username y/o contraseña del propio usuario."""
    nuevo_username = (nuevo_username or "").strip()
    if not nuevo_username:
        raise ValueError("El nombre de usuario no puede estar vacío")

    with get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM usuarios WHERE id=?", (usuario_id,)
        ).fetchone()
        if row is None:
            raise ValueError("Usuario no encontrado")

        if not verificar_password(password_actual, row["salt"],
                                  row["password_hash"]):
            raise PasswordIncorrecta("La contraseña actual no es correcta")

        if nuevo_username.lower() != row["username"].lower():
            existe = conn.execute(
                "SELECT 1 FROM usuarios WHERE username=? COLLATE NOCASE "
                "AND id<>?",
                (nuevo_username, usuario_id),
            ).fetchone()
            if existe:
                raise UsuarioYaExiste(
                    f"El usuario «{nuevo_username}» ya existe"
                )

        campos = ["username=?"]
        valores: list = [nuevo_username]

        if nuevo_password:
            if len(nuevo_password) < 4:
                raise ValueError(
                    "La nueva contraseña debe tener al menos 4 caracteres"
                )
            h, s = crear_hash(nuevo_password)
            campos.append("password_hash=?")
            campos.append("salt=?")
            valores.append(h)
            valores.append(s)

        valores.append(usuario_id)
        conn.execute(
            f"UPDATE usuarios SET {', '.join(campos)} WHERE id=?",
            tuple(valores),
        )

    return {
        "id": usuario_id,
        "username": nuevo_username,
        "rol": row["rol"],
    }


# ================= GESTIÓN (solo admin) =================

def listar_usuarios(solicitante) -> list[dict]:
    _verificar_admin(solicitante)
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT id, username, rol, activo, creado "
            "FROM usuarios ORDER BY username COLLATE NOCASE"
        ).fetchall()
        return [dict(r) for r in rows]


def crear_usuario(username: str, password: str, rol: str,
                  solicitante) -> int:
    _verificar_admin(solicitante)

    username = (username or "").strip()
    if not username:
        raise ValueError("El nombre de usuario no puede estar vacío")
    if len(username) < 3:
        raise ValueError("El nombre debe tener al menos 3 caracteres")
    if len(password) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres")
    if rol not in ("admin", "almacen", "comun"):
        raise ValueError(f"Rol inválido: {rol}")

    with get_conn() as conn:
        existe = conn.execute(
            "SELECT 1 FROM usuarios WHERE username=? COLLATE NOCASE",
            (username,),
        ).fetchone()
        if existe:
            raise UsuarioYaExiste(f"El usuario «{username}» ya existe")

        h, s = crear_hash(password)
        cur = conn.execute(
            "INSERT INTO usuarios(username,password_hash,salt,rol,activo,"
            "creado) VALUES(?,?,?,?,1,?)",
            (username, h, s, rol,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
        )
        return cur.lastrowid


def cambiar_rol(usuario_id: int, nuevo_rol: str, solicitante) -> None:
    _verificar_admin(solicitante)
    if nuevo_rol not in ("admin", "almacen", "comun"):
        raise ValueError(f"Rol inválido: {nuevo_rol}")
    with get_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET rol=? WHERE id=?",
            (nuevo_rol, usuario_id),
        )


def activar_usuario(usuario_id: int, activo: bool, solicitante) -> None:
    _verificar_admin(solicitante)
    with get_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET activo=? WHERE id=?",
            (1 if activo else 0, usuario_id),
        )


def resetear_password(usuario_id: int, nueva_password: str,
                      solicitante) -> None:
    _verificar_admin(solicitante)
    if len(nueva_password) < 4:
        raise ValueError("La contraseña debe tener al menos 4 caracteres")
    h, s = crear_hash(nueva_password)
    with get_conn() as conn:
        conn.execute(
            "UPDATE usuarios SET password_hash=?, salt=? WHERE id=?",
            (h, s, usuario_id),
        )


def eliminar_usuario(usuario_id: int, usuario_actual_id: int,
                    solicitante) -> None:
    _verificar_admin(solicitante)
    if usuario_id == usuario_actual_id:
        raise ValueError("No puedes eliminar tu propio usuario")
    with get_conn() as conn:
        row = conn.execute(
            "SELECT rol FROM usuarios WHERE id=?", (usuario_id,)
        ).fetchone()
        if row and row["rol"] == "admin":
            admins_activos = conn.execute(
                "SELECT COUNT(*) AS n FROM usuarios "
                "WHERE rol='admin' AND activo=1 AND id<>?",
                (usuario_id,),
            ).fetchone()["n"]
            if admins_activos == 0:
                raise ValueError(
                    "No puedes eliminar al último administrador activo"
                )
        conn.execute("DELETE FROM usuarios WHERE id=?", (usuario_id,))