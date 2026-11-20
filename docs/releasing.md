# Preparar una publicación

La publicación se identifica por el valor de `VERSION` y una etiqueta `vVERSION`.
`CHANGELOG.md` debe contener una única sección de esa versión, con fecha válida y
una descripción de los cambios. Los números de formato de ajustes, historial y
manifiestos siguen siendo independientes de la versión de publicación.

## Revisión local

```sh
python3 tools/release.py check --tag "v$(cat VERSION)"
python3 tools/check.py
python3 tools/package.py build --output .runtime/release
python3 tools/package.py verify .runtime/release/hyprlarp-*.pkg.tar.zst
python3 tools/release.py prepare --tag "v$(cat VERSION)" --output .runtime/release
python3 tools/release.py verify .runtime/release
```

El comando `prepare` conserva el archivo fuente que acompaña al `PKGBUILD` del
empaquetado, comprueba su nombre y SHA-256 y contrasta su contenido con el código
actual antes de generar las notas y `SHA256SUMS`. Si las fuentes han cambiado,
exige reconstruir el paquete. Así no recompresa las fuentes con otra versión de
Python o zlib ni altera la suma de la receta. Cuando no hay una receta preparada,
utiliza el archivador del empaquetado para producir las fuentes reproducibles.
La carpeta debe contener exactamente un paquete Arch de la versión actual.
`--source-only` permite preparar únicamente las fuentes para revisión, en una
carpeta distinta sin paquetes. Ninguno de estos comandos crea etiquetas, hace push
ni contacta con GitHub para publicar.

`SOURCE_DATE_EPOCH` fija las fechas al crear el archivo fuente. Si no se proporciona
se utiliza cero; al reutilizar unas fuentes preparadas se conserva su fecha original.
Para reconstruir un artefacto usa el mismo valor registrado en la preparación.
El workflow utiliza la fecha del commit etiquetado. Los archivos fuente
se seleccionan mediante la misma lista permitida que usa `tools/package.py` y no
incluyen el estado de ejecución, cachés, copias locales ni configuración privada.

La [guía de empaquetado](packaging.md) describe las dependencias, la compilación y
la integración opcional del greeter. La comprobación local de paquete con
`--nodeps` omite la comprobación de dependencias de `makepkg`; no sustituye una
instalación en un sistema limpio.

## Automatización en GitHub

`.github/workflows/release.yml` se ejecuta al recibir una etiqueta `v*` o al
seleccionar manualmente una etiqueta existente. La comprobación estricta exige:

- `VERSION`, etiqueta y sección de cambios coincidentes.
- Etiqueta existente y apuntando al mismo commit que se está construyendo.
- Árbol de trabajo limpio, incluidos archivos nuevos no ignorados.
- Pruebas de lógica e interfaz aprobadas en un contenedor Arch como usuario sin
  privilegios, construcción del paquete y verificación de su contenido.

Se conservan los siguientes artefactos durante 14 días y se adjuntan al borrador:

- `hyprlarp-VERSION.tar.gz`: fuentes reproducibles.
- `hyprlarp-PKGVER-1-any.pkg.tar.zst`: paquete para Arch/CachyOS.
- `PKGBUILD`: receta con la suma del archivo fuente utilizado.
- `RELEASE_NOTES.md` y `SHA256SUMS`.

El job de construcción tiene permiso de lectura. Un segundo job recibe los
artefactos, comprueba sus sumas y usa el `GITHUB_TOKEN` con `contents: write` para
crear una publicación **en borrador**. Si se repite la ejecución puede actualizar
ese borrador; rechaza modificar una publicación que ya sea pública. Las acciones
se fijan por SHA de commit y el checkout no conserva credenciales de Git.

Tras revisar los artefactos y los resultados de las pruebas de distribución y
estabilidad, la publicación del borrador se realiza desde GitHub. La preparación
no crea una etiqueta remota automáticamente: el mantenedor decide qué commit
etiquetar y enviar. La ejecución de un workflow en GitHub requiere que estos archivos
ya estén en el repositorio remoto.

Si una etiqueta existente falló por la preparación del entorno de CI, publica la
corrección del workflow en `main` y ejecuta **Actions → Preparar publicación → Run
workflow**, seleccionando la rama `main` e indicando esa etiqueta, por ejemplo
`v0.1.0`. El workflow actualizado prepara un runtime privado y descarga las fuentes
de la etiqueta original. Así puede reconstruirse esa publicación sin mover la
etiqueta ni cambiar sus fuentes. Reejecutar el run anterior utiliza el workflow
anterior; no incorpora la corrección de `main`.

Si el arreglo modifica las fuentes o sus pruebas, prepara una nueva versión en
`VERSION` y `CHANGELOG.md` y publica su nueva etiqueta. Por ejemplo, los cambios
posteriores a `v0.1.0` se publican como `v0.1.1`. Reconstruir `v0.1.0` sigue usando
sus pruebas anteriores; el entorno actualizado no incorpora cambios de fuentes.

SHA-256 permite comprobar que una descarga conserva los bytes preparados. No es
una firma del paquete ni acredita por sí sola su autoría; esta primera preparación
no incorpora claves privadas ni firma con credenciales locales.

Referencias: [crear publicaciones en borrador con GitHub CLI](https://cli.github.com/manual/gh_release_create),
[subir artefactos a una publicación](https://cli.github.com/manual/gh_release_upload) y
[permisos mínimos de GITHUB_TOKEN](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).
Para volver a construir, consulta [ejecución manual](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/manually-run-a-workflow)
y [comportamiento de las reejecuciones](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/re-run-workflows-and-jobs).
