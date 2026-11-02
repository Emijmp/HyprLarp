// Pure state transition: suppress startup and device replacement notifications.
function update(previous, sample, now) {
  const same = previous && previous.available && sample.available && previous.id === sample.id;
  const next = Object.assign({}, sample, {armedAt: same ? previous.armedAt : now});
  return {sample: next, changed: !!same && now - previous.armedAt >= 250 && (sample.value !== previous.value || sample.muted !== previous.muted)};
}
