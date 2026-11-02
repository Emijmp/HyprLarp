# HyprLarp

Un shell para Hyprland construido con **Quickshell / Qt Quick**, inspirado en la organización modular de [Noctalia](https://noctalia.dev/shell). **AMOLED Black**, negro puro y borde exterior blanco de 1 px. Cada módulo de barra tiene su propio fondo gris oscuro, borde discreto y radio de 2 px. La app incluye **Gruvbox Dark, Catppuccin Mocha, Oxocarbon, Tokyo Night, One Dark Pro** y un **tema personalizado**. No requiere instalar Noctalia.

![HyprLarp · vista previa real del shell](docs/preview.png)

## Probar desde el repositorio

Necesitas Quickshell **0.3.2+**, Qt 6 con Qt Quick Controls y Qt SVG, Python **3.10+** y **Hyprland 0.57+** con configuración Lua para usar las integraciones del sistema.

```sh
./bin/hyprlarp doctor
./bin/hyprlarp preview
```

La vista previa abre una ventana normal. Usa datos reales disponibles, no registra un daemon de notificaciones, no inicia la captura del portapapeles y desactiva acciones de red, audio, energía, USB y sesión. Tampoco aplica el filtro nocturno. Sus ajustes se guardan por separado en `$XDG_CACHE_HOME/hyprlarp/preview` (por defecto `~/.cache/hyprlarp/preview`). Puedes explorar aplicaciones, paneles, temas y la configuración sin sustituir tu escritorio; el botón Probar OSD muestra una demostración identificada como Prueba.

Para iniciar el shell real desde este checkout:

```sh
./bin/hyprlarp run
```

Para probar sus notificaciones, una vez activo:

```sh
notify-send 'HyprLarp' 'Notificación de prueba'
```

Solo puede haber un servidor de notificaciones de escritorio a la vez. Si tu sesión inicia otro, cambia su entrada de arranque por HyprLarp para usar estos avisos e historial.

## Qué incluye

| Función | Implementación |
| --- | --- |
| Barra flotante | En todos los monitores; cuatro posiciones, ajustes por monitor y zonas inicio/centro/final; módulos con fondos individuales que se pueden añadir, quitar y reordenar arrastrando o con flechas. Espacios activos por monitor, actualizados mediante eventos de Hyprland. |
| Launcher | Centrado en la pantalla donde lo abres, con iconos de aplicaciones `.desktop`, búsqueda con tolerancia a errores, favoritos, recientes y navegación con flechas y Enter. Usa el índice nativo de Quickshell. |
| Centro de control | Una columna de texto con Wi-Fi, Bluetooth, No molestar, volumen, brillo y acciones del sistema. Multimedia aparece solo si hay un reproductor. |
| Wi-Fi | Redes disponibles, búsqueda, conexiones guardadas o con contraseña, conexión y desconexión mediante NetworkManager. |
| Bluetooth | Encendido, búsqueda, vinculación simple, conexión y desconexión con BlueZ. |
| Notificaciones | Avisos, acciones, No molestar, búsqueda, grupos y filtro por aplicación; reglas de avisos, historial y sonido por aplicación. |
| Portapapeles | Texto e imágenes con `wl-paste` / `cliphist`; fijados persistentes, miniaturas, pausa, búsqueda, caducidad opcional y limpieza sin borrar fijados. |
| Multimedia | Reproductores MPRIS, reproducción, anterior/siguiente, selección de reproductor y posición si la aplicación lo permite. |
| Reloj y calendario | Hora y calendario mensual con navegación; semana desde el lunes. |
| Sesión y bloqueo | Menú con confirmación para salir, reiniciar o apagar. Pantalla de bloqueo con `hyprlock`. Suspensión con bloqueo a través de `hypridle`. |
| Capturas | Región, ventana activa y escritorio; temporizador; editor de recorte, flechas, texto y ocultación sólida; PNG guardado y copiado. |
| Recursos | CPU, RAM, disco, red, temperatura disponible y tiempo activo. Muestreo cada 2 segundos mientras se ve el módulo, Recursos o el centro de control. |
| Batería | Carga, salud/desgaste, capacidad actual y de diseño, ciclos, potencia, voltaje, temperatura, límites de carga y tiempo restante cuando el equipo los informa. Las estimaciones están identificadas. |
| Energía | Perfiles de ahorro, equilibrado y rendimiento mediante power-profiles-daemon; solo ofrece los perfiles compatibles con el equipo. |
| OSD | Indicadores de volumen, micrófono y brillo; posición superior/inferior y duración configurables. No aparecen al iniciar ni al sustituir un dispositivo. |
| Modo nocturno | Filtro cálido con hyprsunset, de 1000 a 6500 K, activación manual o por horario que admite cruzar medianoche. Desactivado inicialmente. |
| USB | Lista de periféricos conectados; montar, abrir, desmontar y expulsar unidades de datos con UDisks. Sin montaje automático. |
| Fondos | Fondos lisos de los tres temas, miniaturas y carpeta personal; el shell dibuja el fondo en cada monitor. |
| Configuración | Buscador, campos numéricos, selector RGB, seis temas y paletas propias; perfiles, importar/exportar y reset por sección. Deshacer, rehacer y restablecer solo desde esta ventana. |
| Audio | Selección nativa de salida/entrada, micrófono, silencio y volumen por aplicación con PipeWire. |
| Bandeja | Módulo opcional con iconos ocultables y menús contextuales nativos. |
| Presentación | Suprime avisos y sonidos e inhibe el reposo automático mediante Wayland mientras está activo. |

Los datos ausentes aparecen como no disponibles. No se simulan conexiones, canciones ni dispositivos. El soporte de reproducción y búsqueda de posición depende de las capacidades MPRIS de cada aplicación. Las redes empresariales/VPN usan `nm-connection-editor` y el emparejamiento Bluetooth con PIN usa `blueman-manager`, accesibles desde los paneles. El botón Mezclador abre el panel nativo de audio.

Capturas de la implementación: [información de batería](docs/battery.png), [OSD de prueba](docs/osd.png), [modo nocturno](docs/night-light.png) y [preferencias del OSD](docs/general-settings.png).

![Launcher centrado con iconos de aplicaciones](docs/launcher.png)

Los iconos usan el tema instalado de Qt/GTK. Si la plataforma Qt no publica las rutas de iconos, el shell resuelve los archivos locales una sola vez y guarda los resultados en memoria. `QS_ICON_THEME=Papirus-Dark ./bin/hyprlarp run` permite elegir explícitamente un tema instalado; la variable está [documentada por Quickshell](https://quickshell.org/docs/v0.3.2/types/Quickshell/Quickshell/).

![Ventana de configuración de HyprLarp](docs/settings.png)

## Deshacer, rehacer y restablecer

La cabecera de configuración tiene **Deshacer**, **Rehacer** y **Restablecer…**. Estas acciones y sus atajos se habilitan únicamente mientras la ventana de configuración está abierta y enfocada. Fuera de ella, Ctrl + Z conserva el comportamiento de la aplicación activa. El historial registra exclusivamente los ajustes hechos desde configuración; los cambios realizados desde otros paneles del shell se conservan al deshacer o rehacer.

El historial conserva hasta **50 cambios de configuración guardados durante la sesión del shell**, incluso al cerrar y volver a abrir su ventana. Se vacía al reiniciar el backend, el shell o cerrar la app independiente. Cada arrastre de slider se guarda como una sola operación; el cambio de tema y su acento también se deshacen juntos.

| Atajo en configuración | Acción |
| --- | --- |
| Ctrl + Z | Deshacer |
| Ctrl + Shift + Z / Ctrl + Y | Rehacer |

**Restablecer… → Restablecer todo** recupera AMOLED y todos los ajustes iniciales, incluida la paleta personalizada. Puede deshacerse. Conserva los historiales de notificaciones y portapapeles. El botón **Restablecer sección…** afecta a la página actual; en Barra y Módulos respeta el monitor seleccionado. Los cambios de atajos se activan con **Aplicar atajos** en su pestaña, después de guardar toda la cola pendiente.

![Confirmación de restablecer la configuración](docs/reset-settings.png)

## Temas y colores personalizados

En **Apariencia**, elige AMOLED Black, Gruvbox Dark, Catppuccin Mocha, Oxocarbon, Tokyo Night o One Dark Pro. **Personalizar este tema** crea una copia editable de la paleta activa. También puedes elegir directamente **Personalizado** para recuperar tu paleta guardada.

El editor permite dar nombre al tema y elegir un color con el selector RGB de cada muestra o escribirlo en formato `#RRGGBB` el fondo de escritorio, barra y paneles, hover, fondo de módulos, bordes, separadores, texto e iconos, texto secundario, acento y alertas. Se aplica al terminar cada campo y se guarda automáticamente. La paleta personalizada se conserva al elegir otro tema y al reiniciar; sus cambios admiten deshacer y rehacer. El bloqueo usa sus colores al abrirse.

![Editor de paleta personalizada](docs/custom-theme.png)

## Redondez

En **Configuración → Apariencia → Redondez** puedes ajustar un radio general de **0–8 px** y definir valores independientes para barra, paneles y configuración, botones/casillas, campos, espacios de trabajo, avisos y ayudas emergentes. **Heredar radio general** elimina la excepción de ese tipo de elemento; 0 conserva las esquinas rectas. Estos cambios se guardan y admiten deshacer, rehacer y restablecer desde configuración.

La redondez de los módulos sigue en **Módulos → Aspecto → Radio**, también de 0–8 px y con los ajustes por monitor. Se ha eliminado el pequeño trazo decorativo superior de los módulos.

## Perfiles y biblioteca

En **Configuración → Perfiles**, guarda la configuración actual con un nombre o guarda solo su paleta. Puedes mantener hasta 50 perfiles y 50 temas. Aplicar un perfil, importar o aplicar una paleta admite deshacer y conserva una copia previa en `settings.backup.json`. La biblioteca se guarda en `library.json`; no se elimina con Restablecer todo.

Los botones Importar / Exportar usan JSON local con tipo y versión explícitos. Los perfiles incluyen apariencia, barra, módulos, ajustes por monitor y preferencias; excluyen el estado temporal de No molestar y la pausa del portapapeles. Los formatos inválidos se rechazan antes de cambiar la configuración.

La captura del portapapeles se pausa desde su panel. Los fijados son copias privadas de hasta 16 MiB por entrada y 50 entradas; siguen disponibles al vaciar cliphist. Las miniaturas se generan al necesitarse, con una caché de 16 imágenes. La caducidad se configura en General, está desactivada con 0 horas y cuenta desde que se observa cada entrada; no borra fijados.

Los sonidos de notificaciones están desactivados por defecto. En General puedes activar sonido y decidir avisos e historial por aplicación. Presentación se controla desde el centro de control o su atajo; inhibe el reposo automático mientras está activo sin modificar los tiempos de hypridle. El bloqueo manual sigue disponible.

El servicio intenta recuperarse con esperas de 1, 2 y 4 segundos, hasta tres intentos; los cambios de preferencias pendientes se conservan y se reenvían. Las acciones de red, sesión y capturas no se repiten automáticamente. El historial de deshacer del backend se vacía tras un reinicio.

## Ajustes de barra

![Configuración de geometría y espaciado de la barra](docs/bar-settings.png)

Abre **Configuración → Barra** con el botón derecho sobre la barra o con `./bin/hyprlarp settings`.

| Ajuste | Opciones |
| --- | --- |
| Posición | Superior, inferior, izquierda o derecha. |
| Longitud y alineación | 25–100% del espacio disponible; inicio, centro o final. |
| Grosor | 22–128 px; el mínimo respeta el tamaño del contenido y el padding. |
| Padding | Horizontal y vertical, por separado. |
| Márgenes | Superior, derecho, inferior e izquierdo independientes; admiten cero. |
| Separación | Distancia entre módulos; admite cero. |
| Borde | 0–4 px, sólido y sin transparencia; blanco en AMOLED. |
| Opacidad | Fondo de la barra de 0 a 100%; el borde conserva su color. |
| Blur | Opcional, apagado inicialmente. Se solicita solo para la región de la barra. |
| Texto e iconos | Tamaños independientes, etiquetas y cantidad de espacios de trabajo. |
| Reserva de espacio | Permite que las ventanas respeten el área de la barra o la ocupen. |

En **Configuración → Apariencia → Detalles visuales**, elige **Sutil** para los pequeños trazos, indicadores y remates geométricos, o **Mínimo** para eliminarlos. Se conservan el negro AMOLED, los bordes sólidos, las esquinas pequeñas y los iconos monocromos. No se añaden sombras, brillos, degradados ni animaciones permanentes.

En **Configuración → Barra / Módulos**, selecciona Todos para los valores base o una salida concreta. Cada monitor hereda los valores base salvo sus ajustes explícitos; **Heredar todo** elimina esa personalización. Los monitores desconectados conservan sus preferencias.

Asigna los módulos a Inicio, Centro o Final; arrastra el tirador hasta un punto de inserción o usa las flechas. El reloj queda centrado si hay espacio; una barra demasiado corta permite desplazar el contenido sin superponer las zonas. **Quitar** y **Añadir** controlan qué módulos están presentes. Se puede dejar vacía y seguir abriendo los ajustes con el botón derecho. La opacidad se ajusta por módulo o de forma general. También puedes modificar la opacidad del fondo, el padding horizontal/vertical, el borde de 0–4 px y el radio de 0–8 px de los módulos. El grosor de la barra aumenta si hace falta para que el contenido no se corte.

Las funciones adicionales empiezan fuera de la barra; las funciones siguen disponibles por teclado y desde los menús. La bandeja se carga solo al añadir su módulo; sus iconos ocultos se configuran en Módulos. Los módulos que eliges permanecen en la barra: Presentación se puede activar desde su botón, y audio, multimedia o batería indican los datos ausentes sin inventarlos.

El catálogo reúne **48 módulos**. En **Módulos → En la barra** puedes quitar, mover entre zonas, reordenar y ajustar la opacidad de cada uno. **Añadir** permite buscar por nombre o función y filtrar por categoría; **Aspecto** contiene el estilo general y los iconos ocultos de la bandeja. Los mismos controles funcionan para cada monitor. Energía, modo nocturno, USB y ajustes del OSD se añaden desde ese catálogo; batería conserva su propio módulo.

| Categoría | Módulos disponibles |
| --- | --- |
| Paneles y barra | Aplicaciones, espacios de trabajo, reloj, calendario, Wi-Fi, Bluetooth, volumen, audio completo, micrófono, brillo, batería, notificaciones e historial, portapapeles e historial, multimedia, recursos, fondos, capturas y editor, centro de control, sesión, bandeja. |
| Configuración | App de configuración, temas y colores, perfiles/biblioteca/importación/exportación, atajos, ajustes de barra, gestión de módulos, reglas de notificaciones y preferencias del portapapeles. Abren la página correspondiente incluso si la ventana ya está abierta. |
| Controles rápidos | No molestar, presentación, pausa del portapapeles, silencio de salida y de micrófono. |
| Multimedia | Reproducir/pausar, pista anterior y siguiente. |
| Capturas directas | Región, ventana activa y escritorio completo. El módulo Capturas abre el temporizador y el editor. |
| Sesión | Bloqueo directo; suspender, cerrar sesión, reiniciar y apagar abren una confirmación. |

Cada entrada tiene fondo propio, icono, ayuda, opacidad y posición. Deshacer, rehacer y restablecer conservan su alcance exclusivo dentro de configuración.

![Añadir, quitar y reordenar módulos](docs/modules.png)

![Catálogo de funciones para la barra](docs/modules-catalog.png)

El indicador muestra inicialmente **solo el espacio actual**, dentro de un recuadro completo con fondo claro y texto oscuro: `[6]`. La rueda recorre todos los espacios disponibles del monitor, incluidos los que no se muestran. Cada barra sigue el activo de su propia pantalla; los espacios especiales no se mezclan con la lista normal. Si Hyprland no informa el activo, se muestra `—`.

En **Configuración → Barra → Espacios** puedes elegir Solo actual, Actual y puntos o Números compactos. Los dos últimos conservan hasta cinco celdas; en Actual y puntos solo el activo tiene número. Los puntos de agrupación permiten activar el espacio oculto más cercano. La lista contempla los espacios 1–N configurados y los existentes con otros números o nombres.

![Solo el espacio actual, resaltado con un recuadro completo](docs/workspaces-current.png)

El blur utiliza [BackgroundEffect de Quickshell](https://quickshell.org/docs/v0.3.1/types/Quickshell.Wayland/BackgroundEffect/). Necesita soporte del compositor y que el blur esté habilitado en él; la opacidad debe ser menor al 100% para verlo. La vista previa no reproduce el desenfoque del escritorio. No se modifica la configuración global de blur del compositor.

Las configuraciones anteriores se migran sin reescribir el archivo hasta que guardes cambios. Se conserva la posición, el orden de los módulos visibles, los atajos y los fondos personales. Se activan los iconos de aplicaciones; los nuevos atajos se añaden únicamente si no chocan con tus combinaciones guardadas.

## Dependencias en Arch / CachyOS

`doctor` comprueba qué herramientas están instaladas. Solo necesitas las correspondientes a los módulos que uses.

```sh
sudo pacman -S quickshell qt6-declarative qt6-svg python networkmanager bluez bluez-utils \
  wireplumber brightnessctl wl-clipboard cliphist grim slurp hyprlock hypridle \
  playerctl imagemagick pipewire-audio inter-font ttf-jetbrains-mono
```

Editores opcionales:

```sh
sudo pacman -S nm-connection-editor blueman pavucontrol
```

Para energía, almacenamiento USB y modo nocturno:

```sh
sudo pacman -S power-profiles-daemon udisks2 python-gobject hyprsunset
```

`python-gobject` proporciona GIO para D-Bus; es opcional para el resto del shell. La lista de periféricos USB se lee de sysfs. `doctor` comprueba las herramientas y el módulo Python, pero no confirma que los servicios estén activos. El modo nocturno gestiona una instancia propia de hyprsunset con configuración aislada; si ya tienes otra activa, muestra el conflicto y permite reintentar al cerrarla. Al salir de HyprLarp se detiene únicamente su filtro.

En **Configuración → General** puedes activar el OSD, cambiar posición/duración, probarlo y configurar el horario nocturno. El OSD automático se oculta durante Presentación; su prueba es explícita. Las unidades USB se consultan al abrir el panel o añadir el módulo y se actualizan con eventos. Expulsar pide confirmación y desmonta los volúmenes antes de apagar la unidad; si están ocupados, comunica el error sin forzar. Las unidades del sistema no ofrecen estas acciones.

NetworkManager, BlueZ y PipeWire deben estar funcionando en tu sesión. El frontend no intenta habilitar servicios del sistema ni instalar paquetes.

## Instalar para tu usuario

```sh
./bin/hyprlarp install --dry-run
./bin/hyprlarp install
```

Se copia el proyecto a `~/.local/share/hyprlarp`, se crea `~/.local/bin/hyprlarp` y una entrada **Configuración de HyprLarp** en el launcher. Respeta `XDG_DATA_HOME` y `XDG_CONFIG_HOME`. La instalación conserva los ajustes válidos existentes y crea respaldos de las copias y archivos que sustituye. No edita tu archivo principal de Hyprland ni activa el shell automáticamente.

Para iniciarlo con Hyprland, añade esto a `~/.config/hypr/hyprland.lua`:

```lua
local config = os.getenv("XDG_CONFIG_HOME") or (os.getenv("HOME") .. "/.config")
dofile(config .. "/hyprlarp/hyprlarp.lua")
```

El archivo incluye el arranque del shell, `hypridle` y los atajos generados. Si ya gestionas `hypridle`, integra el contenido de `~/.config/hyprlarp/hypridle.conf` en tu configuración en vez de iniciar dos instancias. El botón Suspender comprueba que la instancia de `hypridle` de HyprLarp esté activa.

El aspecto de ventanas del rice es opcional:

```lua
local data = os.getenv("XDG_DATA_HOME") or (os.getenv("HOME") .. "/.local/share")
dofile(data .. "/hyprlarp/config/hyprland-look.lua")
```

Este archivo aplica separación, bordes blancos de 1 px, esquinas rectas y desactiva las sombras del compositor. La app configura el shell; las ventanas del compositor se ajustan en ese archivo. El bloqueo recibe los colores del tema actual al abrirse, a partir de la plantilla `config/hyprlock.conf`.

## Atajos y comandos

| Atajo inicial | Acción |
| --- | --- |
| Super + Espacio | Aplicaciones |
| Super + A | Centro de control |
| Super + N | Notificaciones |
| Super + V | Portapapeles |
| Super + M | Multimedia |
| Super + C | Calendario |
| Super + W | Fondos |
| Super + Escape | Sesión |
| Super + Shift + S | Configuración |
| Super + Ctrl + W | Wi-Fi |
| Super + Ctrl + B | Bluetooth |
| Super + Ctrl + R | Monitor de recursos |
| Super + Ctrl + P | Batería |
| Super + Ctrl + E | Perfiles de energía |
| Super + Ctrl + L | Modo nocturno / descanso visual |
| Super + Ctrl + U | Dispositivos USB |
| Super + Ctrl + O | Configuración del OSD |
| Super + Ctrl + S | Menú de capturas |
| Super + Ctrl + A | Audio y micrófono |
| Super + Ctrl + D | Activar/desactivar Presentación |
| Super + L | Bloquear |
| Impr Pant / Shift + Impr Pant | Región / escritorio |
| Super + 1…9 / Super + 0 | Espacios 1…9 / espacio 10 |
| Escape | Cerrar el panel abierto |
| ↑ / ↓ / Enter | Seleccionar / abrir en el launcher |
| Volumen + / − / Silenciar | Audio del sistema |
| Silenciar micrófono | Micrófono del sistema |
| Brillo + / − | Brillo de pantalla |
| Reproducir / pausa, anterior, siguiente | Reproductor multimedia |

**Super** es la tecla Windows. Los atajos globales necesitan la inclusión de `hyprlarp.lua`; no se instalan con la vista previa. Puedes editar los de los paneles en **Configuración → Atajos** y aplicarlos con el botón de esa página. Un campo vacío desactiva ese atajo. El generador sustituye las asignaciones existentes de esas combinaciones para que no se ejecuten dos acciones a la vez, y respeta los atajos personalizados que usen Super + un número. La rueda ajusta volumen, micrófono o brillo en su módulo; el clic central silencia volumen o micrófono; el botón central sobre multimedia reproduce/pausa y el botón derecho sobre un módulo abre su gestión dentro de configuración.

```sh
hyprlarp settings
hyprlarp toggle wifi
hyprlarp toggle bluetooth
hyprlarp toggle audio
hyprlarp toggle presentation
hyprlarp toggle resources
hyprlarp toggle energy
hyprlarp toggle night-light
hyprlarp toggle usb
hyprlarp toggle osd
hyprlarp toggle wallpapers
hyprlarp close
hyprlarp screenshot-region
hyprlarp lock
```

Desde el checkout, sustituye `hyprlarp` por `./bin/hyprlarp`. Los comandos IPC se dirigen a la copia desde la que se ejecutan; usa el ejecutable instalado para controlar el shell instalado.

## Configuración y desarrollo

La barra usa eventos de Hyprland por monitor y audio nativo de PipeWire. Bluetooth se actualiza mediante BlueZ; los cambios de conexión de NetworkManager disparan una lectura, sin búsquedas Wi-Fi periódicas en segundo plano. CPU/RAM se muestrean solo mientras se necesitan; brillo se lee de sysfs cuando se muestra y al recibir eventos de backlight para el OSD; batería se lee cada 30 segundos en la barra o cada 2 segundos en su panel. Energía y USB se actualizan por eventos mientras sus módulos o paneles los necesitan. El horario nocturno comparte el reloj de minutos; el OSD solo mantiene un temporizador mientras está visible. Las tareas de lectura se agrupan para evitar colas de procesos. Los paneles se destruyen al cerrarse; las listas de aplicaciones reutilizan los elementos visibles y los iconos se cargan de forma asíncrona. No se reduce la calidad de renderizado del escritorio.

La metodología y los resultados de la medición están en [docs/performance.md](docs/performance.md). La lista para validar monitores, escalado, integraciones y suspensión está en [docs/validation.md](docs/validation.md). Para repetir una muestra aislada:

```sh
python3 tools/benchmark.py --seconds 12
python3 tools/benchmark.py --seconds 12 --panel resources
```

La configuración vive en `~/.config/hyprlarp/settings.json`. La app agrupa los cambios y los guarda mediante escritura atómica, con una escritura en curso como máximo. `config/modules.json` es el catálogo compartido por la validación y la interfaz; `config/defaults.json` contiene el esquema inicial; la validación, deshacer/rehacer y el protocolo JSON están en `backend/service.py`. Las paletas incluidas están en `config/palettes.json`; la personalizada, en `customPalette` dentro de tus ajustes. `HYPRLARP_STATE_DIR` permite usar un directorio aislado.

```text
HyprLarp.qml        Ventanas, IPC y composición del shell
core/              Estado, temas, puente, notificaciones y MPRIS
components/        Controles e iconos vectoriales propios
widgets/           Barra, fondo, panel flotante y configuración
panels/            Funciones del escritorio
backend/           Integraciones; biblioteca estándar y GIO opcional para energía/USB
config/            Valores iniciales y estilos del compositor/bloqueo
assets/            Fondos y marca originales en SVG
tools/             Instalación y comprobación de la interfaz
tests/             Pruebas de persistencia, parsers y límites de las acciones
```

```sh
make check
# Solo backend, sin Quickshell:
python3 -m unittest discover -s tests -v
```

La comprobación completa abre los 18 paneles, las siete páginas de configuración, las cuatro posiciones de barra, valores a cero, barras cortas, los seis temas incluidos y el personalizado con el renderizador offscreen de Qt y ajustes temporales. Comprueba la navegación de los 48 módulos, las páginas de configuración y las confirmaciones de sesión; los modos visuales Mínimo y Sutil; el selector RGB, las anotaciones, los flujos de audio y la recuperación tras terminar el backend de prueba; añadir, quitar y reordenar módulos, incluyendo una barra vacía; también deshacer/rehacer cambios pendientes y guardados, revertir un reset, agrupar sliders, conservar la paleta y aplicar colores claros personalizados. Comprueba el OSD de prueba, su caducidad y desactivación, y el historial de sus preferencias y del modo nocturno. Las pruebas de lógica cubren errores de escritura, validación de colores, límite del historial, espacios por monitor, planificación del muestreo, telemetría de batería, horarios nocturnos, perfiles compatibles y operaciones USB con servicios simulados; las del modelo de espacios usan Node si está disponible, solo para desarrollo. Los archivos Lua se verifican con `Hyprland --verify-config` cuando está instalado. El renderizado está comprobado con Quickshell 0.3.2 y la configuración con Hyprland 0.57; los cambios físicos de monitor, las conexiones, el bloqueo/PAM, la suspensión, el OSD nativo, energía, USB, el filtro nocturno y las acciones de sesión deben verificarse en una sesión real. La vista previa no valida esos servicios.

El código usa indentación de **2 espacios** en QML, Python, JavaScript, JSON, Lua y configuración. `.editorconfig` y `.qmlformat.ini` conservan esta convención. Las reglas visuales están en [docs/design.md](docs/design.md).

El bloqueo utiliza la autenticación de `hyprlock`; HyprLarp no recibe ni almacena contraseñas de sesión. La suspensión usa la [integración de `hypridle`](https://wiki.hypr.land/hypr-ecosystem/user/hypridle/) con `inhibit_sleep = 3` para esperar el bloqueo antes de dormir. El shell no incluye grabación de pantalla, greeter ni plugins de Noctalia.

## Referencias

- [Quickshell: tipos y servicios](https://quickshell.org/docs/v0.3.1/)
- [Notificaciones de Quickshell](https://quickshell.org/docs/v0.2.1/types/Quickshell.Services.Notifications/NotificationServer/)
- [MPRIS de Quickshell](https://quickshell.org/docs/v0.2.1/types/Quickshell.Services.Mpris/MprisPlayer/)
- [Noctalia, referencia de organización](https://noctalia.dev/shell)
- [Hyprland: configuración Lua](https://wiki.hypr.land/configuring/core/)

Código, iconos y fondos incluidos bajo [MIT](LICENSE).
