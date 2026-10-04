# recursos/

Assets de la app. **Todas las imágenes son opcionales.**

## Imágenes esperadas

| Archivo         | Uso                                                                            | Tamaño                         |
| --------------- | ------------------------------------------------------------------------------ | ------------------------------ |
| `icon.png`      | Logo del launcher y de la app (login, appbar, perfil)                          | 1024×1024 px, PNG transparente |
| `login_bg.png`  | Fondo del login                                                                | 1080×1920 px                   |
| `signin_bg.png` | Fondo del primer arranque                                                      | 1080×1920 px                   |
| `splash.png`    | Splash screen (opcional, requiere descomentar en `main.py` y `pyproject.toml`) | 1080×1920 px                   |

## Probar en VSCode

1. Copia las imágenes con el nombre exacto de la tabla.
2. `flet run`.
3. Cambia entre pantallas (login → principal → perfil) para verlas.

Si quitas una imagen, la app cae automáticamente al fallback (gradiente dorado, ícono genérico).
