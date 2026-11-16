import type { ActivityCalendarDay } from "./types";

// Versions describe different corrections. Never sum or overwrite them together.
export function activitySeries(days: ActivityCalendarDay[]) {
  const versions = [...new Set(days.map((day) => day.method_version))].sort();
  const byDate = new Map<string, Record<string, string | number | null>>();
  for (const day of days) {
    const point = byDate.get(day.date) ?? { date: day.date };
    point[`method_${versions.indexOf(day.method_version)}`] = day.harmonized_activity;
    byDate.set(day.date, point);
  }
  return { versions, points: [...byDate.values()].sort((a, b) => String(a.date).localeCompare(String(b.date))) };
}
