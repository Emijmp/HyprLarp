# Desarrollo y CI

Se requiere Python 3.11 o superior. El greeter usa [tomllib, incorporado en Python 3.11](https://docs.python.org/3/library/tomllib.html). Node y Lua se utilizan para comprobar los modelos y la integración; Quickshell y Qt son necesarios para la interfaz.

```sh
python3 tools/check.py                 # comprobación completa
python3 tools/check.py --backend-only  # lógica, modelos e instalación aislada
python3 tools/check.py --ui-only       # interfaz y vista previa
```

Las pruebas añaden casos de persistencia después de reiniciar, archivos corruptos y escrituras fallidas, restauración y límites del historial, cálculo aritmético, cancelación de búsquedas, nombres con espacios/Unicode y diagnósticos. La comprobación visual prueba el launcher real contra su backend temporal, además de los paneles y páginas existentes. No ejecuta operaciones sobre dispositivos físicos.

El workflow `.github/workflows/check.yml` se ejecuta en push, pull request y bajo demanda. Comprueba el backend en Python 3.11 y 3.14 y ejecuta la suite completa con Qt/Quickshell en Arch como un usuario de prueba sin privilegios. Solo concede lectura del repositorio; los jobs tienen límite de tiempo y cancelan ejecuciones anteriores de la misma rama. Los artefactos contienen registros, versiones y una muestra offscreen; no representan una medición de la GPU del escritorio real.

El mismo workflow construye dos revisiones del [paquete Arch](packaging.md) y realiza
una [instalación, actualización y retirada en un contenedor nuevo](clean-validation.md).
Las acciones se fijan por SHA y el checkout no conserva credenciales. El workflow
[de estabilidad](stability.md) ejecuta dos horas semanalmente o bajo demanda;
el de [publicación](releasing.md) prepara artefactos y un borrador revisable al recibir
una etiqueta que coincida con `VERSION` y `CHANGELOG.md`.

Los jobs Arch preparan un `XDG_RUNTIME_DIR` privado, de modo 0700 y propiedad del
usuario de pruebas. Hyprland lo requiere incluso con `--verify-config`, aunque no
se inicie una sesión gráfica. Las pruebas nativas de Lua, espacios y atajos usan
además su propio directorio temporal, por lo que también funcionan al ejecutar
unittest directamente sin heredar el runtime del escritorio.

## Organización del backend

| Módulo | Responsabilidad |
| --- | --- |
| `service.py` | Protocolo JSON-lines, coordinación y compatibilidad de las importaciones anteriores. |
| `settings_schema.py` | Valores iniciales, validación y migraciones. |
| `settings_store.py` | Guardado, Deshacer/Rehacer y aplicación de cambios. |
| `persistence.py` | Reemplazo atómico de archivos privados. |
| `revisions.py` | Versiones comparables y persistencia del historial. |
| `actions.py` | Mutaciones explícitas del sistema. |
| `metrics.py` | Lecturas de recursos y planificación según consumidores visibles. |
| `diagnostics.py` | Informes de estado bajo demanda. |
| `launcher.py` | Cálculos y búsquedas de archivos acotadas y cancelables. |

Las interfaces existentes de `backend.service` siguen disponibles para los módulos y pruebas anteriores. Los módulos nuevos se incluyen automáticamente en la instalación gestionada.

`backend/performance.py` mide los procesos principales del shell bajo demanda y conserva informes acotados. Las pruebas verifican unidades, caché de PSS, reutilización de PID, exclusión de aplicaciones, persistencia, cancelación, contexto de comparación y el flujo QML con el backend real (`performance-check.qml`). El fixture acepta `HYPRLARP_PERFORMANCE_CAPTURE=/ruta/prefijo` para guardar vistas del panel y del historial con ajustes temporales; `HYPRLARP_PERFORMANCE_HOLD=1` lo mantiene abierto.

La [accesibilidad](accessibility.md) tiene pruebas de persistencia, contraste y navegación con eventos reales de teclado de Qt (`tools/AccessibilityChecks.qml`). El fixture `accessibility-check.qml` permite ejecutarlas aparte; `HYPRLARP_A11Y_HOLD=1` mantiene la ventana abierta para inspeccionar AT-SPI. Las comprobaciones normales no requieren Orca ni una sesión física.

El [aislamiento y la recuperación](recovery.md) se reparten entre `faults.py` (registro y límites por componente), `GuardedLoader.qml` (cargas QML), `supervisor.py` (proceso y cambio de modo), `recovery.py` (servicio y salud) y `recovery_tools.py` (helpers independientes). La suite introduce errores QML reales, excepciones del backend y salidas repetidas de un renderer simulado; comprueba que un componente sano y una aplicación independiente siguen funcionando. Las pruebas nativas adicionales deben usar un compositor anidado y ajustes temporales, sin bloquear ni cerrar la sesión real.

Referencia: [pruebas de Python con GitHub Actions](https://docs.github.com/en/actions/tutorials/build-and-test-code/python).
