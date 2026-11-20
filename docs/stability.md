# Prueba prolongada de estabilidad

```sh
python3 tools/soak.py --duration 7200 --output .runtime/soak-2h
```

La prueba prepara una copia fija del código y abre Quickshell con Qt offscreen/software,
un HOME, ajustes, caché y runtime temporales. Recorre 31 escenas: paneles, páginas de
configuración y el asistente; alterna temas, estilos, diseños y texto ampliado.
Cada 30 minutos reinicia únicamente su backend aislado, verificando PID, identidad
y parentesco antes de enviar la señal. No controla la sesión real.

`result.json` se actualiza durante la ejecución. `samples.jsonl` conserva CPU, RSS,
PSS y procesos; `quickshell.log` contiene los mensajes de interfaz. Un componente
bloqueado, una desconexión sostenida, un cierre inesperado o un error QML hacen fallar
la ejecución. Tras dos minutos de calentamiento, el crecimiento de RSS entre ventanas
inicial y final tiene un presupuesto predeterminado de 64 MiB. Se informa también el
pico, porque una mediana estable no descarta picos transitorios.

Se puede ajustar `--interval`, `--warmup`, `--cycle-ms`, `--max-growth-mib` y
`--restart-every`; este último acepta 0 para desactivar las interrupciones controladas.
La duración admite hasta un día. Los datos tienen la versión y la revisión exacta
de la copia probada. Una ejecución corta prueba el mecanismo, no sustituye dos horas.
SIGINT o SIGTERM guardan un resultado `interrupted` y cierran los procesos propios.

El workflow `stability.yml` ejecuta dos horas semanalmente y permite lanzarlo manualmente.
Conserva el informe, las muestras y el registro durante 14 días. No publica el directorio
de ajustes ni los archivos del HOME temporal.

El resultado distingue expresamente las comprobaciones no ejecutadas: PAM, suspensión
física y desconexión física de monitores. La prueba offscreen no cubre GPU, dispositivos,
bloqueo ni credenciales. Véanse [validación real](validation.md) y
[revisión de experiencia](release-ux.md).
