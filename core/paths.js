function fileUrl(path) {
  return path ? "file://" + path.split("/").map(encodeURIComponent).join("/") : "";
}
