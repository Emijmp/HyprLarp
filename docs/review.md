# Revisión de HyprLarp · 2 de noviembre de 2026

La revisión abarca el shell QML, los servicios Python, el protocolo entre ambos, el procesamiento del portapapeles, los procesos hijos, la configuración y el ciclo de instalación. Se conservaron los cambios de Wi-Fi, Bluetooth y fondos de la revisión anterior. No se instaló ni desinstaló nada en el escritorio del usuario: las pruebas de despliegue usan prefijos temporales.

La corrección posterior de reserva de espacio de la barra sí se aplicó a los dos archivos afectados de la instalación existente, con respaldo y actualización de sus hashes en el manifiesto. No se reescribieron sus ajustes ni la configuración principal de Hyprland.

## Correcciones y comprobaciones

La prioridad de esta tabla expresa el impacto dentro de HyprLarp. No asigna CVE ni representa una certificación de las dependencias.

| Área | Hallazgo | Resultado |
| --- | --- | --- |
| Privacidad · alta | La contraseña Wi-Fi se pasaba en los argumentos de `nmcli`. | Se prepara el perfil mediante GIO/libnm y se envía el secreto directamente a NetworkManager. La activación usa un UUID sin contraseña en argv. Se conservan los perfiles existentes y sus ajustes. Se valida el tipo de adaptador y se consultan solo sus perfiles disponibles. |
| Bluetooth · media | El agente confiaba en el nombre del método y dispositivo, sin comprobar al remitente. | Se verifica el nombre único del propietario de `org.bluez` antes de responder a cualquier método, incluidos Cancel y Release. Se rechazan remitentes ajenos. Es una defensa adicional a las políticas del bus. |
| Disponibilidad · alta | Había lecturas completas de datos antes de comprobar su tamaño, archivos FIFO que podían bloquear y una cola de trabajo ilimitada. | Archivos regulares y lecturas con límite; peticiones ordinarias de hasta 2 MiB, profundidad máxima 64 y Unicode válido; tres workers con hasta doce trabajos pendientes. El historial admite hasta 16 MiB para conservar 500 avisos con Unicode y escapes: se valida y guarda en serie, sin entrar en esa cola. Las entradas rechazadas no dejan botones ocupados. |
| Protocolos · media | Tipos de acción incorrectos, enteros enormes, números no finitos y datos anidados podían provocar excepciones fuera de la validación. | Se rechazan de forma controlada; el backend sigue procesando peticiones posteriores. La configuración inválida no se guarda. |
| Portapapeles · alta | El almacenamiento y los decodificadores podían recibir entradas excesivas o formatos interpretados automáticamente. | Se limita la captura a 16 MiB antes de cliphist. El intermediario usa un descriptor de memoria anónima y se reemplaza con cliphist; no queda un servicio adicional ni un archivo temporal con el contenido. La decodificación y las salidas también tienen límite. |
| Miniaturas · media | ImageMagick infería cualquier formato de stdin. | Se comprueban cabeceras PNG/JPEG/GIF/WEBP/BMP, se fuerza ese decodificador y el primer fotograma. Se limitan caché de memoria/mapa, dimensiones, tiempo, hilos y salida; se prohíbe caché de píxeles en disco. El original del portapapeles no se modifica. |
| Notificaciones · alta | Las notificaciones permanentes y sus sustituciones podían retener objetos y callbacks indefinidamente; nombres como `__proto__` rompían la agrupación. | Hasta 64 notificaciones activas; desconexión del callback anterior al sustituir; agrupaciones sin prototipo. El historial conserva como máximo 500 entradas según configuración, cuerpo de 2048 caracteres y resumen de 256. Se muestran hasta ocho acciones. Objetos con textos o listas de acciones excesivos no se retienen. El recorte conserva pares Unicode. |
| Escrituras y temporizadores · media | Cada aviso enviaba el historial completo y un temporizador buscaba vencimientos cada 500 ms. | Las escrituras se agrupan durante 200 ms y se usa un temporizador de una sola ejecución para el siguiente vencimiento. Sin avisos temporales no hay temporizador de expiración activo. |
| Historial · media | El límite genérico de 2 MiB rechazaba historiales válidos de 500 avisos con texto Unicode. | Se da al historial un presupuesto de 16 MiB en el protocolo y al recargar el archivo, manteniendo sus límites de entradas y campos. Se prueba el guardado y la recarga completos. |
| Procesos · alta | Los helpers y capturadores de portapapeles podían sobrevivir a la muerte del backend. | Los hijos gestionados vinculan su vida al hilo padre mediante Linux PDEATHSIG antes de exec. El cierre termina los grupos de helpers activos y cancela la vinculación/búsqueda Bluetooth. Los editores externos y hyprlock permanecen independientes por su función. |
| Archivos privados · media | Directorios existentes podían conservar permisos amplios; las capturas finales dependían del umask. | Directorios internos de modo 700 y estado de modo 600, escrituras atómicas, capturas creadas de modo exclusivo y privado. La limpieza de borradores reconoce sus nombres propios y evita directorios simbólicos. |
| Recursos · media | El pequeño módulo de CPU/RAM leía también disco, red y sensores; se redescubrían sensores continuamente y las cachés podían crecer. | Lectura ligera para la barra; disco cada diez segundos y descubrimiento térmico cada sesenta cuando el panel completo los necesita. Caché de iconos limitada a 4096; se eliminan referencias a iconos de aplicaciones retiradas y se usa un Set para favoritos. Vista previa de cliphist acotada a 256 caracteres. |
| Instalación · alta | No existía desinstalación con propiedad de archivos, rollback ni protección ante instalaciones simultáneas. | Copia preparada en staging, respaldos, restauración ante fallo de escritura, bloqueo exclusivo y manifiesto de hashes. Se rechazan destinos superpuestos y enlaces simbólicos. Solo se empaquetan las rutas previstas, incluido el lanzador sin extensión. |
| Desinstalación · alta | Faltaba distinguir archivos propios de modificaciones locales y datos al retirar el shell. | Solo se quitan archivos de programa que coinciden con el manifiesto, además de sus cachés Python conocidas. Los cambios locales, archivos ajenos y respaldos externos a configuración se conservan. Toda la carpeta de ajustes se conserva salvo `--purge`, que la elimina con sus historiales y respaldos internos. El manifiesto no puede dirigir borrados fuera de los destinos calculados. |
| Lanzadores y sesión · media | Las rutas reservadas requerían escape de Desktop Entry y la detección de hypridle perdía los límites de sus argumentos. | Se prueba el lanzamiento real con GLib usando espacios, comillas, dólar, backtick y porcentaje. La detección de hypridle usa argv de `/proc` y su `-c` exacto; el desinstalador usa pidfd para señalar únicamente ese proceso. |

Las restricciones de formatos y recursos siguen el enfoque de la [política de seguridad de ImageMagick](https://imagemagick.org/security-policy/). El escape del lanzador se contrasta con la [especificación de Desktop Entry](https://specifications.freedesktop.org/desktop-entry/latest/exec-variables.html).

## Decoración

En Apariencia se conservan Mínimo y Sutil y se añaden seis opciones independientes: remates en paneles, marcas de sección, indicadores de módulos, divisores, iconos de cabecera y marcas de avisos. Mínimo desactiva esos detalles sin perder las preferencias. Los controles funcionales de selección, el workspace activo y los niveles permanecen visibles. Los ajustes admiten deshacer, rehacer y reset de Apariencia exclusivamente desde configuración.

Los cambios conservan AMOLED, bordes sólidos, radios pequeños e iconos monocromos. No incorporan efectos de iluminación ni animaciones permanentes.

## Consumo

Las muestras usan Quickshell 0.3.2, Qt 6.12, renderizado offscreen/software, ocho módulos iniciales, tres segundos de calentamiento y doce segundos de medida. Se mide el árbol de procesos del shell. Los resultados finales se recogen en `docs/performance.md` y en `.preview/review-*.json`.

| Estado | Antes: CPU / RSS | Después: CPU / RSS |
| --- | ---: | ---: |
| Paneles cerrados | 0 ticks / 128.25 MiB | 0 ticks / 129.23 MiB |
| Recursos abierto | 0.25% / 130.25 MiB | 0.25% / 128.78 MiB |

En las cuatro muestras hubo cero comandos externos durante el intervalo medido. No se acredita una reducción global de RAM o CPU; el consumo medido permanece parecido. [performance.md](performance.md) incluye PSS y las limitaciones de comparación.

El objetivo verificable de las optimizaciones es limitar el crecimiento con avisos y portapapeles, evitar procesos que queden vivos, reducir lecturas que no se muestran y conservar el reposo sin procesos periódicos adicionales. Una muestra con cero ticks no demuestra consumo absoluto cero; las muestras cortas no representan Wayland, blur, GPU ni dispositivos reales.

## Validación

Resultado final: **186 pruebas de backend correctas**, recorrido de interfaz completo (`SMOKE COMPLETE`) y vista previa ordinaria que permanece abierta. El registro de la ejecución final está en `.runtime/check-current.log`. El recorrido ampliado dispone de 90 segundos; el límite anterior de 60 segundos podía interrumpir los últimos pasos de configuración sin que hubiera un error QML.

`python3 tools/check.py` ejecuta las pruebas de backend y la escena completa. Incluye:

- Persistencia, configuración inválida, deshacer/rehacer, reset, perfiles y paletas.
- Los 18 paneles, las siete páginas de configuración, las cuatro posiciones de barra y el catálogo de 48 módulos.
- Inundación y sustitución de avisos, nombres especiales de aplicaciones, expiración, límites de Unicode y persistencia/recarga de 500 avisos con texto multibyte.
- Rechazo de FIFO, salidas grandes, exceso de trabajos, peticiones demasiado largas, estructuras profundas e importaciones inválidas.
- Miniatura real de una imagen 4K, captura privada, limpieza de borradores y protección de rutas simbólicas.
- Contraseñas Wi-Fi fuera de argv y serialización local de perfiles libnm; autenticación del remitente y confirmaciones del agente Bluetooth.
- Salida efectiva de un hijo gestionado al matar su padre.
- Instalación, reinstalación, rollback inyectando un fallo, desinstalación, purga y conservación de archivos modificados con prefijos temporales.
- Lanzamiento del envoltorio instalado, validación Desktop Entry y apertura real mediante GLib de un ejecutable de prueba con ruta reservada, sin abrir una ventana.

También se comprueban sintaxis Python, sintaxis de los scripts shell, espacios finales y patrones AST directos como shell=True, eval, exec y os.system. Esa inspección estática complementa las pruebas; no sustituye el análisis de las rutas de datos.

## Instalación y retirada

Desde el repositorio, usa `./install.sh --dry-run` para revisar los destinos y `./install.sh` para instalar. `./uninstall.sh` conserva los datos; `./uninstall.sh --purge` elimina toda la carpeta de ajustes, incluidos historiales y respaldos internos. Ambos aceptan `--prefix` para un destino aislado y `--dry-run` sin escrituras. También se exponen mediante `hyprlarp install` y `hyprlarp uninstall`.

El programa y su desinstalador no editan el archivo principal de Hyprland. Los bloques de integración del README verifican que el archivo exista antes de cargarlo; si se añadió un dofile incondicional anteriormente, se debe retirar al desinstalar. Los respaldos externos a la carpeta de ajustes quedan disponibles y el bloqueo de despliegue ocupa un archivo vacío en el directorio de datos.

## Alcance pendiente

Este entorno bloquea sockets de Wayland y D-Bus. Las pruebas de dispositivos usan servicios simulados y validación de variantes; no cambian redes, montan discos, activan filtros, bloquean la sesión ni suspenden el equipo. La conexión física, PIN con hardware, UDisks/Polkit, PAM, suspensión, múltiples monitores, escalado y GPU requieren la lista de `docs/validation.md` en una sesión real.

Los límites aplicados por el shell actúan después de la recepción de eventos nativos. No se ha realizado fuzzing ni auditoría del código C/C++ de Qt, ImageMagick, BlueZ, NetworkManager o D-Bus, ni se ha modificado su política de sistema. La verificación de dependencias no equivale a ausencia de vulnerabilidades en esos componentes.

Versiones locales registradas: Python 3.14.8, Quickshell 0.3.2, Qt Declarative 6.12.0, ImageMagick 7.1.2.34, BlueZ 5.87, NetworkManager y libnm 1.58.1. Se consultaron las páginas oficiales de [ImageMagick en Arch Security](https://security.archlinux.org/package/imagemagick), [BlueZ en Arch Security](https://security.archlinux.org/package/bluez) y los [avisos del espejo de Quickshell](https://github.com/quickshell-mirror/quickshell/security/advisories). No se actualizaron paquetes del sistema.


## Binds actuales y editor

La revisión posterior sustituye el generador que hacía `hl.unbind` y añadía espacios/multimedia por un adaptador que conserva los handles nativos. El preludio se carga antes de las declaraciones del usuario y la integración se aplica al final. Los conflictos conservan el original salvo reemplazo explícito. La página Atajos permite añadir, editar, eliminar, activar/desactivar y personalizar acciones Lua sin reescribir el archivo principal.

Se verificaron callbacks de pulsar/soltar, funciones Lua, bucles de espacios, submaps, aliases, herencia, restauración al eliminar una personalización, transferencia de Noctalia y escapado de comandos. La retirada del adaptador restaura los handlers y las funciones nativas; el desinstalador comprueba que la ruta corresponda a su instalación antes de retirarlo. Un fallo de recarga restaura el archivo generado anterior.

El editor QML pasa altas, cambios de comando/combinación, bajas, captura, apertura del selector, deshacer/rehacer y adopción de combinaciones de Noctalia. La revisión detectó y corrigió una restricción de variables de bucle constantes de la versión local de Lua y una advertencia de altura al destruir separadores en delegados. El pase final tiene 165 pruebas de backend correctas, `SMOKE COMPLETE` y vista previa estable.

También se cargó el `hyprland.lua` real del usuario entre el preludio y la integración en `Hyprland --verify-config`: 57 declaraciones registradas y cinco binds representativos comprobados (terminal, cierre, explorador y las dos acciones del scratchpad). La verificación terminó con `config ok` y se comprobó por hash que el archivo original no cambió. No se ejecutaron sus procesos de arranque ni acciones de teclado. La prueba de pulsación y recarga con IPC sigue requiriendo la sesión real, como se detalla en [binds.md](binds.md).

## Reserva de espacio de la barra

La barra estaba anclada a dos bordes perpendiculares. Esa combinación hace que se ignore una zona exclusiva positiva aunque Reservar espacio para ventanas esté activado. Se usan ahora tres anclajes y márgenes complementarios en el eje largo, conservando longitud, alineación y márgenes. La reserva se retira al desactivar la opción o esconder la barra. La condición se contrasta con la [documentación de PanelWindow](https://quickshell.org/docs/v0.3.2/types/Quickshell/PanelWindow/).

La prueba QML recorre 108 combinaciones de posición, longitud, alineación y dimensiones lógicas, además de la liberación de espacio. El pase completo conserva 165 pruebas de backend correctas y `SMOKE COMPLETE`. Los sockets de Hyprland no están disponibles en el entorno de comprobación; la colocación real de ventanas queda cubierta por los pasos de [validation.md](validation.md).


## Fondos externos opcionales

Se añade un proveedor externo para Waypaper u otro gestor, sin activarlo inicialmente. La superficie interna se descarga, las miniaturas se liberan y se conservan la imagen y la carpeta anteriores. Se incluyen apertura de Waypaper, restauración manual y restauración al iniciar de elección explícita. No se modifica la configuración de Waypaper ni se detienen sus reproductores al volver al fondo interno.

La validación final pasa 174 pruebas de backend y el recorrido completo de interfaz, incluido `SMOKE Waypaper COMPLETE`. Cubre persistencia, deshacer/reset, liberación de imágenes, omisión del catálogo en modo externo, argumentos fijos y restauración opcional sin efectos en la vista previa. Los archivos de ejecución se actualizaron también en la copia instalada, verificando el manifiesto y guardando un respaldo. No se activó el proveedor ni se lanzó un reproductor en la sesión del usuario.

Waypaper y mpvpaper están instalados. Falta socat para el control de vídeos desde Waypaper; la app lo muestra y la [guía](waypaper.md) incluye su instalación. La compilación de tipos de escritorio sin Wayland devuelve `No PanelWindow backend loaded`; las capas nativas y la reproducción requieren la sesión real y no se presentan como comprobadas aquí.

## Separación de ventanas

Apariencia permite ajustar la separación exterior común o por cada borde y la separación interior. La personalización está desactivada inicialmente y mover un control la activa. Los cambios se guardan, admiten deshacer/rehacer/reset desde configuración y se aplican mediante la cola existente, sin sondeo. Al desactivar la personalización se recarga la configuración original del compositor.

El archivo generado contiene únicamente seis campos numéricos validados; el lector Lua no ejecuta sus datos y limita la lectura a 1 KiB. Los comandos reciben argumentos separados y los valores pasan por la validación de preferencias. El cargador persiste los ajustes y el aspecto base del rice vuelve a aplicarlos al final para no sobrescribirlos con su separación inicial.

El pase final incluye 186 pruebas de backend y `SMOKE window gaps COMPLETE` dentro del recorrido completo de interfaz. Se comprueban cuatro bordes, separación interior, validación, permisos, persistencia, restauración y recuperación tras error. El verificador nativo de Hyprland confirma los valores efectivos, incluidos los de una instalación temporal que carga el aspecto base después de la integración. La colocación real de ventanas mediante el socket del compositor requiere la sesión Wayland; los pasos están en [validation.md](validation.md).

La copia instalada recibió los doce archivos de ejecución afectados, el archivo de datos y la integración de sesión, con respaldo y hashes actualizados. Se verificó que no cambiaron las preferencias, los binds ni la configuración principal del usuario. Esa configuración completa también pasa `Hyprland --verify-config` después de la actualización. La captura de [los nuevos controles](window-gaps-settings.png) utiliza preferencias aisladas y renderizado offscreen.
