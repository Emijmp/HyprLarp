# Paquete para Arch Linux y CachyOS

El paquete `hyprlarp` instala el código compartido en `/usr/share/hyprlarp`, sus
comandos en `/usr/bin`, el icono y la entrada de Configuración. El contenido es
QML, JavaScript, Python y recursos: no necesita generar un ejecutable monolítico.
La receta utiliza `arch=('any')`; la validación local se realiza en x86_64.

La instalación del paquete no modifica `hyprland.lua`, los ajustes personales,
`greetd`, PAM ni los servicios activos. No contiene hooks de activación.
El greeter se incluye como una integración opcional que se activa expresamente.

## Construir y revisar

Desde el árbol de fuentes, con Python y `base-devel` disponibles:

```sh
python3 tools/package.py prepare --output .runtime/package
python3 tools/package.py build --output .runtime/package
python3 tools/package.py verify .runtime/package/hyprlarp-0.1.0-1-any.pkg.tar.zst
```

`prepare` genera un `PKGBUILD` concreto desde `packaging/arch/PKGBUILD.in` y la
versión de `VERSION`. También genera el archivo fuente y su SHA-256: la receta
no descarga una rama cambiante ni utiliza `SKIP` para el checksum.
El nombre exacto del paquete se informa al terminar `build`; cambia con `VERSION`.
`--pkgrel 2` permite generar una segunda revisión del empaquetado de la misma
publicación, por ejemplo para validar una actualización real con pacman. No cambia
`VERSION`; la revisión habitual de una publicación nueva empieza en 1.

`build` ejecuta `makepkg` como usuario y nunca instala dependencias ni invoca sudo.
Si ya verificaste las dependencias en el entorno de trabajo, `--nodeps` permite
omitir su comprobación. `--nocheck` omite la suite de `check()`; la publicación
normal conserva las pruebas. Los modelos JavaScript y Lua requieren `nodejs` y
`lua` para esas comprobaciones.

Los artefactos quedan en el directorio elegido. La fuente comprimida normaliza
orden, propietario, permisos y timestamps; `SOURCE_DATE_EPOCH` o `--epoch` fijan
su fecha. Con el mismo contenido y el mismo epoch, el tar.gz es idéntico.
La reproducibilidad del paquete completo también depende de la configuración
de makepkg y de las versiones de su entorno de construcción.

El comando `verify` inspecciona el paquete sin extraerlo ni ejecutarlo. Comprueba
su versión, manifiesto, hashes de archivos, comandos y lista de rutas; rechaza
archivos fuera de su contenido previsto, como configuraciones globales de login.
También comprueba las dependencias y los permisos de los comandos globales.
No reemplaza la verificación de firmas de pacman ni la comprobación de SHA-256
del archivo descargado.

## Instalar y configurar cada usuario

Una vez revisado el paquete:

```sh
sudo pacman -U /ruta/hyprlarp-VERSION-1-any.pkg.tar.zst
hyprlarp setup
hyprlarp welcome
```

`setup` genera únicamente la integración del usuario, apuntando al código
compartido. Los ajustes quedan en `$XDG_CONFIG_HOME/hyprlarp`, normalmente
`~/.config/hyprlarp`; el código del paquete no se vuelve a copiar en el home.
Las primeras aperturas de `run`, `start`, `settings` y `welcome` pueden preparar
esa integración si todavía falta. `--version` no requiere configuración ni sesión.

Revisa las líneas de carga que informa `setup` antes de añadirlas a tu
`hyprland.lua`. Se mantienen los ajustes y binds existentes. La actualización
con pacman sustituye el código compartido, sin regenerar los archivos activos
de configuración del usuario.

Si existe una instalación anterior del usuario, la integración reconoce su
launcher gestionado y conserva un respaldo al apuntarlo al paquete. Un comando
ajeno en `~/.local/bin` se conserva y se informa para que puedas resolver el
orden de `PATH` conscientemente.

## Funciones opcionales

Las dependencias obligatorias son Python 3.11+, Quickshell 0.3.2+, Hyprland 0.57+,
Qt Quick/SVG/Wayland, `qt6-imageformats`, python-gobject, Pillow, libnm, systemd,
Inter, JetBrains Mono y DejaVu Sans para las anotaciones de capturas. Pillow permite extraer colores de PNG, JPEG, WebP y BMP
en el proceso de análisis aislado.
Las fuentes se incluyen como dependencias para que un sistema mínimo pueda
mostrar texto y medir correctamente los controles desde el primer inicio.
El complemento de formatos de Qt permite mostrar también los fondos WebP admitidos.
La receta declara las
herramientas adicionales como dependencias opcionales: capturas, portapapeles,
brillo, bloqueo, audio, discos y gestores externos. Instala las que
correspondan a las funciones que uses; instalar un paquete no habilita su servicio.

El greeter requiere `greetd` y `noctalia-greeter`, y se prepara por separado:

```sh
python3 /usr/share/hyprlarp/tools/install_greeter.py --dry-run
python3 /usr/share/hyprlarp/tools/install_greeter.py
```

Su instalador comprueba la autorización de administración no interactiva antes
de modificar recursos del sistema. Conserva el greeter anterior para restaurarlo.
Consulta [la guía del greeter](greeter.md) para activación, sincronización y retirada.

## Retirar

Retira primero el greeter opcional si lo activaste y quieres restaurar el anterior:

```sh
hyprlarp-greeter uninstall --dry-run
hyprlarp-greeter uninstall
hyprlarp teardown --dry-run
hyprlarp teardown
sudo pacman -R hyprlarp
```

La retirada de la integración conserva preferencias e historiales y no elimina
el código de `/usr`. Detiene el gestor de bindings del paquete solo en la sesión
verificada y los procesos de reposo que correspondan a su configuración gestionada.
Después retira las líneas de carga de HyprLarp que añadiste
a `hyprland.lua`. Pacman es quien administra los archivos globales del paquete.

Referencias verificadas: [formato PKGBUILD](https://man.archlinux.org/man/PKGBUILD.5.en),
[Quickshell en Arch](https://archlinux.org/packages/extra/x86_64/quickshell/),
[Hyprland en Arch](https://archlinux.org/packages/extra/x86_64/hyprland/).
