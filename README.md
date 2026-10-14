# Almacén ComboFlash

Aplicación de escritorio de gestión de inventario, punto de venta (POS),
clientes, caja, gastos y proveedores para múltiples locales.

Construida en **Python + Flet + SQLite**, con exportación a Excel y
tickets en PDF/PNG.

---

## Índice

- [Stack](#stack)
- [Instalación y arranque](#instalación-y-arranque)
- [Variables de entorno](#variables-de-entorno)
- [Estructura del proyecto](#estructura-del-proyecto)
- [Arquitectura por capas](#arquitectura-por-capas)
- [Conceptos clave](#conceptos-clave)
  - [Multi-local](#multi-local)
  - [Multimoneda](#multimoneda)
  - [Códigos de producto](#códigos-de-producto)
  - [Promedio ponderado de precios](#promedio-ponderado-de-precios)
  - [Motivos de movimiento](#motivos-de-movimiento)
  - [Constantes de motivos de venta](#constantes-de-motivos-de-venta)
- [Base de datos](#base-de-datos)
- [Sincronización POS ↔ Historial](#sincronización-pos--historial)
- [Módulos de dominio](#módulos-de-dominio)
- [Interfaz de usuario](#interfaz-de-usuario)
- [Backup e importación](#backup-e-importación)
- [Exportación a Excel](#exportación-a-excel)
- [Tickets](#tickets)
- [Tests](#tests)
- [Convenciones](#convenciones)
- [Pendientes / Roadmap](#pendientes--roadmap)
- [Historial de cambios relevantes](#historial-de-cambios-relevantes)

---

## Stack

| Capa      | Tecnología                               |
| --------- | ---------------------------------------- |
| UI        | Flet 1.0.x                               |
| BD        | SQLite 3 (WAL, foreign keys ON)          |
| Excel     | openpyxl                                 |
| Tickets   | reportlab + Pillow                       |
| Seguridad | PBKDF2 (hashlib)                         |
| Tests     | `full_test.py` (BD temporal, sin pytest) |

---

## Instalación y arranque

```bash
# 1. Clonar
git clone https://github.com/Di-2003/almacen-app-desktop-ComboFlash.git
cd almacen-app-desktop-ComboFlash

# 2. Entorno virtual
python -m venv .venv
.venv\Scripts\activate      # Windows
source .venv/bin/activate   # Linux/macOS

# 3. Dependencias
pip install -r requirements.txt

# 4. Arrancar
python main.py
```

En el primer arranque la app pide crear un usuario **admin**. Después
siempre pide login.

Los assets (`icon.ico`, `icon.png`, `login_bg.png`, `signin_bg.png`)
viven en `assets/`.

---

## Variables de entorno

| Variable           | Descripción                                                                                                         | Default     |
| ------------------ | ------------------------------------------------------------------------------------------------------------------- | ----------- |
| `ALMACEN_DATA_DIR` | Carpeta donde vive `almacen.db`, `backups/` y `logs/`. Los tests la apuntan a un `tmpdir` para no tocar la BD real. | `./datos/`  |
| `FLET_ASSETS_DIR`  | Carpeta de assets para Flet (`icon.png`, backgrounds de login).                                                     | `./assets/` |

`rutas.py` resuelve estas rutas al arrancar.

---

## Estructura del proyecto

```
almacen-app-desktop-ComboFlash/
├── main.py                    # Punto de entrada (Flet)
├── db.py                      # Esquema, conexión, migración, defaults
├── rutas.py                   # Rutas de datos, backups, logs
├── seguridad.py               # Hash de contraseñas (PBKDF2)
│
├── # ── Dominio ──
├── inventario.py              # Productos, entradas, salidas, traspasos
├── ventas.py                  # POS: carrito, cobro, pagos, edición
├── clientes.py                # Clientes + cuentas por cobrar + abonos
├── caja.py                    # Sesiones de caja + cuadre
├── gastos.py                  # Gastos operativos + categorías
├── devoluciones.py            # Devoluciones (parcial/total)
├── proveedores.py             # Proveedores + pagos + N:M productos
├── categorias.py              # Tipos de producto
├── configuracion_negocio.py   # Datos del negocio + métodos de pago
├── locales.py                 # Almacén + tiendas + vista "General"
├── usuarios.py                # Usuarios + roles
├── metricas.py                # Dashboard: ventas, ganancias, top, etc.
├── excel_sync.py              # Generación de los 3 Excel
├── ticket.py                  # PDF / PNG / texto de ticket
├── backup.py                  # Backup automático a backups/
│
├── # ── UI (Flet) ──
├── ui/
│   ├── app.py                 # AlmacenApp: rutas, drawer, scroll
│   ├── estilos.py             # Paleta, modo claro/oscuro, helpers
│   ├── componentes.py         # Widgets reutilizables (snack, sheet, …)
│   ├── login.py               # Login + primer arranque
│   ├── principal.py           # Inicio (productos) + barra navegación
│   ├── pos.py                 # POS: lista, carrito, cobro, ticket
│   ├── ordenes.py             # Listado de órdenes + detalle + edición
│   ├── clientes.py            # CRUD clientes + cuentas por cobrar
│   ├── caja.py                # Sesiones de caja
│   ├── movimientos.py         # Historial (edición desde aquí)
│   ├── gastos.py              # Gastos + categorías de gastos
│   ├── proveedores.py         # CRUD proveedores + pagos
│   ├── dashboard.py           # Métricas y gráficos
│   ├── lista_productos.py     # Lista filtrada desde el dashboard
│   ├── modales.py             # Entrada/salida/traspaso, editar producto
│   ├── perfil.py              # Perfil, config, admin, datos
│   ├── admin_usuarios.py      # CRUD usuarios
│   ├── admin_locales.py       # Abrir/renombrar/cerrar tiendas
│   ├── admin_categorias.py    # CRUD tipos de producto
│   ├── admin_categorias_gastos.py
│   ├── config_negocio.py      # Datos del negocio + métodos de pago
│   ├── umbrales.py            # Umbrales por defecto
│   ├── producto_proveedores.py
│   ├── drawer.py              # Menú lateral
│   ├── graficos.py            # Línea, pie, barras
│   ├── tablas.py              # Tablas auxiliares
│   ├── _scroll.py             # Persistencia de scroll
│   └── exportar.py            # Import/backup/export con FilePicker
│
├── assets/                    # icon.png, icon.ico, bgs de login
├── datos/                     # almacen.db (WAL)
├── backups/                   # Copias automáticas + antes de importar
├── logs/                      # (reservado)
│
├── full_test.py               # Suite de tests con BD temporal
├── estado.py                  # Script de inspección rápida
├── diagnostico.py             # Diagnóstico de BD y esquema
├── requirements.txt           # Dependencias pip
└── README.md
```

---

## Arquitectura por capas

```
┌───────────────────────────────────────────────┐
│  UI  (ui/*.py)                                │
│  Flet · vistas · modales · componentes        │
└────────────────────┬──────────────────────────┘
                     │  llama a funciones de dominio
┌────────────────────▼──────────────────────────┐
│  Dominio (inventario, ventas, clientes, …)    │
│  Reglas de negocio · validaciones · SQL       │
└────────────────────┬──────────────────────────┘
                     │  abre conexión con contextmanager
┌────────────────────▼──────────────────────────┐
│  db.py                                        │
│  get_conn() (autocierra) · esquema · migración│
└────────────────────┬──────────────────────────┘
                     │
┌────────────────────▼──────────────────────────┐
│  SQLite  (WAL, FK ON, mmap, cache)            │
└───────────────────────────────────────────────┘
```

- **La UI no toca SQL directamente** (salvo contadas excepciones en
  `admin_locales.py` y `modales.py` para propagar flags). Todo lo
  demás pasa por los módulos de dominio.
- **`get_conn()` es un contextmanager** que **cierra la conexión** al
  salir del `with` (esto era un bug en versiones previas y bloqueaba
  el archivo en Windows).
- **La caché de `inventario`** se invalida en cada escritura
  (`_write` la limpia). `app.cambiar_local()` la invalida también.

---

## Conceptos clave

### Multi-local

- **`Almacén`** (`es_almacen = 1`): local principal, no se puede
  cerrar ni renombrar. Sus productos son el "catálogo maestro".
- **Tiendas** (`es_almacen = 0`): cada una con su propio stock,
  precios y umbrales.
- **`General`** (`GENERAL_ID = -1`): **vista virtual agregada**, no
  existe en la tabla `locales`. Suma stock y calcula precios
  ponderados por stock de todos los locales activos.

Cerrar una tienda **traspasa todo su stock al Almacén** y marca la
tienda como inactiva. Los productos con stock 0 se inactivan.

### Multimoneda

- Se guardan **3 columnas por cada precio**:
  - `precio_costo` / `precio_unitario` → siempre en **CUP**.
  - `precio_costo_orig` / `precio_unitario_orig` → en la moneda original.
  - `moneda_costo` / `moneda_venta` → `'CUP' | 'USD' | 'EUR'`.
- Conversión con `a_cup`, `de_cup`, `convertir`.
- Las tasas se guardan en `configuracion` (`tasa_usd`, `tasa_eur`) y al
  cambiarlas se puede **recalcular todos los precios** de golpe
  (`recalcular_todos_los_precios`).
- **Moneda de visualización** (`moneda_visualizacion`): solo afecta a
  cómo se muestran los totales, no a la BD.

### Códigos de producto

Formato `F{A-Z}{0001-9999}`. El código es **global por nombre**: si
un producto existe en Almacén con código `FA0001`, al darlo de alta
en una tienda hereda el mismo código. La app valida:

- No repetir código dentro del mismo local.
- No repetir código para un **nombre distinto** en ningún local.

`siguiente_codigo()` devuelve el siguiente disponible global.

### Promedio ponderado de precios

Al registrar una **entrada** de un producto existente con precio:

| Estado del precio actual         | Comportamiento                      |
| -------------------------------- | ----------------------------------- |
| **Precio > 0** (ya había precio) | Se **promedia ponderado** por stock |
| **Precio = 0** (sin precio)      | Se **fija directo** el nuevo precio |

Esto aplica **por separado** a `precio_costo` y `precio_unitario`. La
lógica está en `inventario.registrar_entrada` y usa
`_promedio_ponderado(stock_antes, orig_antes, cant_nueva, orig_nueva)`.

**Ejemplo** — Producto con stock 10 y costo 0:

- Entrada de 5 con costo $100.
  - **Antiguo:** `(10·0 + 5·100) / 15 = 33.33` (mal).
  - **Actual:** costo final **$100** (fijado directo).
- Siguiente entrada de 5 con costo $200 → promedio sobre stock 15:
  `(15·100 + 5·200) / 20 = 125`.

### Motivos de movimiento

| Motivo             | Origen                             | Cuenta como venta |
| ------------------ | ---------------------------------- | ----------------- |
| `Combos`           | POS actual + salida manual default | ✅ sí             |
| `Venta`            | POS histórico (compatibilidad)     | ✅ sí             |
| `Merma`            | Baja / ajuste manual               | ❌ no             |
| `Error`            | Baja / ajuste manual               | ❌ no             |
| `Pantry`           | Salida interna                     | ❌ no             |
| Nombre de empleado | Salida interna                     | ❌ no             |

**Regla unificada**: una `SALIDA` cuenta como venta si
`LOWER(TRIM(motivo)) IN ('venta','combos')` y **no pertenece a una
orden anulada**.

`productos_estancados` devuelve productos activos con stock > 0 que
**no** tienen ninguna venta real en los últimos N días. Es decir, un
producto que solo tiene mermas, errores o pantry aparece como estancado
(aunque tenga movimientos).

### Constantes de motivos de venta

Existen tres constantes con nombres parecidos; conviene no
confundirlas:

| Constante                | Ubicación                       | Uso                                                                 |
| ------------------------ | ------------------------------- | ------------------------------------------------------------------- |
| `_MOTIVO_VENTA_POS`      | `ventas.py`                     | Motivo que **escribe** el POS (`"Combos"`).                         |
| `VENTA_MOTIVOS`          | `metricas.py` y `excel_sync.py` | Motivos que **cuentan como venta** (`("venta","combos")`).          |
| `_MOTIVOS_VENTA`         | `inventario.py`                 | Motivos **válidos al editar** desde Historial.                      |
| `SQL_ES_VENTA`           | `metricas.py`                   | Fragmento SQL con alias `m.` para contar ventas.                    |
| `SQL_ES_VENTA_SIN_ALIAS` | `metricas.py`                   | Igual, pero sin alias (para queries sobre `movimientos` sin alias). |
| `SQL_NO_ANULADA`         | `metricas.py`                   | Fragmento SQL para excluir movimientos de órdenes anuladas.         |

---

## Base de datos

### Versión de esquema

**v10**. Se marca en `meta.version_esquema`.

Al abrir la app:

1. Si detecta un esquema P1 (v4, sin `local_id` en `productos`),
   **migra in-place** a v10 preservando datos.
2. Si ya está en v10, aplica `_asegurar_*` (idempotente): columnas,
   índices, defaults, métodos de pago.
3. Si es una versión intermedia desconocida, **falla** y pide
   restaurar un backup.

### Tablas

| Grupo       | Tablas                                                       |
| ----------- | ------------------------------------------------------------ |
| Core        | `meta`, `locales`, `usuarios`, `configuracion`, `categorias` |
| Inventario  | `productos`, `movimientos`                                   |
| POS         | `ordenes_venta`, `orden_items`, `pagos`                      |
| Cobros      | `abonos`, `devoluciones`                                     |
| Clientes    | `clientes`                                                   |
| Caja        | `caja_sesiones`                                              |
| Métodos     | `metodos_pago`                                               |
| Gastos      | `categorias_gastos`, `gastos`                                |
| Proveedores | `proveedores`, `producto_proveedores`, `pagos_proveedor`     |

La tabla `meta` es clave/valor: `meta(clave TEXT PRIMARY KEY, valor TEXT NOT NULL)`.

### `get_conn()` — context manager

```python
@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH, timeout=15.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    conn.execute("PRAGMA temp_store = MEMORY")
    conn.execute("PRAGMA cache_size = -20000")
    conn.execute("PRAGMA mmap_size = 134217728")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
```

**Siempre** usar `with get_conn() as conn:`. Nunca guardar `conn`
fuera del bloque (se cierra).

### Migración P1 (v4) → v10

Se ejecuta automáticamente si `productos` existe pero no tiene
`local_id`. Estrategia:

1. Renombra `productos`/`movimientos` viejos a `_productos_v4`/
   `_movimientos_v4`.
2. Ejecuta `SCHEMA` (crea las nuevas).
3. Inserta Almacén + categorías + métodos de pago por defecto.
4. Copia productos con **código secuencial** (`FA0001…`).
5. Copia movimientos.
6. Borra tablas temporales.
7. Marca versión 10.

Preserva usuarios, configuración, productos y movimientos. **No
migra** POS/clientes/caja (no existían en P1).

---

## Sincronización POS ↔ Historial

Una orden POS genera **movimientos SALIDA** en `movimientos` con
`detalle = 'Ticket <numero_ticket>'`. Este string es el vínculo entre
ambas tablas.

### Dirección 1: POS → Historial

`ventas.editar_items_orden(orden_id, items_nuevos, usuario)`:

1. Revierte stock de los items viejos.
2. **Borra** todos los movimientos `SALIDA` de esa orden (cualquier
   motivo en `('venta','combos')` con `detalle LIKE '%<ticket>%'`).
3. Reemplaza `orden_items` con los nuevos.
4. **Inserta** movimientos `SALIDA` nuevos con
   `motivo = ventas._MOTIVO_VENTA_POS` (`"Combos"`) y la **fecha
   original** de la orden (no la de edición).
5. Recalcula `subtotal`, `descuento_global`, `total`, `saldo` y
   `estado`.
6. Sincroniza el pago `Fiado` si existía.

### Dirección 2: Historial → POS

`inventario.editar_movimiento(mov_id, …)`:

1. Valida que el movimiento sea editable (`ENTRADA`/`SALIDA`).
2. Si el movimiento viene de un POS (`detalle` empieza por
   `'Ticket '`):
   - El tipo debe seguir siendo `SALIDA`.
   - El motivo debe seguir siendo `'Venta'` o `'Combos'`.
   - **No** se puede cambiar el producto.
3. Revierte stock del movimiento viejo y aplica el nuevo.
4. Actualiza la fila de `movimientos`.
5. Llama a `_sincronizar_orden_desde_movimiento`, que:
   - Busca la orden por `numero_ticket`.
   - Actualiza `orden_items.cantidad` e `importe`.
   - Llama a `ventas.recalcular_orden_completa(conn, orden_id)`.

### `ventas.recalcular_orden_completa(conn, orden_id)`

Recalcula subtotal (con rebajas), reconstruye el `%` de descuento
global original, aplica el descuento al nuevo subtotal, actualiza
`subtotal`, `descuento_global`, `total` y dispara
`_recalcular_estado_orden` (que ajusta `saldo`, `estado`, `vuelto` y
sincroniza el pago Fiado).

### Reglas invariantes

- **Stock**: toda edición revierte el efecto anterior antes de aplicar
  el nuevo. El stock siempre refleja el estado actual de los items.
- **Monto_cup de pagos**: nunca cambia. `editar_pago` recalcula el
  `monto` en la moneda elegida para preservar `monto_cup`.
- **Anulación**: restaura stock solo del **pendiente** (descontando
  devoluciones previas). Esto evita el bug histórico de duplicar stock.

---

## Módulos de dominio

### `inventario.py`

Productos, entradas, salidas, traspasos, umbrales, precios, categoría,
baja/reactivación, búsqueda.

- Todas las escrituras están decoradas con `@_write` que **invalida la
  caché**.
- `listar_productos`, `totales_local`, `totales_por_concepto` están
  cacheadas.
- `StockInsuficiente` y `ProductoNoExiste` son las excepciones de
  dominio.
- Roles operativos: `admin`, `almacen`.

### `ventas.py`

Carrito en memoria (no toca BD hasta confirmar), cobro con hasta 3
pagos, pago mixto, Fiado, edición de items, edición de pagos,
anulación.

- `_calcular_pagado` = pagos no-crédito + abonos.
- `_sincronizar_pago_fiado` ajusta/elimina el pago Fiado al saldo real.
- Motivo de venta actual: `_MOTIVO_VENTA_POS = "Combos"` (constante al
  inicio del archivo).

### `clientes.py`

CRUD + cuentas por cobrar + abonos parciales.

- `saldo_pendiente(cliente_id)` = suma de `saldo_pendiente` de órdenes
  `pendiente`/`parcial`.
- `registrar_abono` maneja vuelto y propina: el monto aplicado al saldo
  es `min(neto_cup, saldo)`, el resto es propina (solo visible en el
  cuadre de caja).

### `caja.py`

Sesiones opcionales por usuario/local.

- `saldo_sistema = saldo_inicial + Σpagos + Σabonos − Σgastos_sesion`.
- Los gastos se asocian con `caja_sesion_id`.

### `gastos.py`

CRUD de gastos y categorías de gastos.

- `monto_cup = monto × tasa(moneda)` (histórico).
- Filtros: local (o global), rango de fechas, categoría.
- Se puede asociar a una sesión de caja abierta.

### `devoluciones.py`

Devoluciones parciales o totales hasta 7 días (admin sin límite).

- Restaura stock.
- Ajusta `total`, `saldo_pendiente`, `estado` de la orden.
- El monto devuelto se calcula con el precio efectivo del item
  (`importe / cantidad`).

### `proveedores.py`

CRUD + N:M con productos + pagos + saldo.

- `saldo_proveedor = Σentradas con proveedor − Σpagos`.
- `producto_proveedores` guarda el proveedor principal por producto.

### `locales.py`

Almacén + tiendas + vista General.

- `cerrar_tienda` traspasa todo el stock al Almacén y desactiva la
  tienda.
- `get_local_actual(username)` / `set_local_actual` persisten el local
  por usuario.

### `metricas.py`

Dashboard.

- `VENTA_MOTIVOS = ("venta","combos")`, `SQL_ES_VENTA`,
  `SQL_ES_VENTA_SIN_ALIAS`, `SQL_NO_ANULADA`.
- `resumen_periodo` devuelve TODO en un solo query.
- `ventas_ultimos_dias`, `top_productos_vendidos`,
  `ventas_por_metodo_pago`, `productos_estancados`.

---

## Interfaz de usuario

### Rutas

| Ruta                       | Vista               | Rol            |
| -------------------------- | ------------------- | -------------- |
| `/login`                   | Login               | —              |
| `/primer-arranque`         | Crear admin         | —              |
| `/principal`               | Inicio (productos)  | todos          |
| `/pos`                     | Punto de venta      | admin, almacén |
| `/dashboard`               | Métricas            | todos          |
| `/movimientos`             | Historial           | todos          |
| `/perfil`                  | Perfil + admin      | todos          |
| `/clientes`                | Clientes            | admin, almacén |
| `/caja`                    | Sesiones de caja    | admin, almacén |
| `/ordenes`                 | Órdenes de venta    | todos          |
| `/gastos`                  | Gastos              | admin, almacén |
| `/proveedores`             | Proveedores         | admin, almacén |
| `/lista-productos`         | Lista filtrada      | todos          |
| `/config-negocio`          | Datos + métodos     | admin, almacén |
| `/umbrales`                | Umbrales default    | admin, almacén |
| `/admin-categorias`        | Tipos de producto   | admin, almacén |
| `/admin-categorias-gastos` | Categorías de gasto | admin, almacén |
| `/admin-locales`           | Locales             | admin          |
| `/usuarios`                | Usuarios            | admin          |

### Roles

| Rol       | Puede                                                                               |
| --------- | ----------------------------------------------------------------------------------- |
| `admin`   | Todo. Eliminar, anular, gestionar usuarios y locales.                               |
| `almacen` | Operar inventario, POS, caja, gastos, proveedores. No gestiona usuarios ni locales. |
| `comun`   | Solo consulta. No opera.                                                            |

### Patrones de UI

- **`bottom_sheet(content, page)`**: sheet inferior con drag handle.
- **`snack(page, texto, tipo)`**: notificación inferior diferida 150 ms
  (para no chocar con cierres de diálogo).
- **`toast(page, texto, tipo)`**: notificación superior auto-destructiva.
- **`cerrar_dialogo(page, dlg, on_close)`**: cierra y ejecuta callback
  diferido.
- **`mostrar_modal(page, panel, on_close)`**: modal centrado con
  barrier; solo uno a la vez.
- **`mounted(ctrl)`**: `True` si el control está en el árbol. Se usa
  antes de `.update()`.
- **`columna_scroll(ruta, app, controls)`**: columna scrolleable que
  memoriza posición. Solo se restaura al volver de una vista hija.

### Estilos

`ui/estilos.py` expone colores como **variables globales** que se
reescriben al llamar `aplicar_tema(modo, paleta)`. Cambiar de tema
requiere reconstruir la vista (`app.refrescar()`).

---

## Backup e importación

### Backup automático

`backup.hacer_backup()` se puede llamar al arrancar:

1. Copia `datos/almacen.db` → `backups/almacen_YYYY-MM-DD_HHMMSS.db`.
2. Borra backups con más de **30 días** (`RETENCION_DIAS = 30`,
   configurable en `backup.py`).

### Backup manual (desde Perfil)

- **Backup Destino**: elige carpeta con `FilePicker.get_directory_path`.
- **Backup Interno**: guarda el `.db` en la carpeta elegida con
  `FilePicker.save_file`.

### Importar copia

`ui/exportar.importar_backup`:

1. Pide la contraseña del usuario actual.
2. Guarda un backup de la BD actual en `backups/almacen_antes_de_importar_*.db`.
3. **Borra WAL/SHM huérfanos**.
4. Escribe la nueva BD a un archivo **temporal**.
5. Reemplazo **atómico** con `os.replace`.
6. Reinicializa esquema y cierra sesión.

---

## Exportación a Excel

`excel_sync.py` genera 3 libros:

| Función                               | Contenido                                                                                  |
| ------------------------------------- | ------------------------------------------------------------------------------------------ |
| `generar_excel_bytes()`               | Inventario completo (resumen + fondos + hoja por local con productos, movimientos, ventas) |
| `generar_excel_diario()`              | Movimientos del día: hoja resumen + una por local                                          |
| `generar_excel_salidas_hoy(local_id)` | 3 tablas lado a lado por local: entradas, ventas (Combos), otras salidas                   |

**Reglas de clasificación** (idénticas a `metricas`):

- Venta = `SALIDA` con motivo en `('combos','venta')`, no anulada.
- Merma = `BAJA` o `SALIDA` con motivo `'merma'`. `'error'` **no** es merma.
- Fondos (`productos` cuyo nombre empieza con `fondo`) se excluyen de
  ventas y se muestran aparte.

---

## Tickets

`ticket.py` genera:

- **PDF** (`generar_ticket_pdf` / `guardar_ticket(id, "pdf")`).
- **PNG** (`generar_ticket_png`).
- **Texto plano** (`texto_plano_ticket`) para copiar/compartir.

Los datos del negocio salen de `configuracion_negocio` (`nombre`,
`direccion`, `telefono`, `nit`, `eslogan`, `moneda`).

---

## Tests

```bash
python full_test.py
```

- Usa una **BD temporal** (`ALMACEN_DATA_DIR` a un tmpdir).
- Cubre: seguridad, esquema, categorías, usuarios, locales,
  inventario, multimoneda, métricas, clientes, métodos de pago, POS,
  edición de pagos, caja, devoluciones, tickets, gastos, proveedores,
  casos extremos.
- Regresiones clave (entre otras):
  - `test_regresion_devolucion_luego_anular`: anular tras devolver no
    duplica stock.
  - `test_regresion_editar_pago_no_descuadra_caja`: editar pago
    preserva `monto_cup`.
  - `test_regresion_editar_pago_idempotente`: ciclos de cambio de
    moneda no acumulan distorsión.
  - `test_estancados_no_solapa_con_vendidos`: la lista de estancados
    no incluye productos con venta reciente.
  - `test_todos_los_activos_clasificados`: todo producto activo con
    stock > 0 está o en vendidos recientes o en estancados.

Scripts auxiliares:

- `diagnostico.py`: imprime rutas, tablas, columnas, versión.
- `estado.py`: conteos de filas y columnas de `productos`.

---

## Convenciones

- **Idioma**: nombres, docstrings y mensajes de error en español.
- **SQL**: consultas con alias (`m.` para `movimientos`, `o.` para
  `ordenes_venta`) para evitar ambigüedades con `SQL_ES_VENTA`.
- **Escrituras**: siempre decoradas con `@_write` en `inventario`
  (invalida caché) y dentro de `with get_conn()` (commit/rollback
  automático).
- **Fechas**: `'YYYY-MM-DD HH:MM:SS'` en local.
- **Moneda base**: CUP. Los precios en CUP viven en `precio_costo` /
  `precio_unitario`.
- **IDs virtuales**: `GENERAL_ID = -1` solo para consultas, nunca se
  inserta en la BD.

---

## Pendientes / Roadmap

### Fixes pendientes de aplicar

- **`inventario.totales_por_concepto`** — la función sigue con
  `LOWER(TRIM(motivo))='venta'`, así que no cuenta las ventas nuevas
  con motivo `'Combos'`. Aunque el dashboard no la usa (usa
  `metricas.resumen_periodo`), otras vistas antiguas podrían llamarla.
  **Fix**: reemplazar la cláusula por
  `LOWER(TRIM(COALESCE(motivo,''))) IN ('venta','combos')`.
  También cambiar el `<> 'venta'` de la consulta de "otras salidas"
  por `NOT (IN ('venta','combos'))`.

### Mejoras opcionales (cosméticas)

- **`metricas.productos_estancados`** — el docstring menciona
  "Pantry, nombres de empleados, etc." pero no hay ninguna lista
  explícita. El comportamiento **ya es correcto** (todo lo que no sea
  `'venta'`/`'combos'` deja al producto como estancado). Solo se
  podría añadir una constante `MOTIVOS_NO_VENTA = ("merma","error",
"pantry")` para documentarlo. Sin cambio funcional.

- **Unificar motivos en el histórico** — hoy conviven `'Venta'`
  (histórico) y `'Combos'` (nuevo). No hace falta tocarlo (todo el
  código acepta ambos), pero si algún día se quiere un único motivo
  se puede añadir una migración idempotente a `db.inicializar_db()`:

  ```sql
  UPDATE movimientos
  SET motivo='Combos'
  WHERE tipo='SALIDA'
    AND LOWER(TRIM(COALESCE(motivo,'')))='venta';
  ```

### Ideas discutidas pero no implementadas

- **CI / tests automáticos**: hoy los tests se corren a mano con
  `python full_test.py`. No hay GitHub Actions.
- **`CHANGELOG.md` separado**: el historial de cambios vive dentro de
  este README. Se puede extraer cuando crezca.
- **Exclusión explícita de motivos internos en
  `productos_estancados`**: hoy es implícita (lista blanca). Podría
  convertirse en configurable.
- **`CONTRIBUTING.md`**: no existe.
- **Empaquetado / build**: no hay instrucciones para generar un
  ejecutable (PyInstaller, `flet build`, etc.).

### Notas de mantenimiento

- **README vs realidad**: si añades un módulo nuevo, actualiza la
  sección "Estructura del proyecto" y "Módulos de dominio".
- **Regla de oro de motivos**: cualquier query que cuente ventas debe
  usar `metricas.SQL_ES_VENTA` o `SQL_ES_VENTA_SIN_ALIAS` (o el
  equivalente `excel_sync.VENTA_MOTIVOS`). Nunca hardcodear
  `='venta'`.
- **Regla de oro de sincronización**: si tocas `movimientos` de una
  orden POS, actualiza también `orden_items` y los totales de la
  orden (vía `ventas.recalcular_orden_completa`).

---

## Historial de cambios relevantes

### Fix POS ↔ Historial (bidireccional)

- **Antes**: editar en POS no actualizaba `movimientos`; editar en
  Historial no actualizaba `orden_items`. Los datos se desincronizaban
  y el stock "se movía" en direcciones opuestas.
- **Ahora**: ambos lados se avisan mutuamente usando
  `movimientos.detalle = 'Ticket <numero_ticket>'` como clave.

### Fix promedio ponderado condicional

- **Antes**: al dar entrada a un producto con `precio = 0` y stock > 0,
  el nuevo precio se diluía con ceros (`$0` mezclado con `$100` → `$33`).
- **Ahora**: si el precio actual es 0, el nuevo se **fija** directo. Si
  ya había precio > 0, se **promedia ponderado** como antes.

### Motivo de venta del POS

- El POS ahora escribe `motivo='Combos'` en los movimientos `SALIDA`
  (constante `ventas._MOTIVO_VENTA_POS`).
- Las ventas históricas con `motivo='Venta'` **se conservan** y siguen
  contando como venta en métricas, dashboard y Excel
  (`VENTA_MOTIVOS = ('venta','combos')`).
- `inventario._MOTIVOS_VENTA` acepta ambos para las validaciones del
  Fix 1.

### `metricas.py` legacy arreglado

Las funciones de compatibilidad (`vendido_periodo`,
`ventas_periodo`, `otras_salidas_periodo`, `ventas_sin_costo`, etc.)
usaban `='venta'` y no contaban `'Combos'`. Ahora usan
`SQL_ES_VENTA_SIN_ALIAS`.

### `get_conn()` context manager

Antes era una función normal que devolvía la conexión y quedaba
abierta; en Windows bloqueaba el archivo y rompía la importación de
backups. Ahora es un contextmanager que **siempre cierra**.

### Migración automática v4 → v10

Detecta BD del P1 (sin `local_id`) y migra in-place preservando datos.

---

Hecho por [Di-2003](https://github.com/Di-2003).
