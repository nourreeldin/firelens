import { infiniteQueryOptions, queryOptions, type QueryClient } from "@tanstack/react-query";
import { ACTIVITY_METHOD, QA_METHOD, api } from "./api/client";
import { dateAvailabilityScope } from "./api/availability";
import type { ActivityFilters, Filters, ValidationFilters } from "./api/types";

export const defaultFilters: Filters = { region: "", startDate: "", endDate: "", sensor: "ALL" };
export const defaultProductScope = { regionPk: "", methodVersion: ACTIVITY_METHOD, validationMethodVersion: QA_METHOD, spatialGridId: "" };

// Keep each selection for the lifetime of the app's shared QueryClient.
export const dashboardCacheOptions = { staleTime: Infinity, gcTime: Infinity };

export const dashboardQueries = {
  health: () => queryOptions({ queryKey: ["health"], queryFn: ({ signal }) => api.health(signal) }),
  catalog: () => queryOptions({ queryKey: ["region-catalog"], queryFn: ({ signal }) => api.regionCatalog(signal) }),
  regions: () => queryOptions({ queryKey: ["regions"], queryFn: ({ signal }) => api.regions(signal) }),
  availablePeriods: (filters: Filters) => queryOptions({ queryKey: ["available-periods", filters], queryFn: ({ signal }) => api.availablePeriods(filters, signal) }),
  fires: (filters: Filters, page = 1) => queryOptions({ queryKey: ["fires", filters, page], queryFn: ({ signal }) => api.fires(filters, page, 100, signal) }),
  calendar: (filters: Filters) => queryOptions({ queryKey: ["calendar", filters], queryFn: ({ signal }) => api.calendar(filters, signal) }),
  seasonal: (filters: Filters) => queryOptions({ queryKey: ["seasonal", filters], queryFn: ({ signal }) => api.seasonal(filters, signal) }),
  comparison: (filters: Filters) => queryOptions({ queryKey: ["comparison", filters], queryFn: ({ signal }) => api.comparison(filters, signal) }),
  anomalies: (filters: Filters) => queryOptions({ queryKey: ["anomalies", filters], queryFn: ({ signal }) => api.anomalies(filters, signal) }),
  activity: (filters: ActivityFilters, page = 1) => queryOptions({ queryKey: ["activity-records", filters, page], queryFn: ({ signal }) => api.activity(filters, page, 100, signal) }),
  activityCalendar: (filters: ActivityFilters) => queryOptions({ queryKey: ["activity-calendar", filters], queryFn: ({ signal }) => api.activityCalendar(filters, signal) }),
  activitySeasonal: (filters: ActivityFilters) => queryOptions({ queryKey: ["activity-seasonal", filters], queryFn: ({ signal }) => api.activitySeasonal(filters, signal) }),
  activityComparison: (filters: ActivityFilters) => queryOptions({ queryKey: ["activity-comparison", filters], queryFn: ({ signal }) => api.activityComparison(filters, signal) }),
  activityAnomalies: (filters: ActivityFilters) => queryOptions({ queryKey: ["activity-anomalies", filters], queryFn: ({ signal }) => api.activityAnomalies(filters, signal) }),
  validation: (filters: ValidationFilters, page = 1) => queryOptions({ queryKey: ["validation", filters, page], queryFn: ({ signal }) => api.validation(filters, page, 100, signal) }),
  map: (filters: Filters) => infiniteQueryOptions({
    queryKey: ["map-detections", filters],
    queryFn: ({ pageParam, signal }) => api.fires(filters, pageParam, 500, signal),
    initialPageParam: 1,
    getNextPageParam: (lastPage, _pages, lastPageNumber) => {
      const { offset, total } = lastPage.pagination;
      return lastPage.data.length > 0 && offset + lastPage.data.length < total ? lastPageNumber + 1 : undefined;
    },
  }),
};

const preloads = new WeakMap<QueryClient, Promise<void>>();
export const initialPreloadProgress = { completed: 0, total: 16, ready: false };
const progress = new WeakMap<QueryClient, typeof initialPreloadProgress>();
const listeners = new WeakMap<QueryClient, Set<() => void>>();

export function getDashboardPreloadProgress(client: QueryClient) {
  return progress.get(client) ?? initialPreloadProgress;
}

export function subscribeDashboardPreload(client: QueryClient, listener: () => void) {
  let subscribers = listeners.get(client);
  if (!subscribers) { subscribers = new Set(); listeners.set(client, subscribers); }
  subscribers.add(listener);
  return () => { subscribers.delete(listener); };
}

export function preloadDashboardData(client: QueryClient): Promise<void> {
  const existing = preloads.get(client);
  if (existing) return existing;

  const activityFilters: ActivityFilters = {
    startDate: "", endDate: "", regionPk: "", methodVersion: defaultProductScope.methodVersion, spatialGridId: "",
  };
  const validationFilters: ValidationFilters = {
    startDate: "", endDate: "", regionPk: "", methodVersion: defaultProductScope.validationMethodVersion,
  };
  // Prefetch uses the exact keys consumed by the views and shares in-flight requests.
  // It intentionally keeps running if the landing page unmounts during navigation.
  const tasks = [
    client.prefetchQuery(dashboardQueries.health()),
    client.prefetchQuery(dashboardQueries.catalog()),
    client.prefetchQuery(dashboardQueries.regions()),
    client.prefetchQuery(dashboardQueries.availablePeriods(dateAvailabilityScope(defaultFilters))),
    client.prefetchQuery(dashboardQueries.fires(defaultFilters)),
    client.prefetchQuery(dashboardQueries.calendar(defaultFilters)),
    client.prefetchQuery(dashboardQueries.seasonal(defaultFilters)),
    client.prefetchQuery(dashboardQueries.comparison(defaultFilters)),
    client.prefetchQuery(dashboardQueries.anomalies(defaultFilters)),
    client.prefetchQuery(dashboardQueries.activity(activityFilters)),
    client.prefetchQuery(dashboardQueries.activityCalendar(activityFilters)),
    client.prefetchQuery(dashboardQueries.activitySeasonal(activityFilters)),
    client.prefetchQuery(dashboardQueries.activityComparison(activityFilters)),
    client.prefetchQuery(dashboardQueries.activityAnomalies(activityFilters)),
    client.prefetchQuery(dashboardQueries.validation(validationFilters)),
    client.prefetchInfiniteQuery(dashboardQueries.map(defaultFilters)),
  ];
  progress.set(client, { completed: 0, total: tasks.length, ready: false });
  const preload = Promise.all(tasks.map((task) => task.then(() => {
    const completed = getDashboardPreloadProgress(client).completed + 1;
    // Prefetch settles on API errors too, so users can open the workspace's
    // existing error/retry controls instead of getting stuck on this screen.
    progress.set(client, { completed, total: tasks.length, ready: completed === tasks.length });
    listeners.get(client)?.forEach((listener) => listener());
  }))).then(() => undefined);
  preloads.set(client, preload);
  return preload;
}
