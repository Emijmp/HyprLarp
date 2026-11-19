# Pantallas y proyección

Abre **Configuración → Pantallas** para elegir resolución, frecuencia, escala, orientación y posición de cada salida conectada. Las opciones se obtienen de Hyprland, incluidos los monitores desactivados. Selecciona un rectángulo en el esquema y arrástralo; se ajusta a los bordes próximos. También puedes escribir las coordenadas o colocar una pantalla arriba, abajo, a izquierda o derecha de otra. Las distancias se calculan con la escala y la orientación de cada pantalla.

**Super + Shift + P** abre el menú **Proyectar**. Se ha conservado Super + P para el bind existente. Puedes cambiar el nuevo atajo en Atajos. El centro de control y el catálogo de módulos también dan acceso a Pantallas y Proyectar.

El menú ofrece cuatro opciones:

| Opción | Resultado |
| --- | --- |
| Solo pantalla del equipo | Mantiene la pantalla principal y desactiva las demás. |
| Duplicar | Muestra el contenido de la pantalla principal en las demás salidas. |
| Extender | Crea un escritorio independiente en cada pantalla y las alinea hacia la derecha. |
| Solo pantalla externa | Mantiene la pantalla secundaria elegida y desactiva las demás. |

Puedes elegir el origen y la pantalla secundaria cuando hay varias conectadas. En el editor avanzado, Contenido permite duplicar una salida concreta y conservar otras como escritorio extendido. Una pantalla duplicada puede usar su propia resolución y frecuencia; las proporciones distintas pueden producir franjas o escalado según el compositor y el proyector.

## Probar y confirmar

Editar un control solo modifica el borrador. **Probar cambios** aplica el diseño durante **20 segundos**. Las cuatro opciones rápidas también abren una prueba. Un aviso aparece en las pantallas activas para conservar el resultado o recuperar inmediatamente la configuración anterior. El cierre del panel o de configuración mantiene ese aviso.

Un proceso independiente conserva el temporizador y la configuración anterior. Si se cierra Quickshell o su backend durante la prueba, el proceso continúa y recupera la imagen al vencer el plazo. La confirmación comprueba que siguen conectadas las mismas pantallas y que Hyprland aplicó los valores solicitados; únicamente entonces se guarda el diseño. Se rechazan apagar todas las pantallas, duplicaciones circulares, modos no anunciados, escalas incompatibles y pantallas extendidas superpuestas.

Las pruebas pendientes se comparten entre las ventanas de la misma sesión. Un bloqueo de archivo evita que dos procesos inicien pruebas simultáneas. Los recursos del temporizador viven en un directorio privado de `$XDG_RUNTIME_DIR/hyprlarp/d`, separado por instancia de Hyprland, y se conservan hasta diez diagnósticos recientes.

## Guardado y conexiones

Los diseños confirmados se guardan aparte de los temas en `~/.config/hyprlarp/display-profiles.json`, respetando `XDG_CONFIG_HOME` y `HYPRLARP_STATE_DIR`. Se recuerdan hasta veinte combinaciones de pantallas según el conector y los datos de identidad disponibles. Una pantalla sin número de serie puede compartir identidad con otra del mismo modelo.

Al iniciar el shell, recargar Hyprland o conectar otra combinación de pantallas, se recupera el diseño compatible guardado. Los cambios se reciben por eventos; no hay sondeo permanente. Si el proyector que era la única salida activa se desconecta, se intenta recuperar la pantalla restante. La configuración principal de Hyprland conserva sus reglas originales; al cargar el shell se aplican las elecciones confirmadas sobre ellas.

Los perfiles de apariencia, su historial de deshacer y Restablecer todo conservan los diseños de pantallas. La vista previa permite revisar el editor y bloquea las operaciones nativas.

## Validación

Las pruebas cubren los cuatro modos, modos y escalas, colocación, duplicaciones inválidas, guardado y cancelación, recuperación después de terminar el backend y navegación del editor. Las pruebas nativas usan una instancia aislada de Hyprland con salidas virtuales. El comportamiento de un proyector físico y sus modos depende del equipo y de lo que anuncie por el cable conectado.

Referencia: [configuración de monitores de Hyprland](https://wiki.hypr.land/configuring/core/monitors/) y [duplicación de salidas](https://wiki.hypr.land/configuring/core/monitors/modes/).
