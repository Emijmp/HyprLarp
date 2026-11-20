# Cambios de HyprLarp

## [0.1.1] - 2026-11-19

- Las pruebas del panel de rendimiento esperan la confirmación de arranque del
  backend antes de cargar informes de ejemplo, evitando que el historial inicial
  los reemplace durante la comprobación. Se verifican también arranques retrasados.
- Las comprobaciones nativas de Lua, espacios y atajos usan un runtime temporal
  propio; los workflows preparan `XDG_RUNTIME_DIR` para sus usuarios de pruebas.

## [0.1.0] - 2026-11-19

- Shell modular para Hyprland: barra, launcher, notificaciones, portapapeles,
  multimedia, conexiones, energía, capturas y configuración visual de monitores.
- Capturas de región estáticas y dinámicas, editor de capturas y atajos configurables.
- Temas por contexto, estilos y diseños de panel, vistas previas y opciones de
  accesibilidad, legibilidad y rendimiento.
- Identidad HyprLarp en bloqueo e inicio de sesión; integración opcional y reversible
  con greetd, sincronizada con el fondo y el tema del shell.
- Instalación y actualización con respaldo, conservación de ajustes y binds activos,
  historial persistente y recuperación ante fallos de componentes y del shell.
- Asistente de primera ejecución y versión unificada para shell, backend y greeter.
- Optimizaciones verificadas de batería, iconos, contraste, búsquedas, historial,
  sincronización de ajustes y espera del supervisor.
- Paquete para Arch/CachyOS, comprobaciones de distribución y preparación automática
  de publicaciones en borrador con archivo fuente y sumas SHA-256.
