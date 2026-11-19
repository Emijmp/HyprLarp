# Diagnóstico de la instalación

```sh
hyprlarp doctor
hyprlarp doctor --json
hyprlarp doctor --report /tmp/hyprlarp-diagnostico.json
hyprlarp doctor --no-logs --report /tmp/hyprlarp-diagnostico.json
```

Desde el repositorio sustituye `hyprlarp` por `./bin/hyprlarp`. En la interfaz están **Configuración → General → Estado del sistema → Comprobar estado / Exportar informe**.

El diagnóstico comprueba Python, herramientas obligatorias y opcionales, versiones de Quickshell/Hyprland/Qt, validez de los ajustes, disponibilidad de Wayland, servicios de usuario, errores de configuración de Hyprland y el destino IPC del shell. El informe incluye hasta 20 líneas recientes del servicio, salvo con `--no-logs` o en la vista previa.

Las herramientas ausentes de módulos opcionales se distinguen de los errores obligatorios. El comando devuelve un código distinto de cero si falta una dependencia obligatoria o su versión es demasiado antigua. Los servicios inactivos y la ausencia de una sesión gráfica se muestran como avisos: el comando también puede usarse desde una TTY.

Las comprobaciones son explícitas y tienen tiempos de espera y salidas acotados. No arrancan servicios, cambian permisos, instalan paquetes ni solicitan autenticación. El informe JSON se crea con permisos 0600; sustituye la ruta del directorio personal y valores identificados como contraseñas o tokens por marcadores. No se envía a ningún servicio externo.
