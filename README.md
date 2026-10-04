# Almacén Raidel — App móvil (Combos Flash)

Port móvil de **`almacen_app_Raidel`** (Python + PySide6 desktop) usando la
UI/UX, el patrón de proyecto y el pipeline de compilación de
**`almacen_movil_2`** (Python + Flet 1.0.3 Android).

**Objetivo**: app Android-only, offline-first, que replique toda la
lógica multi-local de `almacen_app_Raidel` (Almacén + tiendas + vista
General, códigos por local, traspasos, rebaja por unidad, propagación
de precios/códigos/nombres, Excel con hojas fijas + una por local,
cierre de tienda con histórico) con la experiencia de usuario de
`almacen_movil_2` (bottom nav, bottom sheet, cards, snack) y una
paleta **negra + dorada**.

---

## 1. Decisiones cerradas

| #   | Tema                                 | Decisión                                                                                                                                                                                    |
| --- | ------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1   | Motivos de salida                    | **Texto libre** (como `almacen_movil_2`). Default sugerido configurable.                                                                                                                    |
| 2   | "Dar de baja" vs "Salida con motivo" | **Ambas coexisten**. Baja = producto descatalogado. Salida = movimiento puntual.                                                                                                            |
| 3   | Propagación                          | **TODO propaga a todos los locales** (precio costo, precio venta, código, renombrado).                                                                                                      |
| 4   | Selector de local                    | **AppBar → bottom sheet** con la lista completa (General + Almacén + tiendas).                                                                                                              |
| 5   | Traspaso                             | **Ambos accesos**: botón en AppBar (rápido) + acción dentro del bottom sheet de un producto.                                                                                                |
| 6   | Excel                                | **Un solo botón "Exportar Excel"** que genera: hojas fijas + una hoja por cada local (activo o histórico cerrado). Al cerrar un local, sus hojas quedan guardadas con los datos que tenían. |
| 7   | Export/Import BD                     | **Sí**. Desde Perfil. FilePicker deja elegir dónde guardar/leer el `.db`.                                                                                                                   |
| 8   | Filtros en Inicio                    | Solo filtros lógicos: **búsqueda por nombre/código** + **toggle activos/inactivos**. El filtro por color vive en el Dashboard (4 tarjetas → 4 listas).                                      |
| 9   | Códigos                              | Formato **`F` + letra + 4 dígitos** (`FA0001`…`FA9999` → `FB0001`…). Se auto-sugiere al crear entrada. Orden natural por (letra, número).                                                   |

### Decisiones secundarias (defaults)

| #   | Tema                                             | Default                                                          |
| --- | ------------------------------------------------ | ---------------------------------------------------------------- |
| 10  | Código en el listado                             | Badge pequeño junto al nombre.                                   |
| 11  | Previsualización de impacto al editar movimiento | Sí (portado de Raidel desktop).                                  |
| 12  | Vista "Umbrales masiva"                          | Sí (se mantiene de móvil 2).                                     |
| 13  | Tema claro/oscuro                                | Sí, switch en Perfil.                                            |
| 14  | Cerrar tienda                                    | Doble confirmación + snack verde. Solo admin.                    |
| 15  | Zona horaria                                     | Hora local del dispositivo, sin TZ.                              |
| 16  | Notificaciones                                   | Solo snack in-app al cambiar de color un producto.               |
| 17  | Backup automático                                | Copia en `FLET_APP_STORAGE_DATA/backups/` con retención 30 días. |

---

## 2. Paleta — Negro + Dorado

### Marca (no cambia entre temas)

```python
COLOR_MARCA_DORADO           = "#d4af37"   # dorado clásico
COLOR_MARCA_DORADO_CLARO     = "#f0d97a"   # hover / highlights
COLOR_MARCA_DORADO_OSCURO    = "#a8862a"   # pressed
COLOR_MARCA_DORADO_SUAVE     = "#fdf6e3"   # fondos suaves (light)
COLOR_MARCA_NEGRO            = "#0a0a0a"
COLOR_MARCA_NEGRO_SUAVE      = "#1a1a1a"
```

### Paleta oscura (por defecto)

```
COLOR_FONDO         = "#0a0a0a"   negro profundo
COLOR_SUPERFICIE    = "#141414"   cards
COLOR_SUPERFICIE_2  = "#1e1e1e"   cards internas
COLOR_BORDE         = "#2a2a2a"
COLOR_BORDE_FUERTE  = "#3a3a3a"
COLOR_TEXTO         = "#f5f5f5"
COLOR_TEXTO_SUAVE   = "#a3a3a3"
COLOR_TEXTO_TENUE   = "#6b6b6b"
COLOR_ACENTO        = COLOR_MARCA_DORADO
SOMBRA_CARD         = "#00000099"
GRADIENTE_FONDO     = ["#0a0a0a", "#1a1408", "#2a1f08"]  # negro → dorado muy sutil
```

### Paleta clara

```
COLOR_FONDO         = "#fafaf7"   blanco cálido
COLOR_SUPERFICIE    = "#ffffff"
COLOR_SUPERFICIE_2  = "#f5f4ef"
COLOR_BORDE         = "#e5e3dc"
COLOR_BORDE_FUERTE  = "#c9c5b8"
COLOR_TEXTO         = "#0a0a0a"
COLOR_TEXTO_SUAVE   = "#57534e"
COLOR_TEXTO_TENUE   = "#a8a29e"
COLOR_ACENTO        = COLOR_MARCA_DORADO_OSCURO   # dorado más oscuro para contraste
SOMBRA_CARD         = "#0000001a"
GRADIENTE_FONDO     = ["#fafaf7", "#f5edd5", "#e8d9a8"]
```

### Colores semánticos (independientes del tema)

```
COLOR_VERDE    = "#22c55e"   # stock OK
COLOR_AMARILLO = "#eab308"   # stock bajo
COLOR_ROJO     = "#ef4444"   # stock crítico
COLOR_EXITO    = "#16a34a"
COLOR_PELIGRO  = "#dc2626"
COLOR_AMBAR    = "#ca8a04"
COLOR_INFO     = "#0284c7"
```

Se puede añadir azul (`#0ea5e9`) para "información" o estados neutros
si se necesita. La base dorada + negra con acentos semánticos verde /
amarillo / rojo / azul cubre toda la app.

---

## 3. Esquema BD v6 (multi-local)

```sql
PRAGMA foreign_keys = ON;

CREATE TABLE meta (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE locales (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    nombre      TEXT UNIQUE NOT NULL COLLATE NOCASE,
    es_almacen  INTEGER NOT NULL DEFAULT 0,
    activo      INTEGER NOT NULL DEFAULT 1,
    creado      TEXT NOT NULL
);

CREATE TABLE usuarios (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    username      TEXT UNIQUE NOT NULL COLLATE NOCASE,
    password_hash TEXT NOT NULL,
    salt          TEXT NOT NULL,
    rol           TEXT NOT NULL CHECK(rol IN ('admin','almacen','comun')),
    activo        INTEGER NOT NULL DEFAULT 1,
    creado        TEXT NOT NULL
);

CREATE TABLE configuracion (
    clave TEXT PRIMARY KEY,
    valor TEXT NOT NULL
);

CREATE TABLE productos (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id         INTEGER NOT NULL,
    codigo           TEXT COLLATE NOCASE,
    nombre           TEXT NOT NULL COLLATE NOCASE,
    stock            REAL NOT NULL DEFAULT 0,
    umbral_verde     INTEGER NOT NULL DEFAULT 50,
    umbral_amarillo  INTEGER NOT NULL DEFAULT 20,
    precio_costo     REAL NOT NULL DEFAULT 0,
    precio_unitario  REAL NOT NULL DEFAULT 0,
    fecha_ultima_mod TEXT NOT NULL,
    activo           INTEGER NOT NULL DEFAULT 1,
    FOREIGN KEY(local_id) REFERENCES locales(id)
);

CREATE UNIQUE INDEX idx_prod_local_codigo
    ON productos(local_id, codigo) WHERE codigo IS NOT NULL;

CREATE UNIQUE INDEX idx_prod_local_nombre
    ON productos(local_id, nombre);

CREATE TABLE movimientos (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    local_id                 INTEGER NOT NULL,
    producto_id              INTEGER NOT NULL,
    tipo                     TEXT NOT NULL CHECK(tipo IN
        ('ENTRADA','SALIDA','BAJA','RESTAURACION',
         'TRASPASO_SALIDA','TRASPASO_ENTRADA',
         'UMBRAL','AJUSTE')),
    cantidad                 REAL NOT NULL DEFAULT 0,
    motivo                   TEXT,
    grupo_id                 TEXT,
    detalle                  TEXT,
    rebaja                   REAL NOT NULL DEFAULT 0,
    precio_unitario_momento  REAL NOT NULL DEFAULT 0,
    fecha                    TEXT NOT NULL,
    usuario                  TEXT NOT NULL,
    FOREIGN KEY(local_id) REFERENCES locales(id),
    FOREIGN KEY(producto_id) REFERENCES productos(id)
);

CREATE INDEX idx_mov_local    ON movimientos(local_id);
CREATE INDEX idx_mov_producto ON movimientos(producto_id);
CREATE INDEX idx_mov_fecha    ON movimientos(fecha);
CREATE INDEX idx_mov_grupo    ON movimientos(grupo_id);
CREATE INDEX idx_prod_local   ON productos(local_id);
CREATE INDEX idx_prod_activo  ON productos(activo);
```

`VERSION_ESQUEMA = 6`. `GENERAL_ID = -1` (vista virtual, nunca se
persiste). Si se detecta un esquema anterior, se dropea y se arranca
de cero (mismo patrón que `almacen_app_Raidel`).

### Notas sobre códigos

- **Formato**: `F` + `[A-Z]` + `[0-9]{4}` → `FA0001`, `FA0002`, …,
  `FA9999`, `FB0001`, …
- **Orden natural** (por longitud fija) = orden string. No hace falta
  sorting custom.
- **Auto-sugerencia**: al abrir el modal de Entrada, se calcula el
  siguiente código del local (`siguiente_codigo(local_id)`).
- **Validación**: único por local (constraint SQL ya lo cubre).
- Cuando un mismo producto existe en varios locales, el **mismo código
  se replica en todos** (por la regla de propagación #3). Si el código
  ya está en uso en el otro local por OTRO nombre, la propagación
  falla y se avisa con un diálogo claro.

---

## 4. Estructura del proyecto

```
almacen_movil_raidel/
├── main.py                       Entry Flet + tema + backup
├── rutas.py                      FLET_APP_STORAGE_DATA portable
├── db.py                         Esquema v6 + migraciones
├── seguridad.py                  PBKDF2 (copiado tal cual de móvil 2)
├── inventario.py                 Lógica stock multi-local + roles + códigos
├── locales.py                    CRUD locales + General virtual + prefs
├── usuarios.py                   CRUD usuarios (admin-only, capa negocio)
├── backup.py                     Copia con retención 30 días
├── excel_sync.py                 Generación Excel (multi-hoja)
├── pyproject.toml                Config Flet (package_name nuevo)
├── requirements.txt              flet==1.0.3, openpyxl
├── README.md                     Este archivo
├── recursos/
│   ├── icon.png                  ← COLOCAR AQUÍ (logo de launcher)
│   ├── login_bg.png              ← COLOCAR AQUÍ (fondo del login)
│   ├── signin_bg.png             ← COLOCAR AQUÍ (fondo del primer arranque)
│   ├── main_bg.png               ← COLOCAR AQUÍ (fondo de pantalla principal)
│   └── README.md                 Qué va en cada archivo
├── datos/                        (creado en runtime)
├── backups/                      (creado en runtime)
├── .github/
│   └── workflows/
│       └── build-apk.yml         Build APK (copiado de móvil 2)
└── ui/
    ├── __init__.py
    ├── app.py                    Router
    ├── estilos.py                Paleta negro+dorado + helpers
    ├── componentes.py            ruta_asset, fila_producto, chips, …
    ├── login.py                  Login + primer arranque
    ├── principal.py              Inicio + selector local + búsqueda
    ├── dashboard.py              Métricas + 4 listas por color
    ├── movimientos.py            Historial con filtros
    ├── perfil.py                 Perfil + admin + backup + Excel
    ├── admin_usuarios.py         Gestión usuarios (admin)
    ├── admin_locales.py          Abrir/cerrar tiendas (admin)
    ├── umbrales.py               Edición masiva
    ├── modales.py                Bottom sheets + dialogs + traspaso
    └── exportar.py               FilePicker + delegación a excel_sync
```

---

## 5. Soporte para pruebas visuales en VSCode

Para probar en VSCode con `flet run`, se usan **imágenes opcionales** en
`recursos/`. La app funciona **sin ellas** (con placeholders generados
por código). Cuando tengas las imágenes definitivas, solo las copias a
`recursos/` con el nombre correcto y la app las usa automáticamente.

### Comportamiento

En `ui/componentes.py` habrá un helper:

```python
def imagen_opcional(nombre: str, fallback: ft.Control) -> ft.Control:
    """Devuelve la imagen si existe, o el fallback si no."""
    ruta = ruta_asset(nombre)
    try:
        from pathlib import Path
        if Path(ruta).exists():
            return ft.Image(src=ruta, fit=ft.BoxFit.CONTAIN)
    except Exception:
        pass
    return fallback
```

### Uso por pantalla

| Pantalla              | Imagen          | Fallback si no existe     |
| --------------------- | --------------- | ------------------------- |
| Login                 | `login_bg.png`  | Gradiente negro→dorado    |
| Primer arranque       | `signin_bg.png` | Gradiente negro→dorado    |
| Inicio                | `main_bg.png`   | Fondo plano `COLOR_FONDO` |
| Logo (AppBar, Perfil) | `icon.png`      | Icono genérico de Flet    |

Los bloques de código que insertan las imágenes estarán **comentados**
con un marcador claro, por ejemplo:

```python
# ─── IMAGEN OPCIONAL: login_bg.png ──────────────────────
# Coloca el archivo en recursos/login_bg.png y descomenta.
# Si no existe, se usa el gradiente por defecto.
# img_login = imagen_opcional(
#     "login_bg.png",
#     ft.Container(
#         expand=True,
#         gradient=ft.LinearGradient(
#             begin=ft.Alignment.TOP_CENTER,
#             end=ft.Alignment.BOTTOM_CENTER,
#             colors=es.GRADIENTE_FONDO,
#         ),
#     ),
# )
# ─────────────────────────────────────────────────────────
```

En `recursos/README.md` estarán los nombres exactos y el tamaño
recomendado de cada imagen.

---

## 6. Flujos de usuario

### Navegación principal

- **Bottom nav** 4 tabs: Inicio · Métricas · Historial · Perfil
- **AppBar**:
  - Chip "Local actual" → bottom sheet con lista completa
  - Logo (solo en Inicio)
  - Acciones contextuales (Exportar Excel, Traspaso rápido)

### Inicio (catálogo)

- Chip del local actual
- Buscador pill (por nombre o código)
- Toggle **Activos / Inactivos / Todos** (para ver productos dados de baja)
- Tarjeta resumen (Valor del inventario + badge si hay críticos)
- Grid de productos con `fila_producto` (código como badge + chip de color)
- Botones "Entrada" / "Salida" (solo roles operativos; deshabilitados en General)

### Detalle de producto (bottom sheet)

- Cabecera: nombre, código, chip estado, fecha última mod
- Stats: Stock · Precio costo · Precio venta
- Acciones (según rol):
  - **Entrada**
  - **Salida** (con motivo libre + rebaja por unidad)
  - **Traspaso** (a otro local)
  - **Renombrar** (propaga)
  - **Precio** (costo + venta, propaga)
  - **Código** (editar, propaga)
  - **Umbrales**
  - **Dar de baja**

### Traspaso (bottom sheet o modal desde AppBar)

- Producto (pre-cargado si viene del sheet del producto)
- Local origen (readonly)
- Local destino (dropdown)
- Cantidad + Fecha
- Previsualización: "Centro: 45→40 · Vedado: 20→25"
- Crea 2 movimientos con el mismo `grupo_id`

### Historial

- Filtros chips: Todos / Entradas / Salidas / Bajas / Traspasos / Ajustes
- Buscador por producto o motivo
- Tap → detalle (con "Editar" si admin/almacén) + previsualización de impacto

### Métricas (por local actual, o agregado en General)

- **Estado del inventario** (4 tarjetas clicables):
  - Activos / Stock 0 / Verde / Amarillo / Crítico
  - Al tocar una → abre lista filtrada por ese criterio
- **Dinero**: Invertido · Venta Total · Margen · % Ganancia
- **Actividad**: Hoy / 7 días / 30 días / Histórico
- **Top 5 productos** (30 días)
- **Últimos movimientos**

### Perfil

- Cabecera con logo + usuario + chip de rol
- **Cuenta**: Editar perfil
- **Configuración**: Modo oscuro (switch)
- **Operación**: Umbrales de colores (admin/almacén)
- **Administración** (admin):
  - Gestionar usuarios
  - Administrar locales (abrir / cerrar tienda)
  - Editar movimientos
- **Datos**:
  - Exportar Excel (hojas fijas + una por local)
  - Exportar copia de seguridad (.db) → FilePicker elige dónde
  - Importar copia de seguridad (.db) → FilePicker elige desde dónde
- Cerrar sesión

### Selector de local

Bottom sheet desde el chip de la AppBar con:
`General · Almacén · Tienda1 · Tienda2 · …` + indicador del actual.
Al elegir se guarda en `configuracion` por usuario (`local_actual:<username>`).

---

## 7. Excel: hojas fijas + una por local

`excel_sync.py` genera un único `.xlsx` con:

**Hojas fijas:**

1. `Movimientos` — todos los movimientos globales agrupados por día
2. `VentasGenerales` — cuadrícula mensual con venta diaria / acumulada

**Hojas por local** (activo o histórico cerrado): 3. `<NombreLocal>` — inventario actual del local + totales (solo activos) 4. `Ventas_<NombreLocal>` — solo salidas con motivo "venta" (para locales activos, todo lo histórico; para cerrados, congelado)

Al **cerrar una tienda**, sus productos se traspasan al Almacén, pero
sus hojas `Ventas_<Local>` **quedan en el Excel con el histórico que
tenían**. Si esa tienda se vuelve a abrir (nombre nuevo), tendrá hojas
nuevas.

---

## 8. Módulos: origen y trabajo

### Se copian tal cual de `almacen_movil_2`

- `seguridad.py`
- `backup.py` (ajustar rutas)
- `.github/workflows/build-apk.yml` (cambiar package_name)
- `requirements.txt`
- `pyproject.toml` (renombrar `package_name` → `com.combosflash.almacen_raidel`)
- `main.py` (mismo patrón; cambiar título)

### Se adaptan de `almacen_movil_2`

- `ui/estilos.py` — nueva paleta negro+dorado
- `ui/componentes.py` — añade `imagen_opcional`, badge de código
- `ui/app.py` — rutas nuevas (`/admin-locales`)
- `ui/login.py` — branding dorado; bloque de imagen opcional comentado
- `ui/admin_usuarios.py` — casi igual; adaptar a `usuarios.py` nuevo
- `ui/umbrales.py` — casi igual
- `ui/movimientos.py` — más tipos de movimiento + editor con impacto
- `ui/perfil.py` — secciones nuevas (locales, backup, Excel)
- `ui/modales.py` — añade traspaso, salida con motivo/rebaja, edición código

### Se portan de `almacen_app_Raidel` (reescritos en Flet)

- `db.py` — esquema v6 (basado en `almacen_app_Raidel/db.py`)
- `inventario.py` — multi-local + traspaso + motivos + rebaja + propagación + cierre tienda + códigos Fxyyyy
- `locales.py` — CRUD + General virtual
- `excel_sync.py` — 9 hojas → adaptado a "hojas fijas + una por local"
- `ui/principal.py` — selector de local, búsqueda, lista
- `ui/dashboard.py` — métricas por local + 4 listas por color

### Se crean nuevos

- `ui/admin_locales.py` — abrir/cerrar tienda

---

## 9. Roles y permisos

| Acción                                        | admin | almacen | comun |
| --------------------------------------------- | :---: | :-----: | :---: |
| Ver productos / métricas / historial          |  ✅   |   ✅    |  ✅   |
| Registrar entrada / salida / traspaso         |  ✅   |   ✅    |  ❌   |
| Renombrar / Precio / Código / Umbrales / Baja |  ✅   |   ✅    |  ❌   |
| Cerrar tienda                                 |  ✅   |   ❌    |  ❌   |
| Abrir tienda                                  |  ✅   |   ❌    |  ❌   |
| Editar movimientos                            |  ✅   |   ✅    |  ❌   |
| Gestionar usuarios                            |  ✅   |   ❌    |  ❌   |
| Exportar Excel / Backup / Import BD           |  ✅   |   ✅    |  ✅   |

Validación **en la capa de negocio** (`inventario.py`, `locales.py`,
`usuarios.py`), no solo en UI. Falla con `PermissionError`.

---

## 10. Códigos Fxyyyy — especificación

### Formato

`F` + `[A-Z]` + `[0-9]{4}` → **siempre 6 caracteres**.

Ejemplos: `FA0001`, `FA0042`, `FA9999`, `FB0001`, `FZ0001`.

### Auto-sugerencia al crear producto

```python
def siguiente_codigo(local_id: int) -> str:
    """Devuelve 'FA0001' si no hay códigos, o incrementa el mayor."""
    # Leer todos los códigos del local
    # Filtrar los que matchean ^F[A-Z]\d{4}$
    # Tomar el máximo (orden lexicográfico, que equivale a orden natural)
    # Incrementar el número; si llega a 10000, pasar a la siguiente letra
    # Si se acaba la Z, devolver None y avisar
```

### Orden en el listado

Como todos los códigos tienen la misma longitud, el orden string es
equivalente al orden (letra, número). No hace falta custom sort.

### Propagación

Si un producto existe en varios locales (mismo `nombre`), al cambiar
su código en uno, se propaga el mismo código a todos. Si el código
nuevo choca en algún local con OTRO producto, la operación falla y se
avisa con el nombre del producto en conflicto y el local.

---

## 11. Plan de trabajo (fases)

### Fase 1 — Esqueleto y BD

- [ ] `pyproject.toml`, `requirements.txt`, `.github/workflows/build-apk.yml`
- [ ] `rutas.py`, `seguridad.py`, `backup.py`
- [ ] `db.py` (esquema v6 + migraciones)
- [ ] `main.py` (patrón Flet, warnings, tema)
- [ ] `ui/estilos.py` (paleta negro+dorado claro/oscuro)
- [ ] `ui/componentes.py` (helpers base + `imagen_opcional`)
- [ ] `ui/app.py`, `ui/login.py` (login + primer arranque)
- [ ] **Meta**: app que hace login y entra a un Inicio vacío.

### Fase 2 — Núcleo de inventario

- [ ] `locales.py` (CRUD + General virtual)
- [ ] `inventario.py` (multi-local, entrada, salida, códigos, propagación)
- [ ] `usuarios.py` (capa negocio admin)
- [ ] `ui/principal.py` (Inicio + selector de local + búsqueda)
- [ ] `ui/modales.py` (entrada, salida, precio, código, renombrar, baja)
- [ ] **Meta**: crear productos, editar precios, propagar, ver General.

### Fase 3 — Extras de Raidel

- [ ] Traspaso entre locales (bottom sheet + AppBar)
- [ ] Rebaja por unidad en salida
- [ ] Motivos de salida (texto libre con default configurable)
- [ ] Umbrales por producto + masiva
- [ ] Abrir/cerrar tienda (`ui/admin_locales.py`)
- [ ] **Meta**: paridad funcional completa con `almacen_app_Raidel`.

### Fase 4 — UI secundaria

- [ ] `ui/dashboard.py` (métricas + 4 listas por color)
- [ ] `ui/movimientos.py` (historial con filtros + editor)
- [ ] `ui/admin_usuarios.py` (gestión)
- [ ] `ui/perfil.py` (secciones + switch tema)
- [ ] **Meta**: navegación completa.

### Fase 5 — Excel + Backup

- [ ] `excel_sync.py` (hojas fijas + una por local)
- [ ] `ui/exportar.py` (FilePicker → Excel / BD)
- [ ] Import BD con confirmación
- [ ] **Meta**: export funcional y testeado en Android.

### Fase 6 — Pulido

- [ ] Imágenes opcionales (login_bg, signin_bg, main_bg)
- [ ] Pruebas en dispositivo
- [ ] Ajustes de UX por feedback
- [ ] Compilar APK y verificar en Redmi 14

---

## 12. Cómo continuar en otro chat

Cuando cambies de chat, pégale al asistente:

1. **Este README.md**
2. El código fuente de **`almacen_movil_2`** completo
   (especialmente `ui/estilos.py`, `ui/componentes.py`, `ui/app.py`,
   `ui/login.py`, `ui/principal.py`, `ui/modales.py`)
3. El código fuente de **`almacen_app_Raidel`** completo
   (especialmente `db.py`, `inventario.py`, `locales.py`,
   `excel_sync.py`, `backup.py`, `rutas.py`)
4. Las imágenes (si ya las tienes) o el aviso "las imágenes las pongo
   después en recursos/"
5. Mensaje: _"Continúa con la Fase X del README. Empieza por los
   archivos listados."_

---

## 13. Pendientes de confirmar (menores)

- [ ] ¿El `default` del motivo de salida debe ser "Combos" (como móvil 2)
      o "Venta" (como Raidel)?
- [ ] ¿El % de ganancia en el Dashboard se calcula con `margen /
    invertido * 100` (Raidel) o de otra forma?
- [ ] ¿La lista "Stock 0" del Dashboard incluye productos inactivos o
      solo activos?
- [ ] ¿Se guarda `precio_costo` en el producto o se calcula desde
      movimientos? (Raidel lo guarda por producto.)
- [ ] ¿Cuántos backups se retienen? (default: 30 días, como Raidel.)

Estas se pueden cerrar sobre la marcha sin bloquear el desarrollo.

---

## 14. Compilación APK

Idéntico a `almacen_movil_2`: GitHub Actions con Java 17, Flutter 3.44.8,
Python 3.12, `flet==1.0.3`. Se renombra `package_name` y `product_name`
en `pyproject.toml`.

**Nombre del paquete**: `com.combosflash.almacen_raidel`
**Nombre producto**: `Almacén Raidel`

Instalar en Redmi 14: desinstalar versión previa → reiniciar celular →
instalar APK nuevo (mismo procedimiento documentado en móvil 2).
