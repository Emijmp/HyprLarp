# Consumo y verificación

El [panel de rendimiento](performance-panel.md) permite consultar el consumo actual de HyprLarp y guardar comparaciones desde la interfaz. Las mediciones históricas y el benchmark CLI de este documento conservan su alcance original.

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

`python3 tools/check.py` pasa las pruebas de lógica, verifica la sintaxis Lua con Hyprland instalado y abre los 19 paneles, las 8 páginas de configuración, las 4 posiciones de barra, los 6 temas incluidos y el personalizado, casos de geometría y una barra vacía. Comprueba añadir, quitar y reordenar módulos; también deshacer/rehacer cambios pendientes y guardados, agrupar sliders, revertir un reset y editar paletas. Verifica que esas acciones se deshabilitan al enfocar otra ventana u ocultar configuración y que conservan los cambios hechos desde otros paneles. El historial conserva hasta 50 cambios de claves, con persistencia después de cada edición. Las 30 versiones completas comparten un archivo privado limitado a 6 MiB; no hay sondeos ni procesos adicionales para mantenerlo. Las pruebas del modelo de espacios cubren varios monitores, espacios con nombre, números fuera del rango configurado y comandos de activación.

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

## Pantallas y proyección

Las pantallas se consultan al abrir el editor, al iniciar y tras eventos de conexión o recarga. Los eventos próximos se agrupan durante 350 ms. El editor mantiene un borrador y el esquema solo dibuja las salidas conectadas. El temporizador independiente existe durante una prueba de imagen; se retira al confirmar, cancelar o vencer los 20 segundos. No hay consultas periódicas de monitores en reposo.

## Herramientas de medición y revisión de noviembre de 2026

```sh
# Vista previa aislada; abre el panel después de tres segundos de calentamiento.
python3 tools/benchmark.py --panel launcher --seconds 30 --output /tmp/launcher-before.json
python3 tools/benchmark.py --panel launcher --seconds 30 --compare /tmp/launcher-before.json --output /tmp/launcher-after.json

# Vista previa en una sesión Wayland real, con el renderizador nativo.
python3 tools/benchmark.py --native --panel launcher --seconds 30 --output /tmp/launcher-wayland.json

# Lectura de una instancia real ya abierta; no cambia sus paneles ni procesos.
python3 tools/benchmark.py --pid PID --seconds 300 --output /tmp/hyprlarp-native.json

# Comparación del algoritmo; requiere una copia del archivo anterior.
node tools/search_benchmark.js /ruta/al/fuzzy-anterior.js
```

`--root` permite medir otro checkout con el mismo observador. `--interval` controla el muestreo entre 0,2 y 10 segundos. `--compare` exige el mismo modo y panel y añade diferencias numéricas al informe. Una referencia inexistente se rechaza antes de abrir la vista previa.

El observador recorre únicamente los procesos medidos y los hijos creados por cualquiera de sus hilos, en lugar de inspeccionar todos los procesos del equipo en cada muestra. Comprueba la identidad del PID y cuenta también el tiempo de hijos terminados recogido por sus padres. Informa del número de procesos e hilos, la resolución de los ticks de CPU, RSS, PSS y contadores GPU disponibles.

Las variables de medición habilitan marcas puntuales para `backend_ready_ms` y `panel_load_ms`. La segunda mide desde la solicitud del panel hasta que carga su componente; ninguna mide el primer fotograma ni acredita FPS. Las marcas están desactivadas en el uso normal.

Las optimizaciones del launcher preparan palabras y metadatos una sola vez, reutilizan dos filas de la distancia de edición, limitan a 16 las búsquedas en caché y liberan esa caché al cerrar. Los iconos de respaldo se solicitan por lotes únicamente para las filas visibles. La carga de los paneles es asíncrona. Archivos y calculadora se atienden bajo demanda; no añaden un indexador ni temporizadores permanentes. El historial y el diagnóstico tampoco realizan trabajo periódico.

La comparación de JavaScript comprueba que ambas versiones producen la misma suma de resultados y publica la mediana de cinco muestras. Se ejecuta dentro de cada contexto JavaScript para evitar medir llamadas entre contextos por cada entrada. Node utiliza un motor distinto de QML: el resultado describe el algoritmo y no el consumo total del escritorio.

Referencia: [perfilado y rendimiento de Qt Quick](https://doc.qt.io/qt-6/qtquick-performance.html#profiling).

### Comparación del launcher · 16 de noviembre de 2026

Se comparó una copia del checkout anterior con la revisión ampliada, usando el mismo observador, valores iniciales aislados y Qt 6.12 / Quickshell 0.3.2 offscreen/software. Cada proceso tuvo tres segundos de calentamiento; se abrió el launcher y se midieron los 20 segundos siguientes. Se repitió el par con procesos nuevos. La muestra incluye la carga diferida de los iconos tras abrir el panel; no es una medición exclusiva de reposo estable.

| Muestra | CPU sobre un núcleo | RSS final | Pico RSS muestreado | PSS final |
| --- | ---: | ---: | ---: | ---: |
| Anterior 1 | 5,70% | 185,99 MiB | 260,39 MiB | 134,60 MiB |
| Actual 1 | 0,10% | 142,02 MiB | 142,50 MiB | 90,60 MiB |
| Anterior 2 | 5,45% | 214,85 MiB | 287,93 MiB | 163,35 MiB |
| Actual 2 | 0,10% | 141,85 MiB | 142,35 MiB | 90,57 MiB |

No hubo comandos externos dentro de esas ventanas de medida. La resolución de CPU fue de 10 ms; los contadores GPU no estaban disponibles en offscreen. La variación de la versión anterior y estas dos repeticiones no permiten extrapolar un porcentaje de mejora a todos los equipos o sesiones. Los datos originales se guardaron localmente en `.runtime/improvements/controlled-{before,after}*.json` y `comparison.json`.

Una comprobación adicional con Wayland y renderizador nativo confirmó el funcionamiento del observador y sus contadores DRM. La carga del componente del launcher tardó 187 ms y el backend estuvo listo en 282 ms en esa ejecución. Su ventana de recursos fue de solo dos segundos: sirve para validar la herramienta y no para caracterizar el consumo sostenido.

El comparador de JavaScript evaluó 700 nombres y 28.000 combinaciones por muestra, con cinco repeticiones: mediana anterior 184,61 ms y actual 176,47 ms. La mejora observada fue del 4,41% para ese conjunto; ambas versiones produjeron los mismos resultados. No mide la interfaz ni acredita esa reducción sobre toda la CPU del escritorio.

### Sesión real posterior a la actualización

La instalación de usuario se activó y se comprobó su IPC y la conexión con el backend. Después de abrir y cerrar el launcher se observaron 300 segundos con los paneles cerrados, conservando los ajustes personales. La medición leyó cinco procesos del árbol del shell y 31 hilos en Linux 7.3.4 / Qt 6.12 / Quickshell 0.3.2.

| Duración | CPU sobre un núcleo | RSS final / pico muestreado | PSS final |
| --- | ---: | ---: | ---: |
| 300 s | 0,38% | 302,85 / 302,85 MiB | 196,79 MiB |

Los contadores DRM de los motores observados redondearon a 0,00%; no significa consumo absoluto cero ni describe la ocupación global de la GPU. La medición corresponde al árbol del shell con sus servicios reales, a diferencia de las muestras offscreen anteriores. El servicio siguió activo, sin reinicios automáticos ni errores de ejecución registrados durante la validación. Informe local: `.runtime/improvements/native-final-300s.json`.
