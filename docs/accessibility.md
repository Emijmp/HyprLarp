# Accesibilidad

En **Configuración → General → Accesibilidad** se puede ampliar el texto del 100 al 200%, fijar el mínimo de las etiquetas pequeñas entre 10 y 18 px, activar alto contraste, aumentar los controles a un mínimo de 44 píxeles lógicos y reducir el movimiento. El mínimo predeterminado es 12 px. Las opciones admiten Deshacer/Rehacer, perfiles y restablecimiento de General. Actualizar el shell conserva las preferencias y el historial anteriores.

La escala afecta a paneles, ajustes, notificaciones, OSD y barra. La barra aumenta su grosor cuando el contenido lo necesita. Las opciones se distribuyen en varias líneas y los paneles desplazan el control enfocado a la vista. El alto contraste usa superficies opacas y texto, acento y texto secundario con contraste mínimo 7:1 sobre sus fondos; desactivarlo recupera la paleta elegida. No modifica esa paleta.

## Uso con teclado

| Acción | Teclas |
| --- | --- |
| Recorrer controles | Tab / Mayús+Tab |
| Activar botones y opciones | Enter / Espacio |
| Ajustar deslizadores y selecciones | Flechas |
| Cerrar el panel | Escape |
| Buscar una opción de configuración | Ctrl+F en ajustes |
| Abrir módulos, espacios y bandeja | Escribir `> barra` en el launcher y pulsar Enter |
| Abrir el menú de un icono de la bandeja | Mayús+F10 o tecla Menú |

Los controles muestran un contorno de foco. La selección de fondos, colores y resultados del launcher admite teclado. Los monitores también se colocan mediante sus campos X/Y. En el editor de capturas, las flechas mueven el cursor un píxel, Mayús+flechas diez, Espacio comienza una selección y Enter la termina; Escape cancela el trazo. Los atajos personalizados de Hyprland se conservan.

## Lectores de pantalla

El shell y el greeter activan la integración de Qt con AT-SPI. Los controles exponen nombres, valores, estados y acciones; los errores y avisos usan anuncios de accesibilidad. Los campos de contraseña conservan el enmascaramiento y una descripción de su propósito. La prueba nativa verifica el árbol de AT-SPI y la activación remota de un botón y un deslizador.

Se necesita un lector de pantalla instalado y ejecutándose, como Orca. HyprLarp no instala ni activa automáticamente ese servicio. La integración AT-SPI del shell no sustituye las funciones de accesibilidad del compositor ni de otras aplicaciones. No se afirma una certificación WCAG ni una prueba integral de todos los lectores.

## Inicio de sesión y bloqueo

El greeter recibe la escala, los controles grandes y la reducción de movimiento en sus metadatos limitados; su paleta sincronizada incluye el alto contraste. Estos cambios requieren tener instalada la versión actualizada del greeter mediante `tools/install_greeter.py`. La previsualización de Apariencia usa esas mismas opciones y el formulario de inicio permite desplazamiento con teclado.

El bloqueo nativo de hyprlock sigue la escala, el contraste y la reducción de movimiento. La ampliación se limita al espacio disponible para mantener el formulario dentro de la pantalla. Hyprlock dibuja su propia interfaz y no publica el árbol AT-SPI de Qt; la compatibilidad del lector indicada arriba corresponde al shell y al greeter.

Referencias: [accesibilidad en Qt Quick](https://doc.qt.io/qt-6/accessible-qtquick.html), [propiedades y acciones Accessible](https://doc.qt.io/qt-6/qml-qtquick-accessible.html).
