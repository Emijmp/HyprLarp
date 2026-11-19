# Asistente de primera ejecución

HyprLarp ofrece un recorrido inicial para elegir tema, distribución y estilo del panel,
posición de la barra, rendimiento y accesibilidad. Las elecciones se preparan en el
asistente y se guardan juntas al finalizar; los ajustes que no se eligen se conservan.
La revisión final muestra los cambios antes de aplicarlos.

El asistente se abre automáticamente en una instalación nueva. Al actualizar una
instalación existente, la configuración actual se conserva y el asistente queda
disponible desde **Configuración → General → Asistente de primera ejecución**.
El comando `hyprlarp welcome` lo abre en el shell activo o en una ventana independiente
si el shell no está en ejecución.
Las vistas previas y la ventana independiente de ajustes no lo abren automáticamente.

Los atajos se muestran como referencia. El asistente no instala el greeter, regenera
binds ni modifica `hyprland.lua`. Los cambios de preferencias que guarda forman una
sola operación del historial y pueden deshacerse desde Configuración.

## Estado y recuperación

`~/.config/hyprlarp/onboarding.json` registra por separado si el recorrido se completó
(`completed`) o se omitió (`skipped`), la versión de formato y la versión de HyprLarp.
Omitir no cambia preferencias y evita nuevas aperturas automáticas. Cerrar la ventana
sin completar el recorrido conserva la configuración y deja pendiente el primer inicio.

El instalador conserva la propiedad `first_run` en su manifiesto para distinguir una
instalación nueva incluso cuando ya creó un `settings.json` con valores iniciales.
Una actualización de instalaciones anteriores no fuerza un recorrido nuevo.

Si el archivo de estado está dañado o pertenece a una versión futura, HyprLarp conserva
sus bytes y mantiene operativo el escritorio. El asistente muestra el problema y no
sobrescribe ese estado. Un estado mediante enlace simbólico también se conserva.

Si falla el guardado de preferencias, el recorrido no se marca como completado. Si
las preferencias se guardaron pero falla el archivo de estado, las elecciones y su
historial se conservan: se puede reintentar finalizar sin duplicar la operación.
