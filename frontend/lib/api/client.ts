import type { ActivityFilters, ValidationFilters, ActivityListResult, ActivityCalendarResult, ActivitySeasonalResult, ActivityComparisonResult, ActivityAnomalyResult, ValidationListResult, RegionCatalogResult, RegionListResult, HealthResult, DateFilters, CalendarResult, ComparisonResult, Filters, FireListResult, SeasonalResult, AnomalyResult, FireDetection } from "./types";
const BASE = (process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000").replace(/\/+$/, "").replace(/\/api\/v1$/, "");
export const ACTIVITY_METHOD = "daily-grid-modis-equivalent-v1";
export const QA_METHOD = "pair-integrity-1km-30min-v1";
export class ApiError extends Error { constructor(public status: number, message: string) { super(message); this.name = "ApiError"; } }
export function filterError(filters: DateFilters): string | null {
  if (Boolean(filters.startDate) !== Boolean(filters.endDate)) return "Choose both a start date and an end date, or clear both dates.";
  if (filters.startDate > filters.endDate) return "The start date must be on or before the end date.";
  return null;
}

export function query(filters: Filters) {
  const error = filterError(filters);
  if (error) throw new Error(error);
  const params = new URLSearchParams();
  if (filters.startDate && filters.endDate) {
    params.set("start_date", filters.startDate);
    params.set("end_date", filters.endDate);
  }
  if (filters.region) params.set("region_id", filters.region);
  if (filters.sensor !== "ALL") params.set("sensor", filters.sensor);
  const bounds = filters.bounds;
  if (bounds && Object.values(bounds).some((value) => value?.trim())) {
    const keys = ["min_latitude", "max_latitude", "min_longitude", "max_longitude"] as const;
    if (keys.some((key) => !bounds[key]?.trim())) throw new Error("Enter all four geographic bounds, or clear all of them.");
    const south = Number(bounds.min_latitude), north = Number(bounds.max_latitude);
    const west = Number(bounds.min_longitude), east = Number(bounds.max_longitude);
    if (![south, north, west, east].every(Number.isFinite) || south < -90 || north > 90 || west < -180 || east > 180 || south >= north || west >= east) throw new Error("Geographic bounds must be valid coordinates with south < north and west < east.");
    keys.forEach((key) => params.set(key, bounds[key]!.trim()));
  }
  return params;
}

export function activityQuery(filters: ActivityFilters | ValidationFilters, product: "harmonization" | "validation" = "harmonization") {
  const error = filterError(filters);
  if (error) throw new Error(error);
  const params = new URLSearchParams();
  if (filters.startDate && filters.endDate) {
    params.set("start_date", filters.startDate);
    params.set("end_date", filters.endDate);
  }
  if (filters.regionPk) {
    if (!/^\d+$/.test(filters.regionPk) || Number(filters.regionPk) < 1) throw new Error("Choose a valid catalog region.");
    params.set("region_pk", filters.regionPk);
  }
  if (filters.methodVersion.trim()) params.set("method_version", filters.methodVersion.trim());
  if (product === "harmonization" && "spatialGridId" in filters && filters.spatialGridId.trim()) params.set("spatial_grid_id", filters.spatialGridId.trim());
  return params;
}

function paginated(params: URLSearchParams, page: number, pageSize: number) {
  const limit = Math.max(1, Math.min(pageSize, 1000));
  params.set("limit", String(limit));
  params.set("offset", String((page - 1) * limit));
  return params;
}

export function calendarError(filters: DateFilters) {
  return filters.startDate && filters.endDate && (Date.parse(filters.endDate) - Date.parse(filters.startDate)) / 86_400_000 + 1 > 366
    ? "Choose a range of 366 days or fewer for the daily calendar." : null;
}

export function historyError(filters: DateFilters) {
  return filters.startDate && filters.endDate && filters.startDate.slice(0, 4) !== filters.endDate.slice(0, 4)
    ? "Choose dates within one calendar year to view historical analytics." : null;
}

async function request<T>(path: string, params?: URLSearchParams, signal?: AbortSignal): Promise<T> {
  // Browser requests use the app's origin, so API CORS settings cannot prevent
  // region/date selectors from loading. Node clients can still call the API.
  const url = typeof window === "undefined" ? `${BASE}${path}` : `/api/backend${path.replace(/^\/api\/v1/, "")}`;
  const response = await fetch(`${url}${params?.size ? `?${params}` : ""}`, {
    headers: { Accept: "application/json" },
    // Unfiltered lists scan the study dataset and can exceed 15 seconds.
    signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(60000)]) : AbortSignal.timeout(60000),
  });
  if (!response.ok) {
    const messages: Record<number, string> = {
      404: "The requested data was not found.",
      422: "The selected filters are invalid. Check the date range and region.",
      500: "The FireLens API encountered an internal error.",
      503: "The FireLens API is temporarily unavailable.",
    };
    const body = await response.json().catch(() => null);
    throw new ApiError(response.status, typeof body?.detail === "string" ? body.detail : messages[response.status] || `API request failed (${response.status}).`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: (signal?: AbortSignal) => request<HealthResult>("/api/v1/health", undefined, signal),
  regions: (signal?: AbortSignal) => request<RegionListResult>("/api/v1/regions", undefined, signal),
  regionCatalog: (signal?: AbortSignal) => request<RegionCatalogResult>("/api/v1/regions/catalog", undefined, signal),
  fire: (id: number, signal?: AbortSignal) => request<FireDetection>(`/api/v1/fires/${id}`, undefined, signal),
  fires: (filters: Filters, page: number, pageSize = 100, signal?: AbortSignal) => {
    const params = paginated(query(filters), page, pageSize);
    return request<FireListResult>("/api/v1/fires", params, signal);
  },
  calendar: (filters: Filters, signal?: AbortSignal) => request<CalendarResult>("/api/v1/calendar", query(filters), signal),
  seasonal: (filters: Filters, signal?: AbortSignal) => request<SeasonalResult>("/api/v1/analytics/seasonal", query(filters), signal),
  // Seasonal aggregation accepts multi-year ranges and returns only months
  // represented in the data. Discover all years without paging detections.
  availablePeriods: (filters: Filters, signal?: AbortSignal) => request<SeasonalResult>("/api/v1/analytics/seasonal", query({ ...filters, startDate: "0001-01-01", endDate: "9999-12-31" }), signal),
  comparison: (filters: Filters, signal?: AbortSignal) => request<ComparisonResult>("/api/v1/analytics/comparison", query(filters), signal),
  anomalies: (filters: Filters, signal?: AbortSignal) => request<AnomalyResult>("/api/v1/analytics/anomalies", query(filters), signal),
  activity: (filters: ActivityFilters, page = 1, pageSize = 100, signal?: AbortSignal) => request<ActivityListResult>("/api/v1/harmonization", paginated(activityQuery(filters), page, pageSize), signal),
  activityCalendar: (filters: ActivityFilters, signal?: AbortSignal) => request<ActivityCalendarResult>("/api/v1/harmonization/calendar", activityQuery(filters), signal),
  activitySeasonal: (filters: ActivityFilters, signal?: AbortSignal) => request<ActivitySeasonalResult>("/api/v1/harmonization/analytics/seasonal", activityQuery(filters), signal),
  activityComparison: (filters: ActivityFilters, signal?: AbortSignal) => request<ActivityComparisonResult>("/api/v1/harmonization/analytics/comparison", activityQuery(filters), signal),
  activityAnomalies: (filters: ActivityFilters, signal?: AbortSignal) => request<ActivityAnomalyResult>("/api/v1/harmonization/analytics/anomalies", activityQuery(filters), signal),
  validation: (filters: ValidationFilters, page = 1, pageSize = 100, signal?: AbortSignal) => request<ValidationListResult>("/api/v1/validation", paginated(activityQuery(filters, "validation"), page, pageSize), signal),
};
