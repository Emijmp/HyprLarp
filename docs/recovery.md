# Aislamiento de fallos y recuperación

La instalación incluye `hyprlarp.service` en el directorio de servicios de usuario. El arranque de Hyprland ejecuta `hyprlarp start`: guarda únicamente las variables necesarias de esa sesión en `$XDG_RUNTIME_DIR/hyprlarp/session.env`, con permisos privados, y arranca el servicio. No importa variables al entorno global de systemd ni inicia el escritorio desde una TTY o antes de tener Wayland.

Un supervisor pequeño de Python ejecuta Quickshell y conserva su propio estado privado en `$XDG_RUNTIME_DIR/hyprlarp`. Si el proceso del shell falla, vuelve a intentarlo después de dos segundos. Al tercer fallo en cinco minutos abre una interfaz de recuperación independiente. Si el proceso arranca pero no completa su comprobación de salud en 18 segundos, pasa directamente a recuperación. Una condición comprueba que siguen existiendo la pantalla y la misma instancia de Hyprland antes de arrancar; cerrar la sesión no deja un proceso intentando reconstruirla. Systemd conserva además su límite de tres reinicios en cinco minutos por si falla el propio supervisor.

Al arrancar se exigen tres comprobaciones consecutivas del proceso, el destino IPC exacto `target shell` y una barra visible con dimensiones positivas. Una configuración que desactiva expresamente todas las barras puede arrancar sin ellas. La recuperación se comprueba por su destino `recovery` y su propia barra. El control no permanece sondeando una vez iniciado el shell.

## Fallos de componentes

Cada módulo de barra, panel y página de ajustes se carga con un límite de fallos. Un error de carga muestra una alternativa con **Reintentar componente** y mantiene disponibles los demás componentes. Tres fallos del mismo componente en cinco minutos lo dejan desactivado hasta un reintento explícito. Las excepciones inesperadas de las fuentes del backend siguen ese mismo criterio; los errores habituales de dispositivos o comandos se muestran sin desactivar el componente. Una acción fallida libera su estado ocupado.

En **Configuración → General → Fallos y recuperación** se puede consultar el componente afectado, copiar su último error y reintentarlo. El registro privado `module-faults.json` conserva la desactivación entre reinicios y limita los eventos y mensajes guardados. No modifica `settings.json` ni elimina el componente de la configuración.

Este aislamiento cubre las cargas QML y excepciones gestionadas. Los módulos QML comparten el proceso de Quickshell: un fallo nativo de Qt o de un complemento termina ese proceso y lo atiende el supervisor. El backend sigue siendo un proceso separado; tras agotar sus reconexiones, la interfaz solicita recuperación.

## Modo de recuperación

`recovery.qml` usa controles básicos de Qt y no importa el tema, el Bridge ni los componentes del shell. Presenta una barra en cada pantalla y una ventana con **Reintentar shell**, **Abrir terminal**, **Configuración** y **Diagnóstico**. Conserva el tamaño de texto de accesibilidad incluso si no puede cargar la interfaz normal. El diagnóstico y la configuración pueden seguir mostrando el error que impidió el arranque; la terminal funciona mediante un helper independiente.

```sh
hyprlarp start
hyprlarp recover  # abrir la recuperación desde una terminal
hyprlarp retry    # volver a intentar la interfaz normal
systemctl --user status hyprlarp.service
journalctl --user -u hyprlarp.service -n 40
hyprlarp stop
```

`start` es idempotente cuando el shell supervisado está sano, también en recuperación. `retry` vuelve a la interfaz normal y reinicia el contador de fallos del proceso; no borra los fallos persistentes de los componentes. `stop` detiene la supervisión y el shell. `hyprlarp run` ejecuta el supervisor en primer plano para desarrollo; las vistas previas y la aplicación independiente de ajustes no se convierten en servicios.

La supervisión termina únicamente su proceso de Quickshell al detenerse o cambiar de modo. Las aplicaciones abiertas desde el launcher y hyprlock conservan su vida independiente. El backend cierra sus propios helpers al desaparecer la interfaz. No se reinicia greetd, hypridle ni el compositor. Reintentar y abrir recuperación conservan los ajustes y el historial.

Las actualizaciones realizadas con el instalador mientras el shell está funcionando esperan a que cierre la instancia anterior, aplican el paquete preparado y comprueban el nuevo arranque. Si falla la activación, restauran los archivos, el servicio y los ajustes anteriores y vuelven a iniciar la versión previa. Las instalaciones con `--prefix` permanecen aisladas y nunca controlan la sesión real.

Referencia: [supervisión y límites de reinicio de systemd](https://www.freedesktop.org/software/systemd/man/latest/systemd.service.html).
