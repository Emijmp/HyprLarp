# Validación en Hyprland

Las pruebas automáticas usan Qt offscreen y estados aislados. No prueban los sockets del compositor, D-Bus, PAM ni hardware físico. Esta lista permite completar esa validación desde una sesión real, sin confundirla con el renderizado de la vista previa.

## Monitores y escala

1. Desde Wayland puedes comprobar los tipos nativos sin crear barras con `quickshell --path native-types.qml`; este control requiere el backend Wayland de Qt y no funciona con offscreen. Abre HyprLarp con `./bin/hyprlarp run` después de revisar la instalación y las dependencias. Mantén una terminal disponible.
2. En Configuración → Barra, selecciona cada salida por su nombre de Hyprland. Pon una barra horizontal y otra vertical, y modifica margen, longitud y grosor de una sola pantalla. La otra debe conservar sus ajustes.
   Con Reservar espacio para ventanas activado, prueba las cuatro posiciones y longitudes de 25%, 75% y 100%, también centradas y al final. Las ventanas en mosaico o maximizadas deben dejar libre la barra. Al desactivar la reserva o esconder la barra debe liberarse el espacio. La geometría usa tres anclajes y márgenes complementarios para que acortar la barra no suprima su zona exclusiva.
3. Mueve ventanas y cambia espacios desde ambas barras. El recuadro debe seguir el espacio activo de cada monitor. Comprueba espacios con nombre y números fuera del rango 1–N. Abre los diez espacios en un monitor: en Solo actual debe aparecer únicamente el activo. La rueda debe recorrer los diez. Prueba Actual y puntos: solo el activo debe llevar número. En Números compactos deben aparecer como máximo cinco celdas; prueba ambos grupos de puntos.
4. Desconecta y reconecta una pantalla. Su barra debe desaparecer y volver con sus ajustes; los paneles deben abrirse en la pantalla enfocada. Prueba también tras cambiar la escala a 1.25, 1.5 o 2 desde tu configuración del compositor.
5. Reduce la longitud de la barra o añade todos los módulos. Las zonas no deben superponerse; el contenido que no quepa debe poder desplazarse. Prueba arrastrar módulos y las flechas de respaldo. En Módulos → Añadir busca una función y filtra por categoría; añade calendario, brillo, perfiles y capturas. Deben abrir su función o página. Los botones de sesión deben pedir confirmación antes de ejecutarse.

## Separación de ventanas

1. En Apariencia → Separación de ventanas, mueve el valor exterior común con dos ventanas en mosaico. Comprueba que activa la personalización y respeta el espacio reservado de la barra.
2. Activa los bordes independientes y asigna valores distintos a los cuatro lados. Cambia la separación interior y prueba Deshacer/Rehacer dentro de configuración, incluido un arrastre completo.
3. Recarga Hyprland y reinicia el shell: los valores deben conservarse, también si cargas `hyprland-look.lua` después de la integración. Comprueba un workspace sin reglas propias de separación.
4. Desactiva la personalización: deben recuperarse los valores de tu configuración original. Restablece Apariencia y deshaz ese restablecimiento. Si Hyprland no responde, comprueba el mensaje y Reintentar aplicación.

## Redondez

Desde Apariencia → Redondez cambia el valor general y pon barra a 0, paneles a 6, botones a 4 y espacios a 2. Comprueba que las excepciones se conservan al modificar el valor general, que Heredar recupera ese valor y que Deshacer restaura todos los cambios de un arrastre. En Módulos → Aspecto prueba el radio de una sola pantalla. El borde de la barra se conserva y los módulos no deben mostrar el antiguo trazo superior.

## Integraciones

- Wi-Fi: con NetworkManager activo, conecta una red abierta, una guardada sin reescribir su contraseña y una protegida con contraseña. Prueba una contraseña incorrecta: el error debe permanecer visible en el formulario. Con dos adaptadores, comprueba que conectar/desconectar respeta el elegido. Pulsa Buscar para obtener resultados recientes.
- Bluetooth: con BlueZ y python-gobject disponibles, busca y vincula un dispositivo nuevo; confirma el código o introduce su PIN desde el panel. En un teclado, introduce el código mostrado en el teclado remoto. Comprueba que queda vinculado y conectado, y que una conexión posterior no vuelve a vincularlo. Prueba cancelar, rechazar y cerrar el panel durante la vinculación; la solicitud debe cerrarse y detenerse la búsqueda iniciada por el shell.
- Fondos: elige una carpeta con el explorador y otra escribiendo su ruta. Prueba nombres con espacios, `#`, `%` y Unicode; aplica una imagen, reinicia y comprueba que se conserva en todas las pantallas. Una ruta inválida debe conservar la configuración anterior. Prueba el selector desde el panel y desde configuración, incluyendo Deshacer y Restablecer solo dentro de esta última.
- Audio: cambia salida y entrada; silencia el micrófono; inicia dos reproductores y ajusta un flujo sin alterar el otro.
- OSD: usa las teclas de volumen, silencio, micrófono y brillo, también con sus módulos quitados. Debe aparecer en la pantalla enfocada y caducar sin tomar foco. Cambia posición y duración en General, prueba su demostración y desactívalo. No debe aparecer al iniciar el shell, sustituir un dispositivo ni durante Presentación. El brillo automático requiere los eventos backlight de udev del controlador.
- Energía: con power-profiles-daemon y python-gobject instalados, abre Energía y cambia entre los perfiles que exponga el hardware. Comprueba el resultado con `powerprofilesctl get`; un perfil no soportado no debe ofrecerse. Verifica que los cambios hechos por otra app actualicen el módulo.
- Batería: contrasta capacidades, ciclos, voltaje, potencia y salud con `/sys/class/power_supply`. Los campos no informados deben decir No disponible; los tiempos calculados llevan `~`. Prueba conectado, desconectado y sin batería. Los límites de carga solo se leen; no se cambian desde el shell.
- Modo nocturno: activa el filtro manualmente y cambia temperatura. Prueba el horario atravesando medianoche y el cambio de minuto; Deshacer, Rehacer y Restablecer desde configuración deben volver a aplicar el estado correspondiente. Al cerrar el shell debe detenerse su proceso. Una instancia externa de hyprsunset debe producir un conflicto, sin detenerla ni cambiarla.
- USB: conecta y desconecta un periférico y una unidad de datos. Confirma que el inventario cambia sin refresco manual, y que quitar el módulo/cerrar el panel detiene sus listeners. En una unidad de prueba, verifica montar, abrir y desmontar. Expulsar requiere confirmación y debe fallar sin forzar si un volumen está ocupado. No probar estas acciones sobre unidades que contengan datos en uso. Sin UDisks/GIO debe seguir disponible el inventario de sysfs, con un mensaje para las acciones no disponibles.
- Bandeja: añade el módulo, abre una aplicación compatible y prueba clic principal, central, rueda y menú contextual. Oculta su ID desde Módulos y recupéralo con el botón de expansión.
- Portapapeles: copia texto e imagen, fija ambos, vacía el historial y comprueba que los fijados siguen disponibles. Pausa la captura y copia otro texto: no debe añadirse. La caducidad conserva los fijados y cuenta desde la primera observación de cada entrada.
- Notificaciones: envía un aviso de una aplicación real, busca su texto, filtra por aplicación y cambia sus reglas. Sonido está desactivado salvo activación explícita por aplicación.
- Capturas: prueba región, ventana y escritorio, los temporizadores y Cancelar. En el editor, dibuja una flecha horizontal, texto, recorte y un área negra; abre el PNG final para confirmar el resultado.
- Perfiles: guarda uno, cambia barra/tema y vuelve a aplicarlo. Deshazlo desde configuración. Exporta e importa un perfil y una paleta. Una importación inválida debe conservar el estado anterior.
- Atajos: captura una combinación, comprueba conflictos y aplica con varios cambios de ajustes pendientes. Solo se escribe el archivo gestionado de bindings al aplicar explícitamente.

## Presentación, bloqueo y suspensión

Activa Presentación desde Control o Super + Ctrl + D. Deben desaparecer los avisos flotantes y detenerse el reposo automático mientras el inhibidor Wayland esté activo. Desactívalo para recuperar el comportamiento normal. La app no elimina listeners ni cambia los tiempos de tu configuración de hypridle.

Prueba el bloqueo manual y, por separado, la suspensión desde una sesión con el `hypridle.conf` gestionado. Comprueba desbloqueo con PAM y vuelta de la suspensión, con una y varias pantallas. Estas acciones se verifican manualmente; las pruebas del repositorio no las ejecutan.

## Medición sostenida

Identifica el PID de la instancia de Quickshell que ejecuta HyprLarp con `pgrep -a -x quickshell` o `pgrep -a -x qs`. Usa ese PID, no el de otro shell:

```sh
python3 tools/benchmark.py --pid 12345 --seconds 300 --output .preview/native-idle.json
```

Repite con Recursos, Audio, notificaciones activas y el blur que realmente uses. El comando solo lee el proceso y sus descendientes: no lo inicia, cierra ni modifica. Cambia 12345 por el PID real.

El informe incluye CPU expresada sobre un núcleo, RSS, PSS cuando se permite leerlo y contadores DRM por motor cuando el controlador los expone. Un valor GPU nulo significa que la información no está disponible. Los porcentajes por motor suman clientes y no son la ocupación global del dispositivo. La resolución de ticks puede producir 0.00% en intervalos sin ticks contabilizados; no implica consumo absoluto cero.


## Decoración, instalación y recursos

- En Apariencia cambia cada detalle por separado, activa Mínimo y vuelve a Sutil. Comprueba que conserva las elecciones, permite Deshacer/Rehacer solo desde configuración y recupera los valores iniciales con Restablecer sección.
- Ejecuta los scripts con un `--prefix` temporal, prueba reinstalar y desinstalar, y comprueba que se conservan los ajustes por defecto y que `--purge` los elimina. El conjunto automático también prueba rutas reservadas, manifiestos manipulados, enlaces simbólicos, rollback y lanzamiento Desktop Entry con GLib.
- Repite la medición con `tools/benchmark.py --pid PID --seconds 300` sobre el escritorio real. Incluye copiar una imagen 4K, varias aplicaciones multimedia, muchos avisos y activar/desactivar los módulos que uses. Comprueba que cerrar el shell no deja sus procesos de captura o del filtro nocturno; los editores externos y el bloqueo son aplicaciones independientes.

## Binds actuales y editor

1. Sigue [binds.md](binds.md): carga el preludio antes de tus declaraciones y la integración al final. Conserva los binds de terminal, cierre, explorador, ventanas, ratón, espacios y scratchpad.
2. Prueba Super + Espacio, Super + M, Super + Coma, Super + X, Super + V y Print tras transferir las acciones de Noctalia. Comprueba que Super + Shift + S sigue moviendo al espacio especial. Alt + Tab debe recorrer ventanas con Hyprland.
3. Mantén volumen/brillo pulsado y prueba una segunda pulsación tras soltar: los callbacks de repetición y release deben conservar su funcionamiento. El micrófono y la reproducción del archivo original deben seguir operativos.
4. En Atajos añade un comando de prueba y una acción del shell, cambia su combinación con Capturar, desactiva y elimina. Deshaz y rehace los cambios dentro de configuración y pulsa Aplicar. Un duplicado debe rechazarse.
5. En Actuales mueve una función Lua a otra combinación y desactívala. Elimina su personalización para restaurarla. Prueba un bind dentro de un submap: sus otros binds deben seguir funcionando. Un conflicto conserva el original salvo reemplazo explícito.
6. Prueba reinstalar y retirar una instalación temporal. La retirada solo debe desactivar su propio adaptador; los bloques de integración y los originales del usuario se gestionan en su archivo, sin reescrituras del instalador.
7. Abre Sesión con Super + X y prueba 2 Suspender, 3 Cerrar sesión, 4 Reiniciar y 5 Apagar cancelando cada confirmación con Escape. Prueba también el teclado numérico y un botón enfocado con Tab. Enter confirma; 1 bloquea directamente. Los números deben actuar solo dentro del menú. Las pruebas automáticas inyectan estas pulsaciones en vista previa, donde el backend impide ejecutar acciones de sesión.

## Waypaper y fondos animados

1. En Fondos elige Externo y abre Waypaper. Con mpvpaper selecciona un vídeo local y comprueba que se ve debajo de la barra, paneles y ventanas en todas las salidas seleccionadas.
2. Cambia de vídeo y prueba sonido/pausa desde Waypaper con socat instalado. Comprueba las opciones y la carpeta del gestor externo.
3. Vuelve a HyprLarp y comprueba que recupera la imagen anterior. Waypaper conserva sus reproductores: detén o cambia el vídeo desde ese gestor si corresponde.
4. Prueba Deshacer/Rehacer y Restablecer sección exclusivamente desde configuración. Restaura el último fondo con el botón y activa/desactiva Restaurar al iniciar. La app independiente no debe restaurarlo automáticamente al abrirse; el botón manual sí debe funcionar.
5. Reinicia el shell con restauración activada y desactivada. Comprueba que no se añade un sondeo de Waypaper y que el módulo de Fondos sigue disponible.
