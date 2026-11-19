# Greeter de HyprLarp con greetd

**HyprLarp Greeter** tiene una interfaz propia en Quickshell, con dos diseños: barra lateral de acceso o tarjeta centrada sobre el fondo. Ambos usan el logo del gato con sombrero junto al nombre HyprLarp, controles planos y la paleta, fuente y redondez de la shell, con soporte para los temas incluidos y el personalizado. Los mensajes de error usan la ilustración del gato con interrogante.

En **Configuración → Apariencia → Pantalla de inicio de sesión**, elige **Barra lateral** o **Centrado**. La elección se guarda automáticamente, admite deshacer y se incluye en los perfiles. El diseño lateral es el valor inicial. El fondo y los colores siguen sincronizados en cualquiera de los dos diseños.

Debajo del selector aparece una miniatura de la misma interfaz del greeter. Cambia en vivo con el diseño, la paleta, la tipografía, la redondez y el fondo del escritorio. Respeta las proporciones de la pantalla y muestra un formulario ilustrativo, sin autenticación ni acciones de energía. Con Waypaper usa el último fondo sincronizado; los fondos animados se muestran como imagen fija.

La interfaz autentica con el módulo nativo `Quickshell.Services.Greetd`. Reutiliza el compositor y el helper de sincronización de Noctalia Greeter. Admite errores de contraseña, cancelación y solicitudes adicionales de PAM; la contraseña no se guarda ni se escribe en registros.

Requiere Python **3.11+**, greetd, Noctalia Greeter **1.5+** con `secure-sync-v1`, Polkit y una sesión local activa gestionada por logind. En CachyOS, el greeter se distribuye como `noctalia-greeter`. No necesita ejecutar Noctalia Shell.

```sh
python3 tools/install_greeter.py --dry-run
python3 tools/install_greeter.py
```

El instalador pide autenticación del sistema una vez. Instala la interfaz en `/usr/local/share/hyprlarp-greeter`, prepara `/usr/local/bin/hyprlarp-greeter-session` para greetd, habilita la autorización oficial de Noctalia limitada a sincronizar apariencia para tu usuario e instala un servicio y un observador de systemd de usuario. El exportador se copia aparte a `~/.local/share/hyprlarp-greeter`; sigue funcionando aunque muevas el checkout. Las rutas de usuario respetan `XDG_DATA_HOME`, `XDG_CONFIG_HOME` y `XDG_STATE_HOME`.

El lanzador establece `NOCTALIA_GREETER_BIN=/usr/local/libexec/hyprlarp-greeter-ui`, que es la opción que lee el script nativo antes de iniciar el compositor. `GREETER_BIN` por sí sola se sobrescribe en ese script y abriría la interfaz original de Noctalia. La validación cubre esta cadena completa de arranque además de probar la interfaz y la autenticación con un servicio simulado.

Los ajustes anteriores de greetd y el estado completo del greeter se respaldan en `/var/backups/hyprlarp-greeter/FECHA/`. Se conservan la configuración de autenticación, la selección de sesión, el teclado y las pantallas. El instalador no reinicia greetd ni cierra tu escritorio: verás el resultado al volver al inicio de sesión.

## Sincronización automática

`hyprlarp-greeter-sync.path` observa `hyprlarp/settings.json` y `waypaper/config.ini`. Cada cambio inicia un trabajo corto con un segundo de espera para agrupar guardados. Solo aplica una actualización cuando cambian el fondo, la apariencia o el diseño; cambios de volumen, barra u otros ajustes no vuelven a copiar la imagen. La interfaz observa el estado sincronizado y actualiza sus colores y diseño en vivo, sin reiniciarse. No hay sondeo permanente.

El diseño se comparte por separado en `/var/lib/hyprlarp-greeter/preferences/layout.json`. El instalador prepara el directorio para tu usuario y el grupo del greeter; este archivo solo admite `sidebar` o `centered`. Cambiar el diseño no requiere permisos de administrador ni vuelve a copiar el fondo. El helper oficial de apariencia mantiene su esquema y sus permisos originales.

El fondo se copia bajo `/var/lib/noctalia-greeter/` y se referencia desde `sync.toml`, así que no hace falta dar acceso al greeter a tu carpeta personal. Si eliges el fondo liso del tema, se elimina la imagen anterior del estado sincronizado. Con Waypaper se usa su archivo actual y su modo de ajuste. Los vídeos y GIF se convierten en una imagen fija con FFmpeg; los SVG usan ImageMagick.

```sh
hyprlarp-greeter sync --force
hyprlarp-greeter status
hyprlarp-greeter preview
systemctl --user status hyprlarp-greeter-sync.path
journalctl --user -u hyprlarp-greeter-sync.service -n 30
```

Para exportar un resultado revisable sin escribir en el greeter:

```sh
./bin/hyprlarp-greeter export --output /tmp/hyprlarp-greeter-export
```

El helper oficial valida el contenido y solo mezcla la apariencia. No se conceden permisos para ejecutar comandos arbitrarios, cambiar la sesión ni modificar PAM. Su autorización se puede retirar con `sudo noctalia-greeter passwordless-sync disable USUARIO`.

`preview` abre una ventana con tus datos y tema actuales. Desactiva la autenticación y las acciones de energía. La versión de inicio de sesión abre una ventana Qt por pantalla, con `Qt.FramelessWindowHint`, el tamaño completo del monitor y las solicitudes de cierre rechazadas. No muestra barra de título, bordes ni controles de minimizar o cerrar. Solicita confirmación antes de apagar, reiniciar o suspender.

El compositor nativo configura el tamaño de las superficies xdg, pero no confirma el estado fullscreen de una aplicación Qt. Por eso pedir únicamente `FloatingWindow.fullscreen` dejaba reaparecer la decoración de ventana. El greeter usa los controles públicos de `Window` para quitarla y rechazar el evento `closing`; la vista previa conserva su cierre normal. Las pruebas ejecutan ambos modos y comprueban la geometría, las decoraciones y la entrega real del evento de cierre de Qt. El modo de prueba de pantalla completa solo se habilita con las dos variables de prueba y vista previa activas; no expone controles de prueba en el inicio de sesión real.

Para detener la sincronización, usa `systemctl --user disable --now hyprlarp-greeter-sync.path`. El greeter conserva la última apariencia aplicada. Para restaurar el aspecto anterior, restaura los archivos de la copia de `/var/backups/hyprlarp-greeter/FECHA/` antes del próximo inicio del greeter.

Referencias: [configuración de Noctalia Greeter](https://docs.noctalia.dev/greeter/configuration/) y [sincronización y autorización de apariencia](https://docs.noctalia.dev/greeter/sync/).
