# Preferencias de uso diario

En **Configuración → General** están las opciones de **Reloj y fecha**, **Calendario** y **Avisos de batería**. Los cambios se guardan automáticamente, admiten Deshacer/Rehacer y se incluyen en perfiles y el restablecimiento de General.

El reloj permite 12 o 24 horas, segundos y cinco formatos de fecha. La barra, su módulo de calendario, el panel mensual y las horas de las notificaciones usan estas preferencias. En barras verticales la hora se distribuye en líneas. El reloj compartido se actualiza por minuto; solo usa precisión de segundos cuando esa opción está activa.

El calendario empieza en lunes o domingo y puede mostrar números ISO de semana. Las semanas ISO siempre se definen desde el lunes: en una cuadrícula que empieza en domingo, el número corresponde al lunes de esa fila. Se contemplan años bisiestos y semanas que pertenecen al año anterior o siguiente.

Los avisos de batería están activados inicialmente al **20 %** y **10 %**, y ambos umbrales son configurables. Solo avisan durante la descarga, una vez por nivel. Si el shell arranca por debajo del nivel crítico, emite un único aviso crítico. La memoria se conserva en `battery-alerts.json`, dentro del directorio de configuración, para evitar duplicados al reiniciar. Conectar el cargador o recuperar cinco puntos sobre el umbral bajo rearma los avisos. Presentación oculta los avisos y No molestar permite solo el crítico; las reglas pueden ocultar los de `hyprlarp-battery`. El estado se lee cada 30 segundos aunque no haya un módulo de batería en la barra; las vistas previas y la ventana independiente de configuración nunca envían avisos.

**Ctrl+F** enfoca el buscador de Configuración. Acepta búsquedas sin tildes y varias palabras. Las flechas seleccionan resultados, Enter abre el ajuste y Escape limpia la búsqueda. La página se desplaza al control o sección, con acceso a segundos, calendario, batería, opacidad, monitores y los ajustes existentes.

Los mensajes y pantallas de error incluyen **Copiar**, con confirmación visual. Se copia el texto del error, conservando saltos de línea y caracteres especiales.

El greeter muestra los teclados XKB configurados y un aviso explícito si Bloq Mayús está activado. Lee únicamente el estado público de los LED en `/sys/class/leds`; no abre dispositivos de entrada ni recoge pulsaciones o contraseñas. Un único proceso ligero observa los cambios mientras está abierto el greeter. Si el hardware no expone ese estado, no inventa un estado de Bloq Mayús. Con varios teclados configurados muestra sus nombres, sin atribuirles un grupo activo que el compositor no proporciona. Los errores del greeter también pueden copiarse.

La interfaz de greetd se instala aparte en `/usr/local/share/hyprlarp-greeter` y sus archivos pertenecen a root. Actualizar la shell del usuario no sustituye esos archivos. El instalador opcional es `python3 tools/install_greeter.py`; conserva una copia de seguridad y no reinicia greetd ni cierra la sesión.

Referencias técnicas: [SystemClock de Quickshell](https://quickshell.org/docs/v0.3.2/types/Quickshell/SystemClock/) y [LED de teclado en Linux](https://docs.kernel.org/leds/leds-class.html).
