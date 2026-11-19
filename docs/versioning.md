# Versiones de HyprLarp

`VERSION`, en la raíz del paquete, es la única fuente de la versión de publicación. El shell, el backend, los diagnósticos y el greeter leen ese mismo archivo a través de `backend/version.py`. La versión inicial es `0.1.0`.

```sh
hyprlarp --version
hyprlarp-greeter --version
```

Estas consultas funcionan sin sesión gráfica, servicios activos ni Git. Las instalaciones del shell, la interfaz de inicio de sesión y el puente autónomo del greeter incluyen su propia copia de `VERSION` y del lector. Al actualizar solamente uno de esos componentes, su comando informa la versión de ese componente instalado.

La versión sigue `MAJOR.MINOR.PATCH`: incrementa PATCH para correcciones compatibles, MINOR para funciones y MAJOR para cambios incompatibles. Durante `0.x`, documenta expresamente los cambios incompatibles. Se admiten sufijos como `0.2.0-rc.1` y metadatos como `0.2.0+arch.1`.

Para preparar una publicación, actualiza únicamente `VERSION`, registra los cambios, ejecuta `python3 tools/check.py` y verifica los comandos anteriores desde una instalación aislada. El empaquetado y cualquier etiqueta Git deben usar el mismo valor; cambiar el archivo no crea etiquetas ni publica nada automáticamente.

Los campos enteros `version` de ajustes, historial, informes y manifiestos identifican sus **formatos de archivo**, por lo que conservan su numeración independiente. Los manifiestos de instalación usan `release` para la publicación y los diagnósticos incluyen `versions.HyprLarp`. La revisión de contenido del panel de rendimiento incluye `VERSION` y los archivos de ejecución; identifica tanto los cambios de publicación como los cambios del código entre dos compilaciones de la misma publicación.
