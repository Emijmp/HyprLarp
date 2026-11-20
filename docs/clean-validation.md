# Validación del paquete en un sistema limpio

`tools/clean_check.py` instala el paquete real con pacman, configura un usuario,
actualiza a otra revisión, ejecuta las comprobaciones y retira la instalación.
No utiliza el home, la sesión gráfica, los dispositivos ni los servicios del anfitrión.

## Entorno local sin sudo

Se necesita bubblewrap con espacios de nombres de usuario habilitados y una raíz
privada de Arch ya preparada con las dependencias de `tools/package.py` y las
herramientas de pruebas: Node, Lua, ImageMagick y D-Bus. La raíz debe ser legible
para el usuario que ejecuta la comprobación. El helper no descarga software ni
instala dependencias en el sistema anfitrión.

```sh
python3 tools/package.py build --output .runtime/base
python3 tools/package.py build --output .runtime/upgrade --pkgrel 2 --nocheck
python3 tools/clean_check.py \
  --rootfs /ruta/a/arch-rootfs \
  --package .runtime/base/hyprlarp-0.1.0-1-any.pkg.tar.zst \
  --upgrade-package .runtime/upgrade/hyprlarp-0.1.0-2-any.pkg.tar.zst \
  --output .runtime/clean-check
```

Por defecto se copia esa raíz a un área desechable. `--use-rootfs-workspace`
permite utilizar y modificar directamente una raíz privada de pruebas, por ejemplo
si contiene directorios de servicios que no puede leer el usuario al copiarla.
Esta opción es explícita; se rechazan `/`, el home, los directorios superiores del
proyecto y las salidas que se solapan con la raíz. Nunca se recurre a sudo o a una
instalación en el anfitrión si el aislamiento falla.

Las fases de pacman usan UID 0 dentro del espacio de nombres. Las pruebas de usuario
usan UID 1000 y ven `/usr` y el resto de la raíz como solo lectura; únicamente su home
de pruebas es escribible. Si el bootstrap no tiene una identidad para ese UID, se
crea una cuenta bloqueada dentro de la raíz privada. No se crean contraseñas.
No hay red durante el ensayo ni acceso a sockets o dispositivos de la sesión real.

## Comprobaciones

1. Verifica rutas, permisos, hashes, versión y dependencias de ambos paquetes.
2. Instala el primero con pacman respetando sus dependencias. Una raíz que ya tenga
   HyprLarp instalado se rechaza para conservar instalaciones ajenas al ensayo.
3. Comprueba las versiones del shell, backend y greeter; el plan de `setup` no debe
   escribir nada. El setup real crea solo la integración privada del usuario y
   registra su primera ejecución, sin copiar el programa a su home.
4. Guarda preferencias, historial, un atajo pendiente, bindings activos modificados
   y un archivo personal; toma hashes, modos e inodos. Repetir setup debe conservarlos.
5. Actualiza con pacman al segundo paquete. `--upgrade-package` exige un aumento real
   de versión o `pkgrel`; sin ese argumento se identifica expresamente una reinstalación.
6. Comprueba los archivos conservados y ejecuta la suite de backend y la interfaz
   instaladas, con sus propios ajustes temporales. `--skip-backend-tests` es una
   excepción explícita para diagnóstico, no la validación completa.
7. Retira la integración y el paquete. Conserva preferencias, historial, bindings
   modificados y archivos personales. La lista de otros paquetes debe quedar idéntica.

También se comprueba que las operaciones no hayan cambiado los archivos de greetd.
El informe no afirma que se haya iniciado sesión mediante PAM.

## Informes y CI

`report.json` registra fases, versiones, duración, hashes, transición de actualización
y paquetes del entorno. Cada fase conserva su registro, incluso ante un timeout.
`--rootfs-id` y `--rootfs-sha256` permiten registrar la procedencia del bootstrap;
el hash identifica el archivo aprovisionado, no la raíz después de instalar dependencias.
`--keep-workspace` conserva el home de prueba para inspección; normalmente se elimina.

El workflow de comprobaciones construye dos paquetes en Arch y los prueba en otro
contenedor nuevo, con dependencias de ejecución y herramientas de pruebas, sin la
cadena de compilación. Docker se ejecuta sin red para el ensayo y monta las fuentes
como solo lectura. `--container` solo se admite explícitamente como UID 0 dentro de
un contenedor identificado; existe para CI donde bubblewrap anidado no está permitido.

Un sistema limpio de software no sustituye las pruebas de suspensión, autenticación,
conectores o escalas físicas. Véanse [revisión de experiencia](release-ux.md),
[estabilidad](stability.md) y [validación real](validation.md).
