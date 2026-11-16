import type { CatalogRegion, DateFilters, Filters, Region, RegionOption, SeasonalResult } from "./types";

export type AvailableMonth = { year: string; month: string; count: number };
export type PeriodSelection = { year: string; month: string; day: string };

// Sensors filter results within the chosen period, without changing the
// dataset's date choices or invalidating a user's existing selection.
export function dateAvailabilityScope(filters: Filters): Filters {
  return { ...filters, startDate: "", endDate: "", sensor: "ALL" };
}

// Monthly rows can be split by hemisphere. A period is available only if it
// contains observations, regardless of how many hemisphere rows describe it.
export function availableMonths(rows: SeasonalResult["data"]): AvailableMonth[] {
  const months = new Map<string, AvailableMonth>();
  for (const row of rows) {
    if (row.fire_count <= 0) continue;
    const year = String(row.year).padStart(4, "0");
    const month = String(row.month).padStart(2, "0");
    const key = `${year}-${month}`;
    const previous = months.get(key);
    months.set(key, { year, month, count: (previous?.count ?? 0) + row.fire_count });
  }
  return [...months.values()].sort((a, b) => `${b.year}-${b.month}`.localeCompare(`${a.year}-${a.month}`));
}

export function periodDates({ year, month, day }: PeriodSelection): DateFilters {
  if (!year) return { startDate: "", endDate: "" };
  if (!/^\d{4}$/.test(year) || Number(year) < 1) throw new Error("Choose an available year.");
  if (!month) return { startDate: `${year}-01-01`, endDate: `${year}-12-31` };
  if (!/^(0[1-9]|1[0-2])$/.test(month)) throw new Error("Choose an available month.");
  const end = new Date(`${year}-${month}-01T00:00:00Z`);
  end.setUTCMonth(end.getUTCMonth() + 1, 0);
  if (!day) return { startDate: `${year}-${month}-01`, endDate: end.toISOString().slice(0, 10) };
  const date = `${year}-${month}-${day}`;
  if (!/^(0[1-9]|[12]\d|3[01])$/.test(day) || date > end.toISOString().slice(0, 10)) throw new Error("Choose an available day.");
  return { startDate: date, endDate: date };
}

// The catalog is inexpensive. Do not make country selection wait for the
// slower hotspot geometry aggregation, or use integer catalog IDs on /fires.
export function selectableRegions(catalog: CatalogRegion[], raw: Region[]): RegionOption[] {
  const regions = new Map<string, RegionOption>();
  for (const region of catalog) {
    const code = region.country_code;
    if (!code || regions.has(code)) continue;
    const { min_latitude, max_latitude, min_longitude, max_longitude } = region;
    const bounding_box = min_latitude != null && max_latitude != null && min_longitude != null && max_longitude != null
      ? { min_latitude, max_latitude, min_longitude, max_longitude } : null;
    regions.set(code, { id: code, country_code: code, name: region.name, bounding_box });
  }
  for (const region of raw) {
    const existing = regions.get(region.country_code);
    regions.set(region.country_code, {
      id: region.country_code,
      country_code: region.country_code,
      name: existing?.name ?? region.name.replaceAll("_", " "),
      bounding_box: region.bounding_box ?? existing?.bounding_box,
      centroid: region.centroid,
    });
  }
  return [...regions.values()].sort((a, b) => a.name.localeCompare(b.name, "en"));
}
