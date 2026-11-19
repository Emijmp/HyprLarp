# Búsqueda unificada

Abre el launcher con su atajo o el módulo Aplicaciones. **Todo** reúne aplicaciones, ventanas, acciones y archivos; Favoritas y Recientes conservan los accesos de aplicaciones existentes. Los filtros Ventanas, Archivos y Acciones permiten limitar los resultados.

| Consulta | Resultado |
| --- | --- |
| `firefox` | Aplicaciones y ventanas que coinciden, además de archivos y acciones compatibles. |
| `= 2*(3+4)` | Calcula el resultado; Enter lo copia al portapapeles en la sesión real. |
| `= sqrt(81)+2` | Funciones: sqrt, abs, round, sin, cos, tan, log y log10; constantes pi y e. |
| `> configuración` | Acciones del catálogo, incluidas páginas de configuración y controles del escritorio. |
| `? informe` | Busca nombres de archivos y carpetas del directorio personal. |
| `~/Documentos/` o `/ruta/prefijo` | Completa entradas de una carpeta concreta. |

Las flechas seleccionan y Enter abre o ejecuta el resultado. Las ventanas se activan mediante el modelo nativo de Wayland; no hay consultas periódicas de ventanas. Las acciones de sesión conservan las confirmaciones de su menú existente.

La calculadora interpreta un árbol aritmético: no usa eval, comandos, acceso a atributos ni importaciones. Hay límites de longitud, complejidad, exponentes y resultados.

Los archivos se buscan únicamente mientras el launcher está abierto. La búsqueda por nombre recorre hasta cuatro niveles del directorio personal y 5.000 entradas, sin seguir enlaces simbólicos ni entrar en directorios ocultos o cachés de desarrollo conocidas. Devuelve hasta 40 coincidencias; la interfaz indica cuando hay resultados limitados. Una ruta explícita permite consultar otra carpeta. La caché se reutiliza durante 30 segundos y se libera al cerrar el panel. No existe un indexador permanente.

Escribir agrupa peticiones durante 130 ms. Las respuestas antiguas se descartan mediante un identificador de consulta. Los iconos de respaldo se resuelven por lotes solo para los resultados visibles; las listas reutilizan sus filas.

La vista previa usa ajustes separados. Permite revisar archivos, aplicaciones, acciones y cálculos; no activa ventanas reales ni copia el resultado de la calculadora al portapapeles.

Referencia: [ToplevelManager](https://quickshell.org/docs/v0.3.2/types/Quickshell.Wayland/ToplevelManager/) y [activación de ventanas](https://quickshell.org/docs/v0.3.2/types/Quickshell.Wayland/Toplevel/).
