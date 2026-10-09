# Almacén — App de escritorio (Combos Flash)

App **Windows / desktop**, **offline-first** y **multi-local** para
gestión de almacén, inventario, punto de venta (POS), clientes,
proveedores, gastos, caja, tickets y devoluciones. Soporte completo
**multimoneda (CUP / USD / EUR)**, **promedio ponderado de costos**,
**propagación de precios**, **cuentas por cobrar y por pagar**,
**Excel multi-hoja**, y backup manual/importación de BD.

Construida con **Python + Flet 1.0.3** sobre **Flutter 3.44.8**, SQLite
local, y empaquetada como **`.exe` portable** vía `flet build windows`.

Esta versión está personalizada para **Combos Flash** (paleta roja de
marca, logo propio). Para la versión genérica con **selector de paletas**
y branding neutro, ver el repo `almacen-app-desktop` (próximamente).

---

## Tabla de contenidos

1. [Estado actual](#1-estado-actual)
2. [Estructura del proyecto](#2-estructura-del-proyecto)
3. [Esquema BD v10](#3-esquema-bd-v10)
4. [Rendimiento](#4-rendimiento)
5. [Cómo probar y compilar](#5-cómo-probar-y-compilar)
6. [Roles y permisos](#6-roles-y-permisos)
7. [Roadmap — lo que falta](#7--lo-que-falta--roadmap-de-mejoras)
8. [Análisis de mercado Cuba](#8-análisis-de-mercado-cuba)
9. [Comparativa vs. competencia](#9-comparativa-vs-competencia)
10. [Stack técnico](#10-stack-técnico)
11. [Historial de versiones](#11-historial-de-versiones)
12. [Cómo continuar desarrollo](#12-cómo-continuar-desarrollo)
13. [Licencia y contacto](#13-licencia-y-contacto)

---

## 1. Estado actual

### ✅ Lo que YA está implementado

#### Inventario

- **Multi-local**: 1 Almacén + N tiendas + 1 vista virtual "General".
- **Alta de productos** con código auto-sugerido (`F[A-Z][0-9]{4}`).
- **Entrada**, **Salida** (con motivo y rebaja), **Traspaso**.
- **Dar de baja** / **Reactivar** producto.
- **Propagación** de precio, código, nombre, categoría y flag de
  granel a TODOS los locales.
- **Consistencia de códigos**: un nombre → un código global.
- **Multimoneda real** con valor original + CUP + promedio ponderado.
- **Roles** admin/almacen/comun validados en capa de negocio.

#### POS / Ventas

- **Pantalla `/pos`** con carrito, búsqueda única, chips de categoría.
- **Cobro mixto** hasta 3 pagos con moneda por pago.
- **Editar un pago** en línea.
- **9 métodos de pago configurables** (Efectivo CUP/USD/EUR/MLC,
  Transfermóvil, EnZona, Zelle, Tarjeta, Fiado).
- **Cuenta/QR por método** mostrados al cliente.
- **Correlativo anual** `T-AAAA-NNNN`.
- **Anular orden** restaura stock.
- **Editar orden de venta** (cambiar cantidad, quitar ítems).
- **Validación de stock** al agregar y al editar.
- **POS no obligatorio**: el flujo "Salida → Venta" sigue existiendo.

#### Clientes

- **CRUD completo** con límite de crédito.
- **Cuentas por cobrar** con abonos parciales.
- **Historial de compras** por cliente.
- **Vista "cuentas por cobrar"**.

#### Proveedores

- **CRUD simple** (nombre + teléfono) con capitalización de cada palabra.
- **Relación N:M** producto↔proveedor (un producto puede tener varios
  proveedores).
- **Proveedor principal** por producto (opcional).
- **Cuentas por pagar** con pagos parciales.
- **Historial de pagos** por proveedor.
- **Auto-asociación**: al dar entrada con proveedor, se asocia al
  producto y al movimiento.
- **Crear proveedor inline** desde el modal de entrada y desde el
  detalle de producto.

#### Gastos operativos

- **CRUD completo** con categorías configurables
  (Luz, Agua, Alquiler, Salario, Transporte, Otros).
- **Moneda CUP/USD/EUR** con conversión automática.
- **Gastos por local o globales**.
- **Switch "Pagado de la caja abierta"** → afecta el cuadre de caja.
- **Filtros** por período (Hoy/Semana/Mes/Año/Total), local y categoría.
- **Total del período** en vivo.
- **Utilidad neta en Dashboard** (Ganancia − Gastos).

#### Caja

- **Múltiples sesiones por día** por usuario.
- **Cálculo del saldo esperado**:
  `inicial + Σpagos + Σabonos − Σgastos de la sesión`.
- **Cierre con conteo físico** y cálculo de diferencia.
- **Resumen por método** de pago y abonos.
- **Historial** de sesiones cerradas.

#### Tickets

- **PDF 80mm** (formato térmico) con `fpdf2`.
- **PNG 440px** para compartir por WhatsApp (Pillow).
- **Ticket en texto plano** para copiar al portapapeles.
- **Datos del negocio** configurables.
- **Diálogo "Preparar envío"** que guarda PDF + PNG y copia el texto.

#### Devoluciones

- **Parcial o total**, hasta **7 días** de la venta.
- **Revierte stock** con movimiento `ENTRADA`.
- **Ajusta saldo pendiente** de la orden si era fiado.
- **Motivo** obligatorio.

#### Herramientas

- **`full_test.py`**: test suite completo.
- **`diagnostico.py`**: muestra la ubicación real de la BD y el
  estado del esquema.
- **`estado.py`**: reporte rápido de tablas y versiones.
- **`migrar.py`**: migración standalone P1(v4) → v10 con backup
  automático.

### 🆕 Específico de esta versión desktop

- **`rutas.py` portable**: escribe `datos/`, `backups/`, `logs/`,
  `tickets/` al lado del `.exe`. Si esa carpeta no es escribible
  (p. ej. `C:\Program Files`), cae automáticamente a
  `%LOCALAPPDATA%\Almacen\`.
- **`get_conn()` como contextmanager**: cierra la conexión SQLite al
  salir del `with`. Fix del error `[Errno 22]` al importar la BD.
- **Importador de BD robusto**: escribe a un temporal y usa
  `os.replace()` para el reemplazo atómico. Borra WAL/SHM huérfanos.
- **`editar_movimiento()` en `inventario.py`**: permite editar
  movimientos `ENTRADA` y `SALIDA` revirtiendo/aplicando el efecto
  sobre stock.
- **Drawer con `Stack`** de posicionamiento absoluto: cubre toda la
  altura sin dejar franja entre drawer y barra inferior.
- **FAB del POS movido a la AppBar**: ya no tapa el último producto
  de la lista.
- **Iconos propios**: `assets/icon.png` + `assets/icon.ico`
  multi-resolución para barra de título, taskbar, Alt+Tab y el `.exe`.
- **Dropdown de movimiento** limitado a `ENTRADA` y `SALIDA` para
  evitar intentos de edición sobre `BAJA`/`TRASPASO_*`.

---

## 2. Estructura del proyecto

```text
almacen_desktop_Flet/
├── main.py                       Entry Flet
├── rutas.py                      Rutas portables (dev vs .exe)
├── db.py                         Esquema v10 + migración + contextmanager
├── seguridad.py                  PBKDF2-HMAC-SHA256
├── inventario.py                 Lógica stock + multimoneda + caché
├── locales.py                    CRUD locales + General virtual
├── usuarios.py                   CRUD usuarios (capa negocio admin)
├── categorias.py                 CRUD categorías producto
├── clientes.py                   CRUD clientes + cuentas por cobrar
├── ventas.py                     POS: carrito, cobro, anulación, editar orden
├── caja.py                       Sesiones de caja (lógica)
├── devoluciones.py               Devoluciones con restauración de stock
├── proveedores.py                CRUD proveedores + N:M producto + pagos
├── gastos.py                     CRUD gastos + categorías
├── configuracion_negocio.py      Datos del negocio + métodos de pago
├── ticket.py                     PDF 80mm + PNG + texto plano
├── metricas.py                   Métricas por período calendario
├── backup.py                     Copia con retención 30 días
├── excel_sync.py                 Excel multi-hoja con moneda
├── full_test.py                  Test exhaustivo
├── diagnostico.py                Ubicación real de la BD
├── estado.py                     Reporte de tablas y versiones
├── migrar.py                     Migración standalone con backup
├── pyproject.toml                Config Flet + dependencias
├── requirements.txt              flet, openpyxl, fpdf2, Pillow
├── uv.lock                       Lockfile de uv
├── README.md                     Este archivo
├── .gitignore
├── assets/                       icon.png, icon.ico, README.md
└── ui/
    ├── __init__.py
    ├── _scroll.py                Preservación de scroll entre vistas
    ├── app.py                    Router + estado + drawer + carrito POS
    ├── estilos.py                Paleta Combos Flash + helpers
    ├── componentes.py            Widgets + snack + toast + modales
    ├── drawer.py                 Panel lateral
    ├── login.py                  Login + primer arranque
    ├── principal.py              Inicio + chips + selector tipos
    ├── dashboard.py              Métricas + Gastos + Utilidad neta
    ├── movimientos.py            Historial + paginación + editar
    ├── lista_productos.py        Lista filtrada desde Dashboard
    ├── perfil.py                 Perfil + admin + accesos
    ├── pos.py                    POS: carrito + cobro + ticket
    ├── ordenes.py                Órdenes + detalle + editar + devolver
    ├── clientes.py               Clientes + cuentas por cobrar
    ├── proveedores.py            Proveedores + cuentas por pagar
    ├── producto_proveedores.py   Modal N:M producto↔proveedor
    ├── gastos.py                 Vista gastos
    ├── admin_categorias_gastos.py CRUD categorías gastos
    ├── caja.py                   Vista caja (UI)
    ├── config_negocio.py         Datos del negocio + métodos de pago
    ├── admin_usuarios.py         Gestión usuarios (admin)
    ├── admin_locales.py          Abrir/cerrar tiendas (admin)
    ├── admin_categorias.py       CRUD tipos de producto
    ├── umbrales.py               Edición masiva
    ├── modales.py                Bottom sheets + entrada/salida/traspaso
    └── exportar.py               FilePicker + Excel + BD + backup
```

---

## 3. Esquema BD v10

**Migración v9 → v10 no destructiva** (`CREATE TABLE IF NOT EXISTS`

- `ALTER TABLE ADD COLUMN`). Los datos de v9 se conservan.

```sql
-- TABLAS base
meta, locales, usuarios, configuracion, categorias, productos,
movimientos (con proveedor_id opcional)

-- TABLAS POS + clientes + caja
clientes, ordenes_venta, orden_items, pagos, abonos,
devoluciones, caja_sesiones, metodos_pago

-- TABLAS v10
categorias_gastos (id, nombre UNIQUE, activo)

gastos (
    id, local_id, categoria_id, monto, moneda, tasa, monto_cup,
    metodo, descripcion, fecha, usuario, caja_sesion_id
)

proveedores (
    id, nombre UNIQUE, telefono, activo, creado
)

producto_proveedores (
    id, producto_nombre, proveedor_id, es_principal,
    UNIQUE(producto_nombre, proveedor_id)
)

pagos_proveedor (
    id, proveedor_id, monto, moneda, tasa, monto_cup,
    metodo, fecha, usuario, notas
)
```

**Notas:**

- `VERSION_ESQUEMA = 10`.
- `GENERAL_ID = -1` (vista virtual, nunca se persiste).
- `precio_costo` y `precio_unitario` están siempre en CUP.
- `precio_costo_momento` en movimientos = costo CUP histórico.
- `pagos.monto_cup` = monto convertido con tasa histórica.
- `ordenes_venta.numero_ticket` UNIQUE global.
- Correlativo anual en `configuracion` como
  `ticket_correlativo_<AAAA>`.
- `producto_proveedores.producto_nombre` (no id) → relación global
  entre locales.

---

## 4. Rendimiento

| Técnica                                          | Impacto                         |
| ------------------------------------------------ | ------------------------------- |
| **WAL mode**                                     | Escrituras no bloquean lecturas |
| **`synchronous=NORMAL`**                         | 5–10× más rápido                |
| **`cache_size=20MB`**                            | Menos I/O                       |
| **`mmap_size=128MB`**                            | Lecturas vía mmap               |
| **Índices compuestos**                           | Consultas por período/local     |
| **Caché en memoria** con `@_write`               | Sin repetir SQL                 |
| **`resumen_periodo` unificado**                  | Dashboard en 1 query            |
| **Paginación** (30 Inicio, 30 Historial, 40 POS) | 1200 movs → 30 widgets          |
| **`get_conn()` contextmanager**                  | Cierra conexiones, evita locks  |

---

## 5. Cómo probar y compilar

### Probar localmente

```bash
cd almacen_desktop_Flet
pip install -r requirements.txt
flet run main.py
```

**Dependencias**: `flet==1.0.3`, `openpyxl`, `fpdf2>=2.7.8`,
`Pillow>=10.0.0`.

### Ejecutar tests

```bash
python full_test.py
```

### Compilar `.exe` para Windows

**Recomendado**: usar `uv` para un entorno aislado y limpio.

```bash
# 1. Instalar uv (una sola vez)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# 2. Cerrar y reabrir la terminal para que uv quede en PATH

# 3. Desde la carpeta del proyecto
cd almacen_desktop_Flet
uv sync
uv run flet build windows
```

Tarda 5–15 min la primera vez. El `.exe` queda en:

```
build\windows\almacen-movil-raidel.exe
```

(Renombrable a `Almacen.exe` sin problema — Windows no exige que
coincida con nada del proyecto.)

### Distribuir

Empaqueta la carpeta completa de `build\windows\` como ZIP:

```bash
cd build
zip -r ../Almacen_CombosFlash_v1.0.zip windows/
```

El ZIP resultante es **portable**: se descomprime donde se quiera y
el usuario hace doble click en el `.exe`. La BD se crea al lado del
`.exe` (o en `%LOCALAPPDATA%\Almacen\` si no se puede escribir ahí).

---

## 6. Roles y permisos

| Acción                                      | admin | almacen | comun |
| ------------------------------------------- | :---: | :-----: | :---: |
| Ver productos / métricas / historial        |  ✅   |   ✅    |  ✅   |
| Entrada / Salida / Traspaso                 |  ✅   |   ✅    |  ❌   |
| Renombrar / Precio / Código / Baja / Granel |  ✅   |   ✅    |  ❌   |
| Categorías producto                         |  ✅   |   ✅    |  ❌   |
| POS / Nueva venta                           |  ✅   |   ✅    |  ❌   |
| Editar orden de venta                       |  ✅   |   ✅    |  ❌   |
| Anular orden completa                       |  ✅   |   ❌    |  ❌   |
| Clientes (CRUD + abonos)                    |  ✅   |   ✅    |  ❌   |
| Proveedores (CRUD + pagos)                  |  ✅   |   ✅    |  ❌   |
| Gastos (CRUD + categorías)                  |  ✅   |   ✅    |  ❌   |
| Caja (abrir/cerrar)                         |  ✅   |   ✅    |  ❌   |
| Devoluciones                                |  ✅   |   ✅    |  ❌   |
| Editar datos del negocio                    |  ✅   |   ✅    |  ❌   |
| Cerrar / Abrir tienda                       |  ✅   |   ❌    |  ❌   |
| Editar / Eliminar movimiento                |  ✅   | ✅ / ❌ |  ❌   |
| Gestionar usuarios                          |  ✅   |   ❌    |  ❌   |
| Excel / Backup / Import BD                  |  ✅   |   ✅    |  ✅   |

---

## 7. 📋 LO QUE FALTA — Roadmap de mejoras

### 🔴 Pendiente inmediato

#### 7.1 Etiquetas barcode / QR (impresión)

- Generación de etiquetas en PDF.
- Selector: CODE128 / EAN-13 / QR (o todos).
- Tamaño configurable (default 50×30mm).
- Contenido: código de barras + nombre + precio + moneda.
- Modo "imprimir por hoja A4 con grid" o "rollo individual".
- Cantidad de copias por producto.
- Campo opcional `codigo_barras` por producto.

**Tecnologías:** `python-barcode`, `qrcode`, `Pillow`, `fpdf2`.

### 🟡 Recomendable

#### 7.2 Gráficos en Dashboard

- Curva de ventas (últimos 30 días).
- Top categorías con barra.
- Top productos por ganancia.
- Comparativa mes vs mes.

**Tecnologías:** Flet built-in `LineChart`, `BarChart`, `PieChart`.

#### 7.3 Reportes adicionales

- **Ticket medio** por período.
- **Rotación de inventario** (días de stock).
- **Top por ganancia** (no solo por cantidad).
- **Productos estancados** (sin ventas en X días).
- **Auditoría por usuario** (filtro en Historial).
- **Reporte de utilidad neta** (ventas − costo − gastos).

#### 7.4 Impresión térmica

- Impresora 58mm / 80mm vía USB o red.
- Alternativa: el PDF 80mm se imprime desde el visor del sistema.

#### 7.5 Ticket con más opciones

- QR en el ticket con info fiscal.
- Numeración por local (configurable).
- Múltiples copias (cliente + negocio).
- Formato A4/A5.

### 🔴 Bloqueado por asesoría

#### 7.6 Reportes ONAT

- Para mipymes formales cubanas.
- Reportes fiscales mensuales configurables.

**No arrancable sin:**

1. Cliente real concreto.
2. Contador cubano que explique el formulario exacto.
3. Muestra del formulario lleno.

### 🟢 Opcional (v2.0)

#### 7.7 Multi-negocio

Separar negocios completos dentro de la misma app.

#### 7.8 Nómina / RRHH

- Trabajadores y puestos.
- Asistencia.
- Cálculo de nómina.

#### 7.9 Mesas / Cocina

Solo si el nicho objetivo son restaurantes o paladares.

#### 7.10 Sync en la nube

Requiere backend. Rompe el modelo offline-first.
Recomendado solo si aparece un cliente grande.

#### 7.11 Selector de paletas

**Esta versión (Combos Flash)** viene con la paleta roja de marca
fija. El **selector de 5 paletas** con persistencia por usuario está
planificado para la **versión pública genérica**
(`almacen-app-desktop`).

---

## 8. Análisis de mercado Cuba

### Puntuación global actual: **8.5 / 10**

| Dimensión          | Puntuación |
| ------------------ | ---------- |
| Núcleo inventario  | 9/10       |
| Multimoneda        | 10/10      |
| Offline-first      | 10/10      |
| Multi-local        | 9/10       |
| POS / Ventas       | 9/10       |
| Clientes           | 9/10       |
| Proveedores        | 8/10       |
| Gastos             | 9/10       |
| Caja               | 9/10       |
| Facturación        | 7/10       |
| Métodos de pago    | 8/10       |
| UI/UX              | 8/10       |
| Rendimiento        | 8/10       |
| Seguridad          | 7/10       |
| Estabilidad        | 7/10       |
| Códigos barras/QR  | 0/10       |
| Reportes avanzados | 6/10       |
| Gráficos           | 0/10       |
| ONAT               | 0/10       |

### Puntuación por segmento

- **Mayoristas / distribuidoras:** 9.5/10 — Ideal como está.
- **Paladares / cafeterías:** 8/10 — POS completo, falta mesas.
- **Mipymes formales:** 7/10 — Falta ONAT + gráficos.
- **Early adopters gratis:** 9.5/10 — Muy completa.

### Qué subiría la nota

- **Con etiquetas barcode + gráficos + reportes avanzados
  (2-3 semanas):** → **9.5/10**
- **Además ONAT:** → **10/10**

### Riesgos a conocer

1. **Windows-only por ahora.** Un port a macOS/Linux requiere
   recompilar con `flet build macos` / `flet build linux`.
2. **Flet 1.0.3 es joven.** Algunas integraciones nativas
   (impresoras, lectores de código de barras) requieren extensión
   Dart custom.
3. **Precio.** En Cuba es difícil cobrar. Modelo freemium sugerido.

---

## 9. Comparativa vs. competencia

| Aspecto            | Almacén (tuya) | Tu Cuadre   | Véndeme     | Bind ERP Cuba | QbanPOS     |
| ------------------ | -------------- | ----------- | ----------- | ------------- | ----------- |
| Offline real       | ✅             | ❌ (web)    | ❌ (web)    | ⚠️ parcial    | ⚠️ parcial  |
| Multimoneda real   | ✅             | ❌          | ❌          | ⚠️            | ❌          |
| Promedio ponderado | ✅             | ❌          | ❌          | ✅            | ❌          |
| Multi-local        | ✅             | ❌          | ⚠️          | ✅            | ⚠️          |
| Vista General      | ✅             | ❌          | ❌          | ❌            | ❌          |
| POS / ventas       | ✅             | ✅          | ✅          | ✅            | ✅          |
| Clientes + CC      | ✅             | ⚠️          | ⚠️          | ✅            | ✅          |
| Proveedores + CP   | ✅             | ⚠️          | ⚠️          | ✅            | ✅          |
| Gastos operativos  | ✅             | ✅          | ⚠️          | ✅            | ⚠️          |
| Caja               | ✅             | ✅          | ✅          | ✅            | ✅          |
| Ticket WhatsApp    | ✅             | ✅          | ✅          | ✅            | ✅          |
| QR / barcode       | ❌             | ⚠️          | ⚠️          | ✅            | ✅          |
| ONAT               | ❌             | ⚠️          | ❌          | ✅            | ❌          |
| Precio             | **Gratis**     | Suscripción | Suscripción | Caro          | Suscripción |
| App nativa         | ✅             | ❌          | ❌          | ⚠️            | ⚠️          |

**Tu jugada:** el sistema de inventario + POS + gestión que SÍ
funciona offline y SÍ entiende la multimoneda y la realidad cubana,
sin depender de la nube.

---

## 10. Stack técnico

| Capa            | Tecnología                     |
| --------------- | ------------------------------ |
| Frontend        | Flet 1.0.3 (Flutter 3.44.8)    |
| Lenguaje        | Python 3.12                    |
| Persistencia    | SQLite (WAL mode)              |
| Excel           | openpyxl                       |
| PDF             | fpdf2                          |
| Imágenes        | Pillow                         |
| Auth            | PBKDF2-HMAC-SHA256 (200k iter) |
| Compilación     | `flet build windows` vía `uv`  |
| Nombre del .exe | `almacen-movil-raidel.exe`     |
| Target          | Windows 10+ (x64)              |

---

## 11. Historial de versiones

### v1.0 — Desktop Combos Flash (actual)

**Base portada desde la versión Android v10.**

**Nuevo en esta versión desktop:**

- `rutas.py` portable: escribe al lado del `.exe`, con fallback a
  `%LOCALAPPDATA%`.
- `get_conn()` como contextmanager (fix del error `[Errno 22]` al
  importar la BD).
- Importador de BD robusto con `os.replace()` atómico y limpieza de
  WAL/SHM.
- `editar_movimiento()` en `inventario.py` (revierte y aplica stock).
- Drawer con `Stack` de posicionamiento absoluto (sin franja entre
  drawer y barra inferior).
- FAB del POS movido a la AppBar (ya no tapa el último producto).
- Iconos embebidos: `icon.png` + `icon.ico` multi-resolución.
- Dropdown de movimiento limitado a `ENTRADA` y `SALIDA`.
- Paleta Combos Flash fija (rojo de marca).

**Features heredadas del Android v10:**

- Inventario multi-local con vista General.
- POS con cobro mixto hasta 3 pagos.
- Clientes + cuentas por cobrar + abonos parciales.
- Proveedores + cuentas por pagar.
- Gastos operativos + categorías configurables.
- Caja con sesiones y cuadre (descuenta gastos de la sesión).
- Tickets PDF 80mm + PNG + texto plano.
- Devoluciones hasta 7 días.
- 9 métodos de pago configurables.
- Excel multi-hoja con moneda.
- Multimoneda CUP/USD/EUR con promedio ponderado.
- Esquema BD v10 + migración automática desde P1 (v4).

---

## 12. Cómo continuar desarrollo

1. **Antes de tocar código**, correr `python full_test.py`.
2. **Cambios pequeños**: probar con `flet run main.py`.
3. **Cambios grandes**: recompilar con
   `uv run flet build windows`.
4. **Nunca subir al repo**: `build/`, `.flet/`, `.venv/`, `datos/`,
   `backups/`, `logs/`, `tickets/`, `*.db`, `__pycache__/`.
5. **Backup antes de tocar**: desde Perfil → Backup.

### Flujo típico de trabajo

```bash
# Editar código
code .

# Probar en dev
flet run main.py

# Cuando esté listo, compilar
rm -rf build/ .flet/
export PATH="$HOME/.local/bin:$PATH"
uv run flet build windows

# Renombrar el .exe si quieres
mv build/windows/almacen-movil-raidel.exe build/windows/Almacen.exe

# Empaquetar
cd build
zip -r ../Almacen_CombosFlash_vX.Y.zip windows/

# Commit y push
cd ..
git add -A
git commit -m "descripción del cambio"
git push
```

### Próxima fase recomendada

**1. Probar el `.exe` en una PC limpia** (sin Python ni Flet
instalados). Verificar que:

- Se abre sin errores
- Iconos se ven correctamente
- Importar BD funciona
- Persistencia entre sesiones OK

**2. Con feedback real, arrancar Etiquetas barcode/QR.**

**3. Después: Gráficos + Reportes avanzados.**

**4. ONAT solo con asesor + cliente concreto.**

**5. Versión pública con selector de paletas** → repo separado
`almacen-app-desktop`.

---

## 13. Licencia y contacto

**Propietario:** Di-2003 / Combos Flash
**Repo:** https://github.com/Di-2003/almacen-app-desktop-ComboFlash
**Plataforma:** Windows 10+ (x64)
**Versión actual:** v1.0

Para reportar issues o sugerencias, abrir un issue en GitHub.
