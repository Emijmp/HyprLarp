# Optimización verificada · 19 de noviembre de 2026

Los cambios conservan funciones, apariencia, perfiles y preferencias. No seleccionan
el perfil Eficiente ni reducen la frecuencia de actualización de los controles.
La comparación parte de una copia completa del proyecto con el asistente de primera
ejecución y el versionado unificado ya presentes.

## Trabajo eliminado

- La batería obtiene sus atributos de una lectura agrupada y utiliza archivos
  individuales como alternativa. Cada muestra sigue leyendo datos actuales.
- Guardar tema, fuente u opacidad ya no reinicia observadores de hardware, programa
  el filtro nocturno ni despierta el sondeo de dispositivos. Los cambios relevantes,
  incluidos Deshacer, Rehacer y perfiles, conservan sus efectos.
- Se elimina una lectura de batería duplicada al arrancar y una lectura innecesaria
  en la ventana independiente de configuración. El IPC usa JSON compacto.
- La interfaz conserva su objeto de ajustes cuando la respuesta del backend coincide
  con los valores que ya mostró. Los cambios derivados del backend siguen aplicándose.
- Guardar el historial reutiliza sus instantáneas internas inmutables. Las nuevas
  instantáneas y las pilas conservan su aislamiento y la escritura sigue siendo atómica.
- Los iconos SVG reutilizan el último tinte de cada icono en una caché compartida
  acotada. Los colores visitados no se acumulan. El generador conserva esta mejora.
- La corrección de contraste convierte la luminancia de cada superficie una vez.
  El índice de fallos y las métricas de barra evitan búsquedas y cálculos ajenos al
  módulo que se muestra.
- Resolver un único icono pendiente comprueba candidatos concretos y conserva herencia,
  SVG/PNG/XPM y extensiones con mayúsculas. Los lotes mantienen el recorrido conjunto.
- El launcher conserva solo los mejores 41 candidatos para producir 40 resultados
  y el indicador de truncamiento. El completado de rutas se detiene al alcanzar ese
  mismo límite y mantiene el orden anterior.
- Después de confirmar el arranque, el supervisor espera un aviso de salida del
  renderizador en vez de repetir esperas con timeout. Las solicitudes de recuperación
  siguen despertándolo y la terminación conserva sus límites aunque Qt ignore SIGTERM.

## Medidas de operaciones concretas

Son microbenchmarks locales: no representan la reducción de CPU del shell completo.
Las cifras de memoria de Python corresponden a asignaciones temporales trazadas,
no al RSS del escritorio.

| Operación | Antes | Después |
| --- | ---: | ---: |
| Aperturas de atributos por muestra de batería | 26 | 7 |
| Lectura de batería, mediana de 7 rondas de 100 muestras | 1,208 ms | 0,551 ms |
| Resolver un icono ausente en 2120 carpetas, mediana de 7 intentos | 336,7 ms | 64,5 ms |
| Consulta con 5000 coincidencias, mediana de 60 intentos | 3,34 ms | 2,18 ms |
| Pico temporal de esa consulta | 337 775 bytes | 12 212 bytes |
| Preparar historial con 30 versiones y 40 cambios, sin escritura a disco | 2,016 ms | 0,889 ms |
| Pico temporal de esa preparación | 568 811 bytes | 351 130 bytes |
| 200 correcciones de contraste en Qt/QML, mediana de 3 rondas | 1152 ms | 172 ms |
| 3000 solicitudes idénticas del logo en Qt/QML | 349 ms | Menos de 1 ms |
| Evento IPC de ajustes iniciales | 3583 bytes | 3286 bytes |

Se verificó equivalencia con 2000 combinaciones de telemetría, 2000 correcciones
de contraste y 402 URI de iconos. Las pruebas comprueban además orden y ranking,
cancelación, límites de caché, herencia de iconos, atomicidad del historial,
respuestas de guardado y reactividad de la interfaz.

## Comprobación del shell completo

Se alternaron los paquetes anterior y nuevo, invirtiendo el orden en la segunda
ronda. Cada muestra duró 8 segundos después de 3 segundos de calentamiento, con
los mismos ajustes iniciales en una vista previa Qt offscreen/software aislada.
Estas son medianas de dos ejecuciones; no representan todas las sesiones Wayland.

| Panel | PSS anterior | PSS nuevo | Ajustes recibidos, anterior | Ajustes recibidos, nuevo |
| --- | ---: | ---: | ---: | ---: |
| Cerrado | 84,29 MiB | 81,66 MiB | 250,8 ms | 209,9 ms |
| Control | 91,21 MiB | 88,79 MiB | 244,9 ms | 215,5 ms |
| Launcher | 96,17 MiB | 98,89 MiB | 258,5 ms | 211,7 ms |

El launcher conserva algo más de memoria en estas muestras. La mejora de memoria
demostrada en búsquedas e historial corresponde a sus picos temporales; no se afirma
que todos los paneles reduzcan su memoria residente. Recibir los ajustes tampoco
equivale a mostrar el primer fotograma. La carga de componentes del launcher varió
entre ejecuciones y no permite atribuir una mejora estable con esta muestra.

En reposo, ambas vistas previas registraron 0,00 % dentro de la resolución de los
contadores: con ticks de CPU de 10 ms y muestras tan cortas, ese resultado no prueba
consumo absoluto cero ni permite sostener una reducción global de CPU.

Un ejercicio adicional de 20,55 segundos abrió y cerró 50 paneles, alternando cinco
paneles y cinco tintes. Después del calentamiento, RSS se mantuvo entre 154,22 y
154,85 MiB y PSS entre 100,57 y 101,13 MiB. Las cachés conservaron 27 iconos y tres
recursos de identidad, con procesos e hilos constantes y sin errores de interfaz.
Esto comprueba estabilidad de ese ejercicio corto, no de una sesión prolongada.

En una fixture controlada de supervisor, cuatro segundos de reposo instrumentados
con `strace` pasaron de 120 llamadas a `clock_nanosleep` y 128 a `wait4` en el hilo
principal a ninguna de esas llamadas periódicas. Se añade un hilo bloqueante y
aproximadamente 64 KiB de RSS en esa fixture. Las pruebas incluyen recuperación,
órdenes sucesivas y renderizadores que ignoran SIGTERM.

La verificación completa aprobó 490 pruebas y la comprobación de todos los paneles,
incluido el asistente de primera ejecución y su navegación con texto ampliado.

Los registros detallados de esta ejecución están en `.runtime/full-optimization/`;
no forman parte del paquete ni se publican en Git.
