# Bloqueo con identidad HyprLarp

`hyprlarp lock`, el menú de sesión y hypridle abren el mismo bloqueo nativo de hyprlock. Al bloquear se leen los ajustes guardados: paleta, acento, fuente, radios y el diseño lateral o centrado elegido en Apariencia para el inicio de sesión. El gato con sombrero acompaña a HYPRLARP; se muestran el usuario, la hora, la distribución del teclado y el campo de contraseña. El diseño usa coordenadas proporcionales al área que dibuja hyprlock; el cuadro central se ancla al centro de cada salida y la tipografía y el logo siguen su escala. Esto conserva la alineación al usar 125 %, 150 % o 200 % y al girar una pantalla.

El fondo interno actual se copia a un recurso privado. Con Waypaper se lee su imagen vigente; los SVG y fondos animados se preparan como una imagen fija con tiempo de conversión limitado. Si falta el fondo o la herramienta de conversión, el bloqueo usa el color del tema. Los recursos ya preparados se reutilizan hasta cambiar su origen o el acento. No hay un reproductor ni un observador nuevo funcionando durante el bloqueo.

Las imágenes y metadatos se guardan en `~/.config/hyprlarp/lock-assets`, respetando `XDG_CONFIG_HOME` y `HYPRLARP_STATE_DIR`. Los nombres originales y sus caracteres especiales nunca se insertan como instrucciones de hyprlock: el proceso recibe un descriptor del directorio privado. `generated-lock.conf` se genera de nuevo para cada apertura y está pensado para utilizarse mediante `hyprlarp lock`.

La autenticación permanece en hyprlock y en la configuración PAM existente. Se solicita contraseña desde el principio (`--grace 0`), y el bloqueo tiene un proceso independiente de Quickshell: un reinicio del shell conserva el bloqueo. No se modifica PAM ni se guarda la contraseña en HyprLarp.

Los cambios de tema se reflejan al abrir el siguiente bloqueo. Durante un bloqueo abierto su apariencia queda estable.

Las pruebas automáticas validan la generación, los recursos, los argumentos y el análisis de configuración del binario nativo en una pantalla inexistente. Esa validación no bloquea la sesión ni sustituye una prueba de autenticación con el usuario.

Referencia: [configuración y widgets de hyprlock](https://wiki.hypr.land/hypr-ecosystem/user/hyprlock/).
