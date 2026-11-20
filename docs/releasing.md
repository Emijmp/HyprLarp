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

El comando `prepare` reutiliza el archivador del empaquetado para producir las
fuentes reproducibles, extrae las notas de la versión y genera `SHA256SUMS`.
La carpeta debe contener exactamente un paquete Arch de la versión actual.
`--source-only` permite preparar únicamente las fuentes para revisión, en una
carpeta distinta sin paquetes. Ninguno de estos comandos crea etiquetas, hace push
ni contacta con GitHub para publicar.

`SOURCE_DATE_EPOCH` fija las fechas del archivo fuente. Si no se proporciona se
utiliza cero; para reconstruir un artefacto usa el mismo valor registrado en la
preparación. El workflow utiliza la fecha del commit etiquetado. Los archivos fuente
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

SHA-256 permite comprobar que una descarga conserva los bytes preparados. No es
una firma del paquete ni acredita por sí sola su autoría; esta primera preparación
no incorpora claves privadas ni firma con credenciales locales.

Referencias: [crear publicaciones en borrador con GitHub CLI](https://cli.github.com/manual/gh_release_create),
[subir artefactos a una publicación](https://cli.github.com/manual/gh_release_upload) y
[permisos mínimos de GITHUB_TOKEN](https://docs.github.com/en/actions/tutorials/authenticate-with-github_token).
