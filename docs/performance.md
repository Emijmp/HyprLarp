# Consumo y verificación

Medición local de la revisión 0.3 del 1 de noviembre de 2026, con Quickshell 0.3.2, Qt 6.12, Linux y el tema AMOLED. La muestra inicial corresponde a la barra anterior, con consultas al sistema cada 2 segundos. La muestra final incluye los fondos individuales de módulos y las integraciones por eventos.

| Muestra | CPU de un núcleo | RSS al final | Pico RSS muestreado | Comandos externos en 12 s |
| --- | ---: | ---: | ---: | ---: |
| Antes, paneles cerrados | 2.40% | 110.28 MiB | 117.60 MiB | 30 |
| Después, paneles cerrados | 0.00%* | 116.96 MiB | 116.96 MiB | 0 |
| Después, Recursos abierto | 0.17% | 113.28 MiB | 113.28 MiB | 0 |

\* El contador de CPU no avanzó durante esa muestra; significa consumo por debajo de la resolución de la medición, no una garantía de CPU cero. Las consultas iniciales eran 18 ejecuciones de `hyprctl`, 6 de `wpctl` y 6 de `brightnessctl`. Las lecturas periódicas desaparecieron del intervalo medido. No se demuestra una reducción de memoria: el RSS final de la muestra en reposo es mayor, con un pico similar al anterior.

`tools/benchmark.py` abre una vista previa aislada de 1440 × 900 con el renderizador **offscreen/software**, espera 3 segundos y mide durante unos 12 segundos. Suma los ticks de CPU y el RSS del árbol de procesos de Quickshell y su backend desde `/proc`, incluidos los hijos ya recolectados; toma muestras de RSS cada 200 ms. El RSS suma páginas compartidas entre procesos, por lo que no equivale a memoria exclusiva. La instrumentación de comandos solo registra nombre del programa y momento de ejecución cuando `HYPRLARP_COMMAND_PROFILE` está activado; no registra argumentos ni contraseñas.

```sh
python3 tools/benchmark.py --seconds 12 --output .preview/performance-after.json
python3 tools/benchmark.py --seconds 12 --panel resources --output .preview/performance-resources.json
```

Son muestras cortas del comportamiento de la interfaz y del backend, sin D-Bus ni sockets del compositor disponibles en este entorno. No representan el consumo de GPU ni el coste total en una sesión Wayland real. En el escritorio, el consumo depende de los monitores, la escala, el fondo, el blur, los módulos seleccionados y los eventos de los servicios.

## Trabajo que se evita

- Espacios de trabajo: estado nativo de Hyprland, con el espacio activo de cada monitor y sin ejecutar `hyprctl` a intervalos.
- Audio: estado y controles nativos de PipeWire; no se consulta `wpctl` periódicamente.
- Red: lectura tras cambios de NetworkManager o al abrir Wi-Fi; buscar redes es una acción explícita. La vista previa usa una lectura de respaldo cada 60 segundos si hace falta mostrar la red.
- Bluetooth: actualizaciones de BlueZ en el escritorio; sin consultas periódicas mediante bluetoothctl. El agente de PIN/confirmación vive solo durante la vinculación y la búsqueda dura como máximo 12 segundos o hasta cerrar el panel.
- CPU/RAM/red/disco: lecturas de `/proc` y del sistema de archivos cada 2 segundos, únicamente con el módulo de recursos o un panel que las muestre.
- Brillo: sysfs cada 2 segundos con el centro de control abierto. Batería: 30 segundos para la barra y 2 segundos con su panel abierto.
- Tareas de lectura: una ejecución por fuente y, para eventos acumulados, una actualización pendiente. Las peticiones manuales repetidas también se agrupan.
- Paneles: los `Loader` destruyen su contenido al cerrarse. El índice de aplicaciones se ordena al cambiar las entradas de escritorio; escribir una búsqueda solo filtra ese índice.
- Iconos: listas virtualizadas con reutilización de delegados, imágenes asíncronas a 24 px y resolución local en caché como respaldo. Las rutas inexistentes usan un icono genérico sin reintentos de carga continuos.
- Reloj: una fuente compartida con precisión de minutos. El temporizador de posición multimedia funciona solo con reproducción activa y el panel de media abierto. Los avisos solo usan un temporizador mientras hay notificaciones pendientes de expirar.
- Configuración: escrituras agrupadas, sin reescribir ajustes idénticos.

No se fuerza software rendering, baja resolución, reducción de calidad ni un límite artificial de FPS en la sesión real. El renderizador software se utiliza únicamente para esta comprobación aislada.

## Comprobaciones

`python3 tools/check.py` pasa las pruebas de lógica, verifica la sintaxis Lua con Hyprland instalado y abre los 18 paneles, las 7 páginas de configuración, las 4 posiciones de barra, los 6 temas incluidos y el personalizado, casos de geometría y una barra vacía. Comprueba añadir, quitar y reordenar módulos; también deshacer/rehacer cambios pendientes y guardados, agrupar sliders, revertir un reset y editar paletas. Verifica que esas acciones se deshabilitan al enfocar otra ventana u ocultar configuración y que conservan los cambios hechos desde otros paneles. El historial está limitado a 50 cambios en memoria, guarda únicamente las claves modificadas y trabaja cuando se guardan ajustes. Las pruebas del modelo de espacios cubren varios monitores, espacios con nombre, números fuera del rango configurado y comandos de activación.

La validación con cambios de monitor y servicios físicos debe hacerse en una sesión real de Hyprland; la comprobación offscreen no ejecuta esas acciones.

## Revisión 0.5 y sesión real

La biblioteca, la búsqueda difusa, las reglas por aplicación y los fijados no añaden temporizadores permanentes. Los flujos de audio completos se siguen solo mientras Audio está abierto; la bandeja solo se crea al seleccionar su módulo. La caducidad del portapapeles añade una tarea cada 60 segundos únicamente cuando se configura un plazo mayor que cero. Se tienen en cuenta los módulos de los monitores conectados; los ajustes de un monitor ausente no activan muestreos.

El benchmark admite `--pid PID --seconds 300` para leer una instancia nativa ya abierta, incluye PSS cuando está disponible y contadores GPU DRM por motor cuando el controlador los expone. No termina ni modifica la instancia a la que se conecta. Los resultados de la revisión 0.3 de arriba son históricos; no deben presentarse como una medición de la versión ampliada. Sigue [validation.md](validation.md) para completar una medición sostenida y las pruebas de hardware.

Muestra local de 0.5, misma plataforma offscreen/software, paneles cerrados y 12.00 s tras el calentamiento: **0 ticks de CPU contabilizados**, RSS final/pico muestreado **120.78 MiB**, PSS final **84.74 MiB**, **0 comandos externos**. Los contadores GPU no estuvieron disponibles. Es una muestra corta; no acredita el consumo de una sesión Wayland ni una reducción de RAM frente a las versiones anteriores.

## Decoración sutil y catálogo de módulos

Los remates son rectángulos de uno o dos píxeles e iconos vectoriales; no tienen temporizadores ni animaciones propias. El catálogo se envía una vez al iniciar el backend y sirve también para validar los módulos; añadir accesos a páginas o acciones no crea procesos residentes. La lista de elementos disponibles solo crea sus filas mientras se ve Añadir. El módulo de brillo añade lecturas de sysfs cada dos segundos únicamente mientras esté en una barra de un monitor conectado o su panel esté abierto. Los cambios con la rueda se agrupan durante 100 ms.

Muestra local tras el catálogo y los detalles sutiles, con la selección inicial de ocho módulos y paneles cerrados: 12.00 s, **0 ticks de CPU contabilizados**, **0 comandos externos**, RSS final/pico **127.24 MiB** y PSS final **104.42 MiB**. Los contadores GPU no están disponibles. La decoración no requiere muestreo continuo; esta muestra corta offscreen/software no acredita CPU absoluta cero ni el consumo de una sesión Wayland real.

El indicador de espacios compacto se deriva de los mismos eventos de Hyprland: no añade consultas ni temporizadores. Conserva todos los destinos en los grupos ocultos y limita a cinco las celdas dibujadas cuando hay muchos espacios. Los radios y el resaltado se dibujan con rectángulos nativos, sin máscaras ni efectos animados.


## Energía, OSD, descanso visual y USB

El indicador inicial dibuja solo el espacio actual; usa los mismos eventos y conserva la rueda para navegar. El modo nocturno no añade un reloj: reutiliza el minuto compartido y envía cambios únicamente al cambiar el estado solicitado. Hyprsunset solo se ejecuta si se activa el filtro, con salida al cerrar el shell o su backend.

Energía y almacenamiento USB comparten una conexión GIO de D-Bus con suscripciones limitadas a esos servicios. Se inicia al necesitar esos módulos o paneles y se retira al cerrar el último consumidor. Los periféricos se leen de sysfs y se actualizan con eventos USB de libudev; no se ejecuta lsusb/lsblk periódicamente. Los errores de conexión no provocan un bucle de reintentos; Actualizar permite reintentar.

El OSD sigue los cambios nativos de PipeWire y backlight. Su escucha de brillo es pasiva mediante libudev, sin un proceso auxiliar ni sondeo. La ventana se carga únicamente mientras el indicador es visible y se descarga al vencer su único temporizador. Desactivar el OSD retira también esa escucha de brillo. Las acciones de montaje, expulsión y cambio de perfil solo se realizan tras una acción del usuario.

Las pruebas automáticas cubren la caducidad y desactivación del OSD, horarios a ambos lados de medianoche, valores de batería ausentes, unidades/ciclos, perfiles no compatibles, protección de unidades del sistema y expulsión sin forzar un desmontaje ocupado. Todas las operaciones de dispositivos de las pruebas usan servicios simulados; no montan ni expulsan unidades físicas.

Muestra del 2 de noviembre de 2026, con la selección inicial de ocho módulos, paneles cerrados y Qt offscreen/software: **12.00 s**, **0 ticks de CPU contabilizados**, **0 comandos externos**, RSS final/pico **128.94 MiB**, PSS final **103.08 MiB**. Los contadores GPU no estuvieron disponibles. El informe se genera con `python3 tools/benchmark.py --seconds 12 --output .preview/performance-system-idle.json`. No incluye los servicios nativos de Wayland/D-Bus ni el filtro activado y no demuestra una reducción de memoria respecto de revisiones anteriores.


El selector de fondos usa GridView con reutilización de las miniaturas visibles y una zona de caché de 136 px; no crea 200 imágenes a la vez. La carpeta se lee al abrir el selector, cambiar su ruta o pulsar Actualizar. Los nombres de archivo se convierten a URL local con los caracteres especiales escapados. Wi-Fi conserva el adaptador elegido y solo fuerza una búsqueda al pulsar Buscar. Las respuestas del agente Bluetooth se atienden fuera de la cola de operaciones lentas para no bloquear la confirmación de un PIN.

## Revisión de recursos y seguridad · 2 de noviembre de 2026

Comparación de esta revisión con el código inmediatamente anterior. Cada muestra usa los ocho módulos iniciales, tres segundos de calentamiento y doce segundos de medida con Qt offscreen/software. No se ejecutaron pruebas ni otras vistas previas en paralelo con las mediciones.

| Muestra | CPU de un núcleo | RSS final/pico muestreado | PSS final | Comandos externos |
| --- | ---: | ---: | ---: | ---: |
| Antes, paneles cerrados | 0.00%* | 128.25 MiB | 93.32 MiB | 0 |
| Después, paneles cerrados | 0.00%* | 129.23 MiB | 106.42 MiB | 0 |
| Antes, Recursos abierto | 0.25% | 130.25 MiB | 94.97 MiB | 0 |
| Después, Recursos abierto | 0.25% | 128.78 MiB | 104.53 MiB | 0 |

\* No avanzaron los ticks contabilizados. No se demuestra una reducción global de RAM o CPU: el reposo ya estaba por debajo de la resolución de esta muestra y la memoria varía entre ejecuciones. PSS depende además del reparto de páginas compartidas. Los contadores GPU no estuvieron disponibles. Los resultados originales están en `.preview/review-before-idle.json`, `.preview/review-after-idle.json`, `.preview/review-before-resources.json` y `.preview/review-after-resources.json`.

Las mejoras verificadas son límites de crecimiento y menos trabajo por evento: tres workers y doce tareas pendientes como máximo; lecturas y salidas de procesos acotadas; captura del portapapeles limitada antes de guardarla; hasta 64 avisos activos sin acumular callbacks al sustituirlos; escrituras agrupadas y un único vencimiento de avisos programado. La lectura ligera de la barra omite disco, red y sensores; el panel completo reutiliza los datos de disco durante diez segundos y el descubrimiento térmico durante sesenta. Las cachés de iconos tienen límite y se retiran las referencias a aplicaciones eliminadas.

Los seis interruptores de decoración controlan dibujos nativos sin temporizadores propios. Los helpers gestionados terminan con el backend, incluidos los capturadores del portapapeles, evitando procesos residuales. El alcance y las comprobaciones de estas correcciones se detallan en [review.md](review.md).

## Binds conservados

El gestor registra los handlers nativos durante la carga de la configuración y conserva los callbacks originales. La transferencia de comandos de Noctalia usa dispatchers nativos y las herramientas de audio/brillo existentes; no añade un cliente Noctalia por pulsación. Las funciones de repetición del usuario conservan su frecuencia. No hay sondeos ni procesos residentes nuevos. La consulta de binds es explícita y las listas del editor crean solo los delegados visibles. Véase [binds.md](binds.md).

## Fondos externos

Al seleccionar Externo, el `LazyLoader` destruye la superficie nativa de fondo y el modelo de miniaturas queda vacío. No hay consultas periódicas de Waypaper ni un reproductor adicional dentro del shell. La restauración automática es opcional y se programa una vez al iniciar el backend del shell. El reproductor externo conserva su propio ciclo de vida y consumo; no se incluye una medición nueva de vídeo/GPU en el entorno offscreen.

## Separación de ventanas

Los controles de separación no añaden sondeos ni procesos residentes. Las actualizaciones se agrupan en la cola existente del backend y solo se aplican si cambian los valores efectivos. Se escribe el archivo privado únicamente cuando difiere; la interacción usa una llamada acotada a `hyprctl eval`. Solo desactivar una personalización activa requiere recargar Hyprland. El archivo de datos se lee al cargar la configuración, sin añadirlo al observador de archivos Lua del compositor.
