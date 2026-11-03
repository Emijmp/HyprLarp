// Search labels mirror real settings rather than indexing instantiated controls.
var entries = [
  ["Appearance", "Separación de ventanas", "gaps ventanas bordes pantalla margen exterior interior distancia separacion espacios"],
  ["General", "OSD", "volumen brillo microfono indicadores nivel duracion posicion"],
  ["General", "Modo nocturno", "descanso visual temperatura luz azul horario hyprsunset"],
  ["Appearance", "Redondez", "radio redondear esquinas bordes barra paneles botones campos notificaciones ayudas espacios de trabajo"],
  ["Appearance", "Detalles visuales", "decoracion adornos sutil minimo esquinas marcas geometricas"],
  ["Appearance", "Tema", "amoled gruvbox catppuccin oxocarbon tokyo night one dark pro personalizado colores paleta"],
  ["Appearance", "Acento", "color rgb hexadecimal"],
  ["Appearance", "Fuente", "tipografia letra radio opacidad paneles animaciones"],
  ["Bar", "Posición", "barra monitor pantalla arriba abajo izquierda derecha"],
  ["Bar", "Grosor", "altura tamaño padding horizontal vertical borde margen longitud alineacion blur desenfoque transparencia opacidad"],
  ["Modules", "Inicio", "modulos agregar quitar arrastrar reordenar centro final inicio bandeja tray ocultos"],
  ["Modules", "Aspecto de los módulos", "fondo radio padding borde transparencia opacidad"],
  ["Wallpapers", "Fondos", "wallpaper imagen directorio carpeta externo waypaper animado video mpvpaper restaurar inicio"],
  ["Shortcuts", "Atajos", "binds teclado capturar combinacion conflicto aplicar agregar eliminar modificar personalizados comandos actuales noctalia"],
  ["General", "Historial del portapapeles", "clipboard activar desactivar pausar caducidad vencimiento"],
  ["General", "Notificaciones", "sonido popup avisos reglas aplicaciones historial"],
  ["Profiles", "Perfiles", "guardar cargar perfil importar exportar json biblioteca temas"]
];
function search(text) {
  const words = text.normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim().split(/\s+/);
  return entries.filter(entry => words.every(word => entry.join(" ").normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().includes(word)));
}
