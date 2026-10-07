# Almacén Raidel — App móvil (Combos Flash)

App **Android-only**, **offline-first** y **multi-local** para gestión de
almacén e inventario, con soporte **multimoneda (CUP / USD / EUR)**,
promedio ponderado de costos, propagación de precios entre locales,
Excel multi-hoja, backup manual a carpeta elegida e importación de BD.

Construida con **Python + Flet 1.0.3** sobre **Flutter 3.44.8**, SQLite
como almacenamiento local, y empaquetada como APK vía **GitHub Actions**.

---

## Tabla de contenidos

1. [Estado actual (v7 — Multimoneda)](#1-estado-actual-v7--multimoneda)
2. [Estructura del proyecto](#2-estructura-del-proyecto)
3. [Esquema BD v7](#3-esquema-bd-v7-resumen)
4. [Cómo probar y compilar](#4-cómo-probar-y-compilar)
5. [Roles y permisos](#5-roles-y-permisos)
6. [Roadmap de mejoras](#6--lo-que-falta--roadmap-de-mejoras)
7. [Comparativa vs. competencia](#7-lo-que-tienes-mejor-que-la-competencia)
8. [Stack técnico](#8-stack-técnico)
9. [Historial de versiones](#9-historial-de-versiones)
10. [Cómo continuar desarrollo](#10-cómo-continuar-desarrollo)
11. [Licencia y contacto](#11-licencia-y-contacto)

---

## 1. Estado actual (v7 — Multimoneda)

### ✅ Lo que YA está implementado

#### Núcleo de inventario

- **Multi-local real**: 1 Almacén + N tiendas + 1 vista virtual "General".
- **Alta de productos** con entrada, código auto-sugerido (formato
  `F[A-Z][0-9]{4}` → `FA0001`…`FZ9999`), cantidad, precio costo y venta.
- **Entrada** a producto existente o nuevo; auto-rellena stock actual.
- **Salida** con motivo libre (default "Venta"), rebaja por unidad
  validada contra el precio unitario.
- **Traspaso** entre locales con preview "Centro: 45→40 · Vedado: 20→25"
  y 2 movimientos con mismo `grupo_id`.
- **Dar de baja** producto (descatalogado, no puntual). **Reactivar**.
- **Propagación** de precio (costo + venta), código y nombre a TODOS
  los locales donde exista el mismo producto (por nombre).
- **Edición** de umbrales verde/amarillo por producto + editor masivo.
- **Cierre de tienda** con traspaso automático al Almacén y conservación
  del histórico. **Abrir** y **renombrar** tiendas (solo admin).

#### Multimoneda (Fases 1–3)

- Cada precio guarda **valor original** (en CUP/USD/EUR) **y valor CUP**
  calculado con la tasa actual.
- Dropdown de moneda en **entrada**, **P. costo** y **P. venta**.
- **Promedio ponderado** del costo en la moneda original del producto:
  `nuevo = (stock_antes × orig_antes + cant_nueva × orig_nueva) / total`.
- **Recálculo automático** de TODOS los precios en USD/EUR al cambiar
  la tasa desde Perfil. Los productos en CUP **no se tocan**.
- **Cambiar moneda** de un precio ya guardado (convierte el valor con
  las tasas actuales).
- **Selector de moneda de visualización** (CUP/USD/EUR) en Perfil.
- **Dashboard** muestra dinero en CUP y **≈ USD** al lado.

#### Historial y movimientos

- Tipos: `ENTRADA`, `SALIDA`, `BAJA`, `RESTAURACION`,
  `TRASPASO_SALIDA`, `TRASPASO_ENTRADA`, `UMBRAL`, `AJUSTE`.
- Filtros: Todos / Entradas / Salidas / Traspasos / Bajas.
- Búsqueda por producto, código o motivo.
- **Editar movimiento** (admin/almacén) con preview de impacto.
- **Eliminar movimiento** revirtiendo el stock automáticamente
  (incluye par de traspaso).

#### Roles y usuarios

- Roles: **admin**, **almacen**, **comun**.
- Validación **en capa de negocio** (`inventario.py`, `locales.py`,
  `usuarios.py`) — no solo en UI.
- Autenticación PBKDF2-HMAC-SHA256 (200k iteraciones).
- Editar perfil, resetear contraseña, activar/desactivar, eliminar.
- Un admin **no puede eliminarse a sí mismo** ni al último admin activo.

#### Datos y persistencia

- **SQLite** local (`FLET_APP_STORAGE_DATA/almacen.db`).
- **Backup Destino**: el usuario elige la carpeta (SAF en Android 11+).
- **Backup Interno**: guarda en la carpeta destino configurada.
- **Importar copia**: reemplaza la BD, con confirmación por contraseña.
- **Exportar Excel**: hojas fijas + una por local + una por moneda.

#### UI/UX

- Paleta **negro + dorado** con tema oscuro/claro.
- Navegación: bottom nav (Inicio / Métricas / Historial / Perfil).
- **Selector de local** en chip del AppBar (bottom sheet).
- Detalle de producto (bottom sheet) con todas las acciones.
- Snacks flotantes **15 s** con cierre por X.
- Diálogos que se cierran correctamente (sin cuelgues).
- Chip de estado como **punto de color** (sin texto).
- Autocompletado nombre/código en entrada y salida.
- **Fecha y hora** personalizable en entrada y salida.

#### Excel

- Hoja por local: `Código · Producto · Stock · Moneda · Costo orig. ·
Costo CUP · Venta orig. · Venta CUP · Costo Total · Venta Total · Margen`.
- Hoja `Movimientos` con cierre diario (rebajas, merma).
- Hoja `Ventas_<Local>` por cada local activo o histórico.
- Hoja `VentasGenerales` (resumen mensual histórico).

#### Compilación

- **GitHub Actions** compila el APK automáticamente al hacer push a `main`.
- Java 17, Flutter 3.44.8, Python 3.12, `flet==1.0.3`.
- **Anulación de `jni=1.1.0`** para resolver conflicto con `jni_flutter`.
- Permisos Android declarados (`READ/WRITE_EXTERNAL_STORAGE`,
  `MANAGE_EXTERNAL_STORAGE`).

---

## 2. Estructura del proyecto

```text
almacen_movil_Raidel/
├── main.py                       Entry Flet
├── rutas.py                      FLET_APP_STORAGE_DATA portable
├── db.py                         Esquema v7 (multimoneda)
├── seguridad.py                  PBKDF2
├── inventario.py                 Lógica stock + multimoneda + propagación
├── locales.py                    CRUD locales + General virtual + prefs
├── usuarios.py                   CRUD usuarios (capa negocio admin)
├── backup.py                     Copia con retención 30 días
├── excel_sync.py                 Excel multi-hoja con moneda
├── full_test.py                  Test exhaustivo (80+ tests)
├── pyproject.toml                Config Flet + permisos + jni override
├── requirements.txt              flet==1.0.3, openpyxl
├── README.md                     Este archivo
├── recursos/                     icon.png, login_bg.png, etc. (opcional)
├── datos/                        (runtime — BD)
├── backups/                      (runtime — backups)
├── .github/workflows/
│   └── build-apk.yml             Build APK
└── ui/
    ├── __init__.py
    ├── app.py                    Router + estado de sesión
    ├── estilos.py                Paleta + helpers + MONEDAS_INFO
    ├── componentes.py            Widgets base + cerrar_dialogo
    ├── login.py                  Login + primer arranque
    ├── principal.py              Inicio + selector local + búsqueda
    ├── dashboard.py              Métricas + margen CUP/USD
    ├── movimientos.py            Historial con filtros y editor
    ├── perfil.py                 Perfil + tasas + moneda visualización
    ├── admin_usuarios.py         Gestión usuarios (admin)
    ├── admin_locales.py          Abrir/cerrar tiendas (admin)
    ├── umbrales.py               Edición masiva
    ├── modales.py                Bottom sheets + diálogos
    └── exportar.py               FilePicker + Excel + BD
```

---

## 3. Esquema BD v7 (resumen)

```sql
productos (
    id, local_id, codigo, nombre, stock,
    umbral_verde, umbral_amarillo,
    precio_costo,        precio_unitario,          -- en CUP
    precio_costo_orig,   precio_unitario_orig,     -- en su moneda
    moneda_costo,        moneda_venta,             -- CUP|USD|EUR
    fecha_ultima_mod, activo
)

movimientos (
    id, local_id, producto_id, tipo, cantidad,
    motivo, grupo_id, detalle,
    rebaja, precio_unitario_momento,
    fecha, usuario
)

configuracion (
    umbral_verde_default, umbral_amarillo_default,
    motivo_default_salida, tema,
    tasa_usd, tasa_eur,
    moneda_visualizacion,
    backup_carpeta,
    local_actual:<username>
)
```

**Notas:**

- `VERSION_ESQUEMA = 7`. Si se detecta un esquema anterior, se dropea
  y se reinicia de cero.
- `GENERAL_ID = -1` (vista virtual, nunca se persiste).
- `precio_costo` y `precio_unitario` están siempre en CUP para que
  sumas, márgenes y totales funcionen.
- `*_orig` guardan el valor original para recalcular al cambiar la tasa.

---

## 4. Cómo probar y compilar

### Probar localmente

```bash
cd almacen_movil_Raidel
pip install -r requirements.txt
flet run main.py
```

### Ejecutar tests

```bash
python full_test.py
```

Debe dar `✅ TODOS LOS TESTS PASARON (81/81)`.

### Compilar APK (GitHub Actions)

```bash
git add -A
git commit -m "Descripción del cambio"
git push origin main
```

Espera ~10–15 min y descarga el APK desde
`Actions → Build APK → Artifacts → almacen-raidel-apk`.

---

## 5. Roles y permisos

| Acción                               | admin | almacen | comun |
| ------------------------------------ | :---: | :-----: | :---: |
| Ver productos / métricas / historial |  ✅   |   ✅    |  ✅   |
| Entrada / Salida / Traspaso          |  ✅   |   ✅    |  ❌   |
| Renombrar / Precio / Código / Baja   |  ✅   |   ✅    |  ❌   |
| Cerrar / Abrir tienda                |  ✅   |   ❌    |  ❌   |
| Editar movimiento                    |  ✅   |   ✅    |  ❌   |
| Eliminar movimiento                  |  ✅   |   ❌    |  ❌   |
| Gestionar usuarios                   |  ✅   |   ❌    |  ❌   |
| Excel / Backup / Import BD           |  ✅   |   ✅    |  ✅   |

---

## 6. 📋 LO QUE FALTA — Roadmap de mejoras

El proyecto está funcional y estable. Para sacarlo al mercado con
competitividad, este es el plan priorizado.

### 🔴 Crítico (necesario antes de vender)

#### 6.1 Módulo de Ventas / POS

Sin esto la app es "sistema de inventario", no "sistema de gestión".

- Pantalla de **Nueva Venta** con carrito.
- Cliente (opcional al principio, obligatorio con cuenta).
- Selección de método de pago (efectivo, transferencia, Zelle).
- Cobro en CUP/USD/EUR con tasa del día.
- Guardar venta como **orden de venta** (no solo como salida).
- Ticket / recibo descargable o imprimible.
- Cierre diario de caja.

#### 6.2 Clientes

- CRUD de clientes (nombre, teléfono, dirección, notas).
- Historial de compras por cliente.
- Cuentas por cobrar (ventas a crédito).
- Ticket medio por cliente.

#### 6.3 Proveedores

- CRUD de proveedores.
- Asociar entradas a proveedores (saber a quién le compras).
- Órdenes de compra formales.

#### 6.4 Categorías de productos

- CRUD de categorías (Bebidas, Limpieza, Alimentos, etc.).
- Asociar productos a categorías.
- Filtro por categoría en Inicio y Dashboard.
- Reporte de ventas por categoría.

#### 6.5 Gastos operativos

- Registrar gastos (luz, agua, alquiler, salario).
- Categorías de gastos.
- Reporte de gastos mensuales.
- Balance: ingresos − gastos.

### 🟡 Recomendable (a medio plazo)

#### 6.6 Dashboard con filtro temporal

Copiar el patrón de Tu Cuadre: **Hoy / Semana / Mes / Año**.
Actualmente solo hay "Hoy / 7 días / 30 días / Total".

#### 6.7 Gráficos en Dashboard

- Curva de ventas (últimos 30 días).
- Comparativa mes vs mes.
- Top categorías con gráfico de barras.

#### 6.8 Ticket / Recibo

- Generar PDF del ticket.
- Compartir por WhatsApp/Telegram.
- Impresora térmica Bluetooth (opcional).

#### 6.9 Códigos de barras / QR

- Escanear con cámara para entrada/salida rápida.
- Generar QR/código de barras para cada producto.
- Imprimir etiquetas.

#### 6.10 Órdenes de compra

- Crear orden de compra a proveedor.
- Estados: pendiente, recibido, cancelado.
- Recepción parcial.

#### 6.11 Cuentas por cobrar / pagar

- Ventas a crédito.
- Pagos parciales.
- Vencimientos y alertas.

#### 6.12 Métricas adicionales

- **Ticket medio**.
- **Rotación de inventario** (días de stock).
- **Top por ganancia** (no solo top por cantidad).
- **Productos estancados** (sin ventas en X días).

#### 6.13 Auditoría por usuario

- Filtro de movimientos por usuario.
- Vista de actividad por usuario.
- Log de cambios sensibles (precios, códigos, bajas).

### 🟢 Opcional (versión 2.0)

#### 6.14 Multi-negocio

Separar negocios completos dentro de la misma app.

#### 6.15 Nómina / RRHH

- Trabajadores y puestos.
- Asistencia.
- Nómina definida.

#### 6.16 Mesas / Cocina

Solo si el nicho es restaurantes.

#### 6.17 Contabilidad / ONAT

Reportes fiscales para Cuba.

#### 6.18 Zonas de entrega

Si hay delivery.

#### 6.19 Métodos de pago configurables

El usuario decide cuáles aparecen en el POS.

#### 6.20 Fichas técnicas / elaboración

Para negocios que producen (kits, combos).

#### 6.21 Sincronización en la nube

Requiere backend. Rompe el modelo offline-first actual.
Recomendado solo si hay cliente grande que lo pida.

---

## 7. Lo que TIENES MEJOR que la competencia

| Aspecto                        | Almacén Raidel                               | Tu Cuadre             |
| ------------------------------ | -------------------------------------------- | --------------------- |
| Multimoneda real               | CUP/USD/EUR con tasas congeladas + recálculo | Solo muestra CUP      |
| Promedio ponderado             | Cálculo correcto del costo real              | No se ve              |
| Offline-first                  | 100% SQLite local                            | Parece app web        |
| Multi-local en una app         | Cambias de local con un chip                 | Cada negocio separado |
| Vista General                  | Suma automática de todos los locales         | No aparece            |
| Simplicidad                    | 4 tabs + 15 pantallas                        | 50+ secciones         |
| App nativa Android             | APK nativa                                   | Web con wrapper       |
| Backup manual a carpeta        | Control total del usuario                    | (no se ve)            |
| Cierre de tienda con histórico | Datos preservados en Excel                   | (no se ve)            |
| Gratis                         | Auto-hospedado, sin suscripción              | Suscripción mensual   |

---

## 8. Stack técnico

| Capa            | Tecnología                       |
| --------------- | -------------------------------- |
| Frontend        | Flet 1.0.3 (Flutter 3.44.8)      |
| Lenguaje        | Python 3.12                      |
| Persistencia    | SQLite (archivo local)           |
| Excel           | openpyxl                         |
| Auth            | PBKDF2-HMAC-SHA256 (200k iter)   |
| Compilación APK | GitHub Actions + flet build apk  |
| Package name    | `com.combosflash.almacen_raidel` |

---

## 9. Historial de versiones

### v7 — Multimoneda (actual)

- Fase 1: schema v7 con `moneda_*` y `*_orig`, promedio ponderado.
- Fase 2: recálculo automático al cambiar tasa + cambio de moneda.
- Fase 3: Excel con columnas de moneda + margen dual CUP/USD.
- Fix: `jni=1.1.0` override para build Android.
- Fix: `cerrar_dialogo` robusto (sin cuelgues).
- Fix: snack flotante 15 s con X.
- Fix: chip de estado como punto (sin texto).
- Fix: autocompletado nombre/código + fecha editable.
- Fix: eliminar movimiento revierte stock.
- Fix: totales por concepto en Dashboard.
- Fix: motivo default = "Venta".
- Fix: entrada a producto existente no falla por código duplicado.

### v6 — Multi-local

- Almacén + N tiendas + General virtual.
- Códigos Fxyyyy, propagación completa.
- Traspasos, cierre de tienda.
- Excel multi-hoja.
- Roles y permisos.

### v5 — Base

- Login + primer arranque.
- CRUD productos.
- Entrada / Salida / Baja.
- Umbrales verde/amarillo.
- Backup interno.

---

## 10. Cómo continuar desarrollo

1. **Antes de tocar código**, corre `python full_test.py`.
   Debe dar **81/81**.
2. **Cambios pequeños**: push a `main` → GitHub Actions compila.
3. **Cambios grandes**: probar local con `flet run main.py` primero.
4. **Nunca subir**: `datos/`, `backups/`, `.flet/`, `*.db`.
5. **Backup antes de tocar**: el usuario puede exportar desde Perfil.

### Para empezar una nueva funcionalidad

Empezar por la **Fase A — Módulo de Ventas / POS**, que es el
diferenciador #1 para salir al mercado. Estructura sugerida:

```text
├── ventas.py                Lógica de órdenes de venta (capa negocio)
├── clientes.py              CRUD clientes
├── ui/
│   ├── pos.py               Pantalla de nueva venta (carrito)
│   ├── ordenes.py           Listado de órdenes
│   ├── clientes.py          CRUD clientes
│   └── ticket.py            Generación de ticket PDF
```

Tablas nuevas en BD (v8):

```sql
CREATE TABLE clientes (...);
CREATE TABLE ordenes_venta (...);
CREATE TABLE orden_items (...);
CREATE TABLE pagos (...);
CREATE TABLE categorias (...);
CREATE TABLE proveedores (...);
CREATE TABLE gastos (...);
```

---

## 11. Licencia y contacto

**Propietario:** Di-2003 / Combos Flash
**Repo:** https://github.com/Di-2003/almacen_movil_Raidel
**Package:** `com.combosflash.almacen_raidel`
**Target device:** Android 7+ (minSdk 24)

Para reportar issues o sugerencias, abrir un issue en GitHub.
