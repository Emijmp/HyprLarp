// Search labels mirror real settings rather than indexing instantiated controls.
var entries = [
  ["General", "Asistente de primera ejecución", "bienvenida primeros pasos comenzar inicio configuración inicial version hyprlarp", "setting-welcome"],
  ["General", "Rendimiento del shell", "rendimiento consumo cpu ram memoria arranque revision comparar medicion historial procesos", "setting-performance"],
  ["General", "Perfil de actividad del shell", "rendimiento optimizar eficiente equilibrado agil sondeos fondo cpu memoria efectos desenfoque animaciones", "setting-performance-mode"],
  ["General", "Accesibilidad", "escala texto tamaño letra grande alto contraste movimiento teclado tab foco lector pantalla orca at-spi", "setting-accessibility"],
  ["General", "Tamaño mínimo del texto", "accesibilidad legibilidad lectura letra fuente etiquetas pequeñas px", "setting-minimum-font-size"],
  ["General", "Fallos y recuperación", "fallo falla recuperar recuperacion seguro minimo desactivado modulo componente reiniciar", "setting-recovery"],
  ["Displays", "Pantallas y proyección", "monitor monitores proyector proyectar duplicar espejo extender resolucion frecuencia hz escala orientacion girar posicion pantalla externa principal secundaria", "Pantallas conectadas"],
  ["General", "Reloj y fecha", "reloj hora formato tiempo 12h 24h am pm", "setting-clock"],
  ["General", "Formato de hora", "reloj 12h 24h am pm", "setting-clockFormat"],
  ["General", "Mostrar segundos", "reloj hora segundos", "setting-clockSeconds"],
  ["General", "Formato de fecha", "dia mes año fecha formato dd mm yyyy", "setting-clockDateFormat"],
  ["General", "Calendario", "semana semanas iso lunes domingo primer dia", "setting-calendar"],
  ["General", "Avisos de batería", "bateria baja critica carga porcentaje alertas aviso cargador", "setting-batteryAlerts"],
  ["General", "Diagnóstico", "diagnostico errores dependencias versiones informe exportar", "Estado del sistema"],
  ["Appearance", "Opacidad de paneles", "opacidad transparencia paneles"],
  ["Bar", "Opacidad", "barra opacidad transparencia"],
  ["Appearance", "Separación de ventanas", "gaps ventanas bordes pantalla margen exterior interior distancia separacion espacios"],
  ["General", "OSD", "volumen brillo microfono indicadores nivel duracion posicion", "OSD · volumen, micrófono y brillo"],
  ["General", "Modo nocturno", "descanso visual temperatura luz azul horario hyprsunset", "Modo nocturno / descanso visual"],
  ["Appearance", "Redondez", "radio redondear esquinas bordes barra paneles botones campos notificaciones ayudas espacios de trabajo"],
  ["Appearance", "Detalles visuales", "decoracion adornos sutil minimo esquinas marcas geometricas"],
  ["Appearance", "Tema", "amoled gruvbox catppuccin oxocarbon tokyo night one dark pro personalizado colores paleta"],
  ["Appearance", "Tema por horario", "tema contextual automático día noche horario hora amanecer anochecer", "setting-theme-schedule"],
  ["Appearance", "Vista previa de temas", "tema previsualizar vista muestra paleta barra panel aplicar", "setting-theme-preview"],
  ["Appearance", "Colores extraídos del fondo", "wallpaper fondo imagen muestrear extraer colores paleta acento swatches", "setting-wallpaper-colors"],
  ["Appearance", "Vista previa del panel", "panel diseño lateral centrado flotante opacidad transparencia vidrio flat aplicar descartar", "panel-design-preview"],
  ["Appearance", "Distribución de paneles", "panel diseño lateral sidebar flotante centrado pantalla completa", "setting-panel-distribution"],
  ["Appearance", "Estilo de paneles", "panel superficie vidrio glass translúcido desenfoque flat plano estándar opacidad", "setting-panel-surface"],
  ["Appearance", "Pantalla de inicio de sesión", "greetd greeter diseño tema barra lateral centrado login acceso"],
  ["Appearance", "Acento", "color rgb hexadecimal"],
  ["Appearance", "Fuente", "tipografia letra", "Tipografía"],
  ["Appearance", "Animaciones", "animaciones transiciones color", "Transiciones cortas de color (80 ms)"],
  ["Bar", "Posición", "barra monitor pantalla arriba abajo izquierda derecha"],
  ["Bar", "Grosor", "altura tamaño padding horizontal vertical borde margen longitud alineacion blur desenfoque transparencia opacidad"],
  ["Modules", "Inicio", "modulos agregar quitar arrastrar reordenar centro final inicio bandeja tray ocultos"],
  ["Modules", "Aspecto de los módulos", "fondo radio padding borde transparencia opacidad", "Aspecto de los módulos", "appearance"],
  ["Wallpapers", "Fondos", "wallpaper imagen directorio carpeta externo waypaper animado video mpvpaper restaurar inicio"],
  ["Shortcuts", "Atajos", "binds teclado capturar combinacion conflicto aplicar agregar eliminar modificar personalizados comandos actuales noctalia"],
  ["General", "Historial del portapapeles", "clipboard activar desactivar pausar caducidad vencimiento"],
  ["General", "Notificaciones", "sonido popup avisos reglas aplicaciones historial", "Notificaciones · reglas por aplicación"],
  ["Profiles", "Perfiles", "guardar cargar perfil importar exportar json biblioteca temas"]
];
function normalize(text) {
  return String(text).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}
function search(text) {
  const words = normalize(text).split(/\s+/).filter(Boolean);
  if (!words.length)
    return [];
  return entries.filter(entry => words.every(word => normalize(entry.slice(0, 3).join(" ")).includes(word)));
}
