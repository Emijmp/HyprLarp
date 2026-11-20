# Revisión de experiencia para la publicación

La revisión conserva la distribución visual y las funciones del shell. Las pruebas
utilizan Qt/Quickshell real con ajustes temporales y acciones de dispositivos
desactivadas; no requieren las preferencias ni los archivos del escritorio del usuario.

## Correcciones verificadas

| Caso | Comportamiento corregido | Comprobación |
| --- | --- | --- |
| Mensajes de error y estado | Respetan el tamaño mínimo de fuente y la escala de accesibilidad. Un mensaje de 11 px se muestra a 28 px con mínimo de 16 y escala de 175 %. | Interfaz real, incluida su identificación como alerta accesible. |
| Primera muestra de CPU o dato ausente | Recursos muestra `N/D` mientras CPU sea `null` o no exista. Una medición válida de cero sigue mostrando `0%`. | Estados ausente, nulo, cero y valor numérico. |
| Wi-Fi sin redes | Si el adaptador ya está activo, ofrece actualizar la búsqueda; si está apagado, indica activarlo; si falta el servicio, identifica NetworkManager. | Los tres estados con el componente real. |
| Bluetooth sin dispositivos | Distingue adaptador ausente, Bluetooth apagado y búsqueda de un dispositivo listo para vincular. | Los tres estados con el componente real. |

## Cobertura de teclado y legibilidad

`tests/test_release_ux.py` abre los 21 paneles principales con texto al 200 % y
objetivos grandes: Control, Audio, Brillo, Energía, Modo nocturno, USB, Launcher,
Barra y bandeja, Wi-Fi, Bluetooth, Notificaciones, Portapapeles, Multimedia,
Calendario, Sesión, Recursos, Rendimiento, Batería, Fondos, Capturas y Proyección.
Comprueba que reciben foco, aceptan Tab y Shift+Tab y se cierran con Escape.
También reduce la altura disponible con un control situado al final de una lista
larga y verifica que el control enfocado continúa visible.

Esta prueba de entrada, recorrido y salida complementa las comprobaciones existentes:

- `tools/AccessibilityChecks.qml`: activación con Espacio y Enter, checkbox, sliders,
  campos de texto, semántica de contraseñas y edición de capturas mediante teclado.
- `tools/WelcomeChecks.qml`: recorrido y revisión del asistente, borrador independiente,
  navegación con texto al 160 % y 200 %, foco visible y Enter sin confirmación doble.
- `tools/SettingsChecks.qml`: foco en la ventana de configuración, historial y controles
  de guardado, incluidas las operaciones de Deshacer, Rehacer y Restablecer.
- `tools/LauncherChecks.qml`, `tools/SessionChecks.qml`, `tools/ShortcutChecks.qml` y
  `tools/DisplayChecks.qml`: búsqueda y activación, confirmaciones de sesión, atajos y
  prueba/recuperación de pantallas.
- La comprobación completa `python3 tools/check.py --ui-only` carga todos los paneles
  y las ocho páginas de configuración, comprueba sus temas y mantiene una vista previa
  normal abierta. Sus registros son parte de la evidencia de la publicación.

Los textos de error se mantienen como texto plano y se pueden copiar mediante un
botón accesible. Los estados vacíos indican la siguiente acción según los datos
disponibles; un dato ausente no se presenta como una medición exitosa.

## Matriz de validación en una sesión gráfica real

La tabla separa lo que puede automatizarse de las comprobaciones que necesitan un
compositor, hardware o una sesión de inicio de sesión. Debe completarse antes de
declarar compatibles esas configuraciones concretas.

| Entorno o transición | Pasos y resultado esperado | Evidencia necesaria |
| --- | --- | --- |
| Primer arranque en una instalación nueva | Iniciar HyprLarp, recorrer los cuatro pasos por teclado, revisar cambios y terminar. Reiniciar el shell: no vuelve a ofrecer el recorrido. | Resultado del recorrido y estado persistente. |
| Actualización de una instalación existente | Actualizar el paquete manteniendo ajustes y binds activos, abrir General y volver al asistente manualmente. | Hashes anteriores y posteriores; sin recorrido forzado. |
| Inicio de sesión con greetd | En una VM o un equipo de prueba, activar el greeter opcional, usar una contraseña incorrecta, corregirla e iniciar la sesión elegida. El error debe ser legible y no dejar controles bloqueados. | Inicio de sesión real mediante PAM, usuario de prueba y registro del greeter. |
| Bloqueo e identidad | Bloquear desde un equipo de prueba en escala 100 %, 150 % y 200 %. Comprobar posición, contraste, idioma del teclado, error de contraseña y desbloqueo. | Fotograma y desbloqueo real en cada configuración. |
| Tema y fondo del greeter | Cambiar tema, fondo y diseño lateral/centrado; esperar la sincronización y abrir una nueva sesión del greeter. | Apariencia real, no solo la vista previa. |
| Suspensión y reanudación | Suspender con un panel abierto y con el escritorio en reposo; reanudar varias veces. Verificar bloqueo, teclado, audio, conectividad y ausencia de reinicios repetidos del shell. | Ciclos reales con sus horas y registros. |
| Proyector y monitor externo | Conectar y desconectar; probar duplicar, extender y solo pantalla externa. Rechazar una prueba de resolución y comprobar la restauración automática. | Geometría real y recuperación; monitores y escalas utilizados. |
| Pantallas de distinta escala u orientación | Alternar monitor enfocado, abrir paneles, mover el puntero, bloquear y capturar pantalla en cada salida. | Resultados por salida, incluyendo rotación y escalas mixtas. |
| Navegación asistida | Usar Orca/AT-SPI y solo teclado para launcher, configuración, errores, contraseñas y confirmaciones de sesión. | Lectura y orden de foco observados con el lector real. |
| Sesión prolongada | Durante varias horas, alternar paneles y temas, reconectar dispositivos y suspender/reanudar. Comparar memoria después del calentamiento y revisar errores. | Informe de estabilidad con duración real, muestras y transiciones ejercidas. |

Las pruebas offscreen comprueban componentes y eventos reales de Qt; no equivalen
a una autenticación PAM, una suspensión del kernel, una conexión física de monitor
o una evaluación con un lector de pantalla. Las filas físicas conservan su estado
pendiente hasta disponer de esa evidencia. Una publicación no debe presentarlas como
aprobadas basándose solamente en la suite automatizada.
