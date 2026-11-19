function contains(root, item) {
  for (let current = item; current; current = current.parent)
    if (current === root) return true;
  return false;
}
function first(root) {
  if (!root || !root.visible || !root.enabled) return null;
  if (root.activeFocusOnTab && root.width > 0 && root.height > 0) return root;
  for (const child of root.children || []) {
    const result = first(child);
    if (result) return result;
  }
  return null;
}
