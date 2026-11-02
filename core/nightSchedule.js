function active(settings, date) {
  if (!settings.nightLightSchedule) return !!settings.nightLightEnabled;
  const minute = date.getHours() * 60 + date.getMinutes();
  const parse = value => { const parts = value.split(":"); return Number(parts[0]) * 60 + Number(parts[1]); };
  const start = parse(settings.nightLightStart || "20:00"), end = parse(settings.nightLightEnd || "07:00");
  return start < end ? minute >= start && minute < end : start > end ? minute >= start || minute < end : true;
}
