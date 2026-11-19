# Panel de rendimiento de HyprLarp

Abre **Configuración → General → Rendimiento del shell**, busca `> rendimiento` en el launcher o ejecuta `hyprlarp toggle performance`. También está disponible desde Recursos y se puede añadir como acceso a la barra. La ventana independiente de configuración puede abrirlo sin iniciar otro shell.

## Consumo actual

El panel lee CPU, RSS, PSS y número de hilos de sus procesos principales: Quickshell, su backend y, cuando existe, su supervisor. No suma aplicaciones lanzadas desde el shell, hyprlock ni herramientas externas. El panel Recursos sigue mostrando el consumo del equipo completo.

La CPU se calcula con diferencias de los contadores de usuario y sistema de `/proc/PID/stat`, comprobando la identidad de cada PID. El 100% equivale a un núcleo; puede superar ese valor. La primera lectura muestra N/D hasta disponer de dos muestras. Un contador sin avance puede producir 0,00%, sin demostrar consumo absoluto cero. La resolución del contador se indica en el panel.

RSS suma memoria residente y puede contar páginas compartidas más de una vez. PSS reparte esas páginas entre los procesos que las comparten; si no está disponible, se muestra N/D. Su lectura se reutiliza durante ocho segundos. El pico de memoria es el máximo observado en las muestras y no el máximo absoluto entre ellas.

Se toma una muestra cada dos segundos **solo con el panel abierto y sin pausar**. Actualizar permite una lectura manual estando pausado. Los gráficos conservan hasta 60 muestras de la apertura actual en memoria y se redibujan cuando reciben datos; no tienen un temporizador de animación. No se ejecutan comandos externos para obtener estas lecturas.

**Vista compacta** oculta gráficos y detalles por proceso sin cambiar el muestreo. Los umbrales iniciales son 80% de CPU y 1024 MiB RSS; se editan en Avisos de consumo y los valores que los superan se resaltan. Se guardan en `performance-preferences.json`, aparte de la configuración general. El indicador de estabilidad resume los eventos de fallos aislados registrados en los últimos cinco minutos; no intenta contar reinicios del compositor.

## Arranque y carga de paneles

La interfaz confirma que recibió su configuración inicial. La diferencia respecto del inicio de su proceso Quickshell proporciona el tiempo de arranque; se conserva al reconectar únicamente el backend. Una conexión tardía sin registro anterior muestra N/D en vez de presentar la antigüedad del proceso como tiempo de arranque. Se usa el reloj desde el arranque de Linux para los tiempos de creación de procesos.

La carga de un panel se mide desde su solicitud hasta que el Loader completa el componente. Se conservan los últimos diez tiempos en memoria. Estas medidas **no son tiempo hasta el primer fotograma ni FPS**.

La revisión es una huella del paquete instalado; en un checkout se calcula a partir de su código y recursos. No es el número de versión del esquema de ajustes, y no requiere Git ni una consulta de red.

## Mediciones y comparación

Escribe un nombre opcional y elige 15, 30 o 60 segundos. **Medir** guarda la CPU media ponderada por la duración real, RSS final y pico muestreado, PSS final, procesos, hilos, arranque y revisión. La duración real puede superar ligeramente la elegida porque termina con la siguiente muestra. El panel abierto forma parte de la carga medida.

Cerrar el panel, cambiar sus pantallas o modificar la configuración cancela la medición que está en curso. No se guarda una ventana que mezcle esos contextos. El historial privado `performance-history.json` conserva hasta veinte informes, con lectura limitada a 256 KiB y reemplazo atómico; las muestras de los gráficos no se guardan continuamente. `performance-startup.json` identifica el arranque del proceso nativo; la vista previa y los ajustes independientes usan archivos separados. Ninguno de estos archivos modifica preferencias, binds ni perfiles.

Busca informes por nombre, fecha o revisión. Selecciona **A** como referencia y **B** como destino. La comparación calcula B − A: CPU en puntos porcentuales, memoria en MiB y arranque en milisegundos. Solo muestra diferencias cuando coinciden modo, renderizador, configuración, pantallas y versión del kernel. Las revisiones del paquete pueden ser distintas. Incluso con contexto compatible, la carga de otras aplicaciones puede variar; estas cifras no prueban por sí solas una mejora universal. La vista previa, la ventana independiente de ajustes y el shell nativo se distinguen.

**Copiar informe B** copia JSON y **Copiar CSV B** copia una fila compatible con hojas de cálculo; **Eliminar medición B** retira únicamente ese informe. Las herramientas CLI y las mediciones históricas de [performance.md](performance.md) siguen disponibles.

Referencias: [contadores de procesos de Linux](https://man7.org/linux/man-pages/man5/proc_pid_stat.5.html), [memoria proporcional PSS](https://man7.org/linux/man-pages/man5/proc_pid_smaps.5.html), [relojes de Linux](https://man7.org/linux/man-pages/man2/clock_gettime.2.html).
