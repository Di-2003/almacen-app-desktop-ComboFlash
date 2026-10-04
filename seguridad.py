"""
Hash y verificación de contraseñas.

Usa PBKDF2-HMAC-SHA256 de la librería estándar. Cero dependencias externas.

Formato guardado en la BD (dos columnas separadas):
  - password_hash: el hash en hex
  - salt:          el salt en hex

Para verificar: se recalcula el hash con la contraseña ingresada y el salt
guardado, y se compara en tiempo constante.
"""
import hashlib
import hmac
import os

ITERACIONES   = 200_000   # recomendado OWASP 2023 para PBKDF2-SHA256
LONGITUD_SALT = 16        # 16 bytes = 128 bits
ALGORITMO     = "sha256"


def generar_salt() -> str:
    """Devuelve un salt aleatorio en hex (32 caracteres)."""
    return os.urandom(LONGITUD_SALT).hex()


def hash_password(password: str, salt_hex: str) -> str:
    """Aplica PBKDF2 al password usando el salt dado. Devuelve el hash en hex."""
    salt = bytes.fromhex(salt_hex)
    dk = hashlib.pbkdf2_hmac(
        ALGORITMO,
        password.encode("utf-8"),
        salt,
        ITERACIONES,
    )
    return dk.hex()


def verificar_password(password: str, salt_hex: str,
                       hash_guardado: str) -> bool:
    """Compara en tiempo constante. True si coincide, False si no."""
    calculado = hash_password(password, salt_hex)
    return hmac.compare_digest(calculado, hash_guardado)


def crear_hash(password: str) -> tuple[str, str]:
    """Devuelve (hash_hex, salt_hex) listos para guardar en la BD."""
    salt = generar_salt()
    return hash_password(password, salt), salt