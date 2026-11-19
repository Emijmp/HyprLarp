# Historial persistente de configuración

Deshacer y Rehacer conservan hasta 50 cambios de configuración después de reiniciar. Siguen disponibles únicamente con la ventana de configuración enfocada. Los cambios realizados desde otros paneles se excluyen de la pila o invalidan únicamente las claves correspondientes, para conservarlos al deshacer.

En **Configuración → Perfiles → Historial de configuración**, las últimas 30 versiones permiten ver la fecha, los ajustes diferentes y una comparación de valores. **Restaurar esta versión** valida el contenido y lo aplica como una nueva edición, que también se puede deshacer.

Las versiones excluyen los estados temporales de No molestar y pausa del portapapeles. Los diseños de pantallas se guardan por separado y no se restauran desde este historial. Una imagen o carpeta eliminada puede impedir restaurar una versión que todavía la referencia; la configuración actual permanece intacta.

El historial vive en `settings-history.json`, dentro del directorio de ajustes, con permisos privados y reemplazo atómico. Conserva una huella de la configuración a la que corresponden sus pilas. Si `settings.json` cambia externamente, las pilas que ya no coinciden se descartan y las versiones permanecen consultables. Un historial corrupto no impide cargar los ajustes.

El formato actual del historial es la **versión 2**. Al abrir un historial de versión 1 se completan las preferencias conocidas que se añadieron posteriormente: accesibilidad, temas por horario, diseño y estilo del panel, desenfoque, modo de rendimiento y el atajo de captura estática. Se conservan los valores existentes, identificadores, fechas y nombres de las versiones. El atajo nuevo queda sin asignar si su combinación ya está ocupada.

La migración se realiza en memoria: abrir el shell o consultar el historial no reescribe el archivo antiguo. La siguiente edición guarda el formato actualizado de forma atómica. Deshacer y Rehacer siguen disponibles si la huella anterior coincide después de añadir únicamente los valores iniciales registrados; un valor nuevo modificado externamente invalida esas pilas. Los formatos futuros, los campos desconocidos y los datos inválidos se rechazan sin modificar los archivos originales.

El límite total es 6 MiB; los datos más antiguos se retiran primero si se alcanza. Guardar valores idénticos no escribe archivos ni crea versiones. Un fallo al escribir el historial conserva los ajustes que ya se guardaron y registra el motivo en el aviso del almacén. No hay temporizadores ni procesos dedicados a esta función.
