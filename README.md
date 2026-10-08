# Almacén — App móvil (Combos Flash)

App **Android-only**, **offline-first** y **multi-local** para gestión
de almacén, inventario, punto de venta (POS), clientes, proveedores,
gastos, caja, tickets y devoluciones. Soporte completo
**multimoneda (CUP / USD / EUR)**, **5 paletas × claro/oscuro**,
**promedio ponderado de costos**, **propagación de precios**,
**cuentas por cobrar y por pagar**, **Excel multi-hoja**, y backup
manual/importación de BD.

Construida con **Python + Flet 1.0.3** sobre **Flutter 3.44.8**, SQLite
local, y empaquetada como APK vía **GitHub Actions**.

---

## Tabla de contenidos

1. [Estado actual (v10)](#1-estado-actual-v10)
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

## 1. Estado actual (v10)

### ✅ Lo que YA está implementado

#### Inventario (v5–v8)

- **Multi-local**: 1 Almacén + N tiendas + 1 vista virtual "General".
- **Alta de productos** con código auto-sugerido (`F[A-Z][0-9]{4}`).
- **Entrada**, **Salida** (con motivo y rebaja), **Traspaso**.
- **Dar de baja** / **Reactivar** producto.
- **Propagación** de precio, código, nombre, categoría y flag de
  granel a TODOS los locales.
- **Consistencia de códigos**: un nombre → un código global.
- **Multimoneda real** con valor original + CUP + promedio ponderado.
- **Roles** admin/almacen/comun validados en capa de negocio.

#### POS / Ventas (v9–v10)

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

#### Clientes (v9)

- **CRUD completo** con límite de crédito.
- **Cuentas por cobrar** con abonos parciales.
- **Historial de compras** por cliente.
- **Vista "cuentas por cobrar"**.

#### Proveedores (v10)

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

#### Gastos operativos (v10)

- **CRUD completo** con categorías configurables
  (Luz, Agua, Alquiler, Salario, Transporte, Otros).
- **Moneda CUP/USD/EUR** con conversión automática.
- **Gastos por local o globales**.
- **Switch "Pagado de la caja abierta"** → afecta el cuadre de caja.
- **Filtros** por período (Hoy/Semana/Mes/Año/Total), local y categoría.
- **Total del período** en vivo.
- **Utilidad neta en Dashboard** (Ganancia − Gastos).

#### Caja (v9–v10)

- **Múltiples sesiones por día** por usuario.
- **Cálculo del saldo esperado**:
  `inicial + Σpagos + Σabonos − Σgastos de la sesión`.
- **Cierre con conteo físico** y cálculo de diferencia.
- **Resumen por método** de pago y abonos.
- **Historial** de sesiones cerradas.

#### Tickets (v9)

- **PDF 80mm** (formato térmico) con `fpdf2`.
- **PNG 440px** para compartir por WhatsApp (Pillow).
- **Ticket en texto plano** para copiar al portapapeles.
- **Datos del negocio** configurables.
- **Diálogo "Preparar envío"** que guarda PDF + PNG y copia el texto.

#### Devoluciones (v9)

- **Parcial o total**, hasta **7 días** de la venta.
- **Revierte stock** con movimiento `ENTRADA`.
- **Ajusta saldo pendiente** de la orden si era fiado.
- **Motivo** obligatorio.

#### Paletas (v9)

- **5 paletas**: Negro + Dorado, Azul, Verde, Rojo, Púrpura.
- **2 modos**: claro y oscuro.
- **10 combinaciones** totales.
- **Persistencia** por usuario.

#### Herramientas

- **`full_test.py`**: **134 tests**.
  ```
  python full_test.py   → ✅ TODOS LOS TESTS PASARON (134/134)
  ```
- **`seed_data.py`**: puebla la BD con datos de prueba masivos.
- **`diagnostico.py`**: muestra ubicación de la BD según contexto.

---

## 2. Estructura del proyecto

```text
almacen_movil_Raidel/
├── main.py                       Entry Flet
├── rutas.py                      FLET_APP_STORAGE_DATA portable
├── db.py                         Esquema v10 + migración no destructiva
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
├── full_test.py                  Test exhaustivo (134 tests)
├── seed_data.py                  Genera datos masivos de prueba
├── diagnostico.py                Muestra ubicación de la BD
├── pyproject.toml                Config Flet + dependencias
├── requirements.txt              flet, openpyxl, fpdf2, Pillow
├── README.md                     Este archivo
├── .gitignore
├── .github/workflows/
│   └── build-apk.yml             Build APK
├── recursos/                     icon.png (obligatorio), login_bg.png, etc.
└── ui/
    ├── __init__.py
    ├── app.py                    Router + estado + drawer + carrito POS
    ├── estilos.py                5 paletas + helpers + MONEDAS_INFO
    ├── componentes.py            Widgets + snack + toast + modales
    ├── drawer.py                 Panel lateral
    ├── login.py                  Login dinámico + primer arranque
    ├── principal.py              Inicio + chips + selector tipos + FAB POS
    ├── dashboard.py              Métricas + Gastos + Utilidad neta
    ├── movimientos.py            Historial + paginación
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
    ├── paletas.py                Selector de paletas + modo
    ├── admin_usuarios.py         Gestión usuarios (admin)
    ├── admin_locales.py          Abrir/cerrar tiendas (admin)
    ├── admin_categorias.py       CRUD tipos de producto
    ├── umbrales.py               Edición masiva
    ├── modales.py                Bottom sheets + entrada/salida/traspaso
    └── exportar.py               FilePicker + Excel + BD
```

---

## 3. Esquema BD v10

**Migración v9 → v10 no destructiva** (`CREATE TABLE IF NOT EXISTS`

- `ALTER TABLE ADD COLUMN`). Los datos de v9 se conservan.

```sql
-- TABLAS v8
meta, locales, usuarios, configuracion, categorias, productos,
movimientos (con proveedor_id opcional)

-- TABLAS v9
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

---

## 5. Cómo probar y compilar

### Probar localmente

```bash
cd almacen_movil_Raidel
pip install -r requirements.txt
flet run main.py
```

**Dependencias:** `flet==1.0.3`, `openpyxl`, `fpdf2>=2.7.8`,
`Pillow>=10.0.0`.

### Poblar con datos de prueba

```bash
python seed_data.py
```

### Ejecutar tests

```bash
python full_test.py
```

Debe dar **✅ TODOS LOS TESTS PASARON (134/134)**.

### Compilar APK

```bash
git add .
git commit -m "descripción"
git push origin main
```

Espera ~10–15 min y descarga desde
`Actions → Build APK → Artifacts → almacen-raidel-apk`.

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
| Paletas y modo                              |  ✅   |   ✅    |  ✅   |

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

#### 7.4 Impresión térmica Bluetooth

- Impresora 58mm / 80mm.
- Requiere extensión Dart (`flutter_blue_plus` + `esc_pos_utils`).
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

#### 7.7 Escaneo con cámara

Requiere **extensión Dart custom** con `mobile_scanner`. Alto riesgo:
documentación escasa, compatibilidad con Flutter 3.44.8, permisos
runtime. Recomendado solo cuando la app esté estable y con clientes.

#### 7.8 Multi-negocio

Separar negocios completos dentro de la misma app.

#### 7.9 Nómina / RRHH

- Trabajadores y puestos.
- Asistencia.
- Cálculo de nómina.

#### 7.10 Mesas / Cocina

Solo si el nicho objetivo son restaurantes o paladares.

#### 7.11 Sync en la nube

Requiere backend. Rompe el modelo offline-first.
Recomendado solo si aparece un cliente grande.

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
| Paletas            | 10/10      |
| UI/UX              | 8/10       |
| Rendimiento        | 8/10       |
| Seguridad          | 7/10       |
| Estabilidad        | 6/10       |
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
- **Además ONAT + cámara:** → **10/10**

### Riesgos a conocer

1. **Android real vs Windows dev.** Falta probar el APK en móvil.
2. **Flet 1.0.3 es joven.** Los plugins de cámara, Bluetooth y
   notificaciones no están todos disponibles. Algunos requieren
   escribir extensión Dart.
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

| Capa            | Tecnología                       |
| --------------- | -------------------------------- |
| Frontend        | Flet 1.0.3 (Flutter 3.44.8)      |
| Lenguaje        | Python 3.12                      |
| Persistencia    | SQLite (WAL mode)                |
| Excel           | openpyxl                         |
| PDF             | fpdf2                            |
| Imágenes        | Pillow                           |
| Auth            | PBKDF2-HMAC-SHA256 (200k iter)   |
| Compilación APK | GitHub Actions + flet build apk  |
| Package name    | `com.combosflash.almacen_raidel` |
| Nombre launcher | `Almacen`                        |

---

## 11. Historial de versiones

### v10 — Gastos + Proveedores + Editar orden (actual)

**Gastos operativos:**

- Tablas `categorias_gastos` y `gastos`.
- CRUD con moneda CUP/USD/EUR.
- Gastos por local o globales.
- Switch "Pagado de la caja abierta" → afecta cuadre.
- Filtros por período, local y categoría.
- Utilidad neta en Dashboard.

**Proveedores:**

- Tabla `proveedores` + `producto_proveedores` (N:M) +
  `pagos_proveedor`.
- Capitalización de cada palabra del nombre.
- Relación N:M producto↔proveedor por nombre (global).
- Proveedor principal opcional por producto.
- Cuentas por pagar con saldo vivo.
- Auto-asociación al dar entrada con proveedor.
- Crear proveedor inline desde entrada y detalle de producto.
- Modal de gestión de proveedores por producto.

**POS:**

- Editar orden de venta (cambiar cantidad, quitar ítems).
- Validación de stock al agregar y editar.
- Toast arriba en lugar de snackbar abajo.

**UI:**

- Botones a ancho completo en listas.
- Modales con X arriba a la derecha.
- Toggles verde/gris para activo/inactivo.
- Textos largos con `max_lines` + `ellipsis`.

**Tests:**

- `full_test.py` → **134/134**.

### v9 — POS + Clientes + Caja + Tickets + Paletas

- POS con carrito y cobro mixto (3 pagos).
- Clientes + cuentas por cobrar + abonos parciales.
- Caja con sesiones y cuadre.
- Tickets PDF 80mm + PNG + texto.
- Devoluciones (7 días).
- Métodos de pago configurables (9 por defecto).
- 5 paletas × claro/oscuro.
- Flag de granel.
- 87 tests.

### v8 — Categorías + Métricas + Rendimiento

- Tabla `categorias` con CRUD.
- `precio_costo_momento` en movimientos.
- Chips de período calendario.
- Consistencia de códigos global.
- WAL + PRAGMAs + caché.
- 99 tests.

### v7 — Multimoneda

- Schema v7 con `moneda_*` y `*_orig`.
- Recálculo automático al cambiar tasa.

### v6 — Multi-local

- Almacén + N tiendas + General virtual.

### v5 — Base

- Login + primer arranque.
- CRUD productos.
- Entrada / Salida / Baja.
- Umbrales verde/amarillo.

---

## 12. Cómo continuar desarrollo

1. **Antes de tocar código**, correr `python full_test.py`.
   Debe dar **134/134**.
2. **Cambios pequeños**: push a `main` → GitHub Actions compila.
3. **Cambios grandes**: probar local con `flet run main.py`.
4. **Nunca subir**: `.flet/`, `datos/`, `backups/`, `*.db`,
   `__pycache__/`, `_test_full/`, `tickets/`.
5. **Backup antes de tocar**: desde Perfil.

### Próxima fase recomendada

**1. Probar el APK en móvil real (Redmi 12 y Redmi 14).**

- Login → Inicio → POS → venta → ticket.
- Clientes → fiado → abono.
- Proveedores → crear → producto → entrada.
- Gastos → crear → dashboard → utilidad neta.
- Caja → abrir → vender → gasto → cerrar.
- Cambiar paleta → persistencia.

**2. Con feedback real, arrancar Etiquetas barcode/QR.**

**3. Después: Gráficos + Reportes avanzados.**

**4. ONAT solo con asesor + cliente concreto.**

---

## 13. Licencia y contacto

**Propietario:** Di-2003 / Combos Flash
**Repo:** https://github.com/Di-2003/almacen_movil_Raidel
**Package:** `com.combosflash.almacen_raidel`
**Target device:** Android 7+ (minSdk 24)

Para reportar issues o sugerencias, abrir un issue en GitHub.
