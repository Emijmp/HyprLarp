# Apariencia y perfiles de rendimiento

## Temas por horario

En **Configuración → Apariencia → Tema**, activa **Cambiar tema según el horario**. Elige una paleta para el día y otra para la noche, y define sus horas locales. El shell reutiliza su reloj para seguir el horario, los cambios de día y la reanudación; el horario que cruza medianoche también funciona. La paleta **Papel Claro** está pensada para el día. Al aplicar manualmente un tema o una copia personalizada, se desactiva el horario. Al abrir el bloqueo se resuelve el mismo horario. Cuando está instalada la sincronización del greeter, un cambio efectivo de tema la activa sin añadir un sondeo periódico.

## Diseños y superficies de panel

**Distribución** permite usar paneles flotantes junto a la barra, centrados o como barra lateral de pantalla completa. La posición y el tamaño respetan la barra y los límites del monitor, incluso con escalado. **Superficie** elige el estilo estándar, vidrio translúcido o plano sin borde. El desenfoque de vidrio es opcional, se limita a la superficie del panel y requiere soporte del compositor. Alto contraste y el perfil eficiente lo desactivan. La barra conserva sus opciones independientes de posición, longitud y alineación.

La vista previa muestra muestras de barra, superficie, texto y acento para todas las paletas antes de aplicarlas. Aplicar desde una muestra usa el historial habitual de ajustes y apaga el horario automático.

## Colores del fondo

En **Apariencia → Colores del fondo**, extrae hasta seis colores de la imagen seleccionada por HyprLarp y elige uno como acento. La muestra conserva el tono original y enseña la variante legible que se aplicará. El acento se ajusta hacia claro u oscuro para alcanzar 4,5:1 sobre las superficies de las paletas incluidas. Una paleta personalizada con superficies incompatibles puede requerir activar alto contraste. El análisis se hace localmente en PNG, JPEG, WebP, BMP o SVG. Los formatos raster usan Pillow; SVG se analiza sin dependencias adicionales. La imagen raster se muestrea a tamaño pequeño; se rechazan archivos de más de 64 MiB o 24 megapíxeles. Para SVG se leen únicamente colores hexadecimales del texto, sin ejecutar ni renderizar el documento. La extracción no cambia la paleta hasta que seleccionas un color. Waypaper externo no publica su ruta actual al shell; para analizar un fondo, selecciónalo desde HyprLarp.

El análisis usa un proceso temporal con límites de memoria (384 MiB de espacio de direcciones), CPU (3 s), espera (5 s) y salida (4 KiB). El backend no importa Pillow ni mantiene la imagen decodificada. Solo se permite un trabajo simultáneo; una caché LRU de ocho resultados se invalida cuando cambia el archivo.

## Vista previa de paneles

En **Apariencia → Diseño y estilo de paneles**, cambia la distribución, la superficie y la opacidad en controles temporales. La muestra usa el fondo seleccionado y comparte las reglas de posición del panel real. **Aplicar diseño del panel** guarda los valores juntos y espera la confirmación del backend; **Descartar vista previa** recupera los valores guardados. Deshacer, Restablecer o importar otro diseño actualiza el borrador. Las modificaciones de otros ajustes conservan los cambios pendientes del panel. Si el guardado falla, el borrador sigue editable y muestra el error. El desenfoque se activa en los paneles reales cuando el compositor lo admite; la tarjeta previa representa la transparencia y muestra el indicador de desenfoque, pero no simula el blur del compositor.

## Legibilidad y accesibilidad

En **Configuración → General → Accesibilidad** puedes escalar texto hasta el 200%, establecer el tamaño mínimo de etiquetas pequeñas, activar alto contraste, controles grandes y reducir movimiento. El tamaño mínimo predeterminado es 12 px y afecta solo a las fuentes, sin aumentar los márgenes o iconos pequeños. Las vistas previas crecen con el texto y los paneles desplazan el contenido para mantener los controles accesibles. Los ajustes existentes siguen disponibles para navegación con teclado y lectores de pantalla.

## Perfiles de rendimiento

En **Configuración → General → Perfil de actividad del shell** hay tres opciones:

- **Eficiente:** alarga 2,5 veces los sondeos periódicos de sistema que están activos, desactiva transiciones y desenfoque del shell.
- **Equilibrado:** conserva los intervalos actuales.
- **Ágil:** reduce a 0,75 veces los intervalos periódicos, con un mínimo de medio segundo.

El sondeo de rendimiento del panel y la limpieza de caducidad del portapapeles conservan su intervalo. Los sondeos siguen siendo bajo demanda: recursos, red, batería, brillo y portapapeles solo se consultan cuando están habilitados o visibles. Los historiales, muestras y sondeos usan límites; no hay un bucle nuevo de métricas de fondo. Estos perfiles cambian la frecuencia de actualización, no garantizan una cantidad fija de memoria ni una mejora idéntica en todas las máquinas.

La imagen de escritorio se decodifica con dimensiones acotadas a 3840×2160 y no conserva imágenes anteriores en su caché local. La tabla de miniaturas del portapapeles conserva hasta 16 entradas y elimina las que dejan de existir. Las mediciones de sesiones repetidas ayudan a detectar crecimiento sostenido; una comprobación corta no demuestra ausencia de fugas en toda una sesión.
