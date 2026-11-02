# Validación en Hyprland

Las pruebas automáticas usan Qt offscreen y estados aislados. No prueban los sockets del compositor, D-Bus, PAM ni hardware físico. Esta lista permite completar esa validación desde una sesión real, sin confundirla con el renderizado de la vista previa.

## Monitores y escala

1. Desde Wayland puedes comprobar los tipos nativos sin crear barras con `quickshell --path native-types.qml`; este control requiere el backend Wayland de Qt y no funciona con offscreen. Abre HyprLarp con `./bin/hyprlarp run` después de revisar la instalación y las dependencias. Mantén una terminal disponible.
2. En Configuración → Barra, selecciona cada salida por su nombre de Hyprland. Pon una barra horizontal y otra vertical, y modifica margen, longitud y grosor de una sola pantalla. La otra debe conservar sus ajustes.
3. Mueve ventanas y cambia espacios desde ambas barras. El recuadro debe seguir el espacio activo de cada monitor. Comprueba espacios con nombre y números fuera del rango 1–N. Abre los diez espacios en un monitor: en Solo actual debe aparecer únicamente el activo. La rueda debe recorrer los diez. Prueba Actual y puntos: solo el activo debe llevar número. En Números compactos deben aparecer como máximo cinco celdas; prueba ambos grupos de puntos.
4. Desconecta y reconecta una pantalla. Su barra debe desaparecer y volver con sus ajustes; los paneles deben abrirse en la pantalla enfocada. Prueba también tras cambiar la escala a 1.25, 1.5 o 2 desde tu configuración del compositor.
5. Reduce la longitud de la barra o añade todos los módulos. Las zonas no deben superponerse; el contenido que no quepa debe poder desplazarse. Prueba arrastrar módulos y las flechas de respaldo. En Módulos → Añadir busca una función y filtra por categoría; añade calendario, brillo, perfiles y capturas. Deben abrir su función o página. Los botones de sesión deben pedir confirmación antes de ejecutarse.

## Redondez

Desde Apariencia → Redondez cambia el valor general y pon barra a 0, paneles a 6, botones a 4 y espacios a 2. Comprueba que las excepciones se conservan al modificar el valor general, que Heredar recupera ese valor y que Deshacer restaura todos los cambios de un arrastre. En Módulos → Aspecto prueba el radio de una sola pantalla. El borde de la barra se conserva y los módulos no deben mostrar el antiguo trazo superior.

## Integraciones

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
