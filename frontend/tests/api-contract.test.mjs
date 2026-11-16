import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { afterEach, test } from "node:test";
import ts from "typescript";

// Load the TypeScript modules without adding a test runner dependency.
async function loadModule(path) {
  const source = await readFile(new URL(path, import.meta.url), "utf8");
  const { outputText } = ts.transpileModule(source, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
  });
  return import(`data:text/javascript;base64,${Buffer.from(outputText).toString("base64")}`);
}

const { ACTIVITY_METHOD, QA_METHOD, api, query, activityQuery, calendarError, historyError } = await loadModule("../lib/api/client.ts");
const { activitySeries } = await loadModule("../lib/api/activity-series.ts");
const { availableMonths, dateAvailabilityScope, periodDates, selectableRegions } = await loadModule("../lib/api/availability.ts");
const { GET: exportRoute } = await loadModule("../app/api/exports/[product]/route.ts");
const { GET: backendRoute } = await loadModule("../app/api/backend/[...path]/route.ts");
const GET = (request, product = "fires") => exportRoute(request, { params: Promise.resolve({ product }) });
const originalFetch = globalThis.fetch;
const originalKey = process.env.FIRELENS_API_KEY;
const originalBase = process.env.FIRELENS_API_BASE_URL;
const originalWindow = globalThis.window;
const filters = { region: "EGY", startDate: "2025-07-01", endDate: "2025-07-31", sensor: "VIIRS" };
const correctedFilters = { regionPk: "7", methodVersion: "v1", spatialGridId: "grid-001", startDate: "2025-07-01", endDate: "2025-07-31" };

afterEach(() => {
  globalThis.fetch = originalFetch;
  if (originalWindow === undefined) delete globalThis.window;
  else globalThis.window = originalWindow;
  for (const [name, value] of [["FIRELENS_API_KEY", originalKey], ["FIRELENS_API_BASE_URL", originalBase]]) {
    if (value === undefined) delete process.env[name];
    else process.env[name] = value;
  }
});

test("fire pages send documented limit/offset and retain the API total", async () => {
  let requested;
  globalThis.fetch = async (url) => {
    requested = new URL(url);
    return Response.json({ data: [{ id: 101 }], pagination: { limit: 100, offset: 100, total: 352 } });
  };
  const response = await api.fires(filters, 2);
  assert.equal(requested.pathname, "/api/v1/fires");
  assert.equal(requested.searchParams.get("offset"), "100");
  assert.equal(requested.searchParams.get("limit"), "100");
  assert.equal(requested.searchParams.get("region_id"), "EGY");
  assert.equal(requested.searchParams.get("sensor"), "VIIRS");
  assert.equal(requested.searchParams.get("start_date"), "2025-07-01");
  assert.equal(requested.searchParams.get("end_date"), "2025-07-31");
  assert.equal(requested.searchParams.has("page"), false);
  assert.equal(response.pagination.total, 352);
});

test("map batches respect the 1000-record API limit", async () => {
  globalThis.fetch = async (url) => {
    const params = new URL(url).searchParams;
    assert.equal(params.get("limit"), "1000");
    assert.equal(params.get("offset"), "1000");
    return Response.json({ data: [], pagination: { limit: 1000, offset: 1000, total: 1000 } });
  };
  await api.fires(filters, 2, 2000);
});

test("partial and reversed date ranges cannot silently export unfiltered data", () => {
  assert.throws(() => query({ ...filters, endDate: "" }), /both a start date/);
  assert.throws(() => query({ ...filters, startDate: "2025-08-01" }), /on or before/);
  const params = query({ region: "", startDate: "", endDate: "", sensor: "ALL" });
  assert.equal(params.size, 0);
});

test("API validation errors preserve readable backend messages", async () => {
  globalThis.fetch = async () => Response.json({ detail: "Calendar range exceeds 366 days." }, { status: 422 });
  await assert.rejects(api.calendar(filters), { status: 422, message: "Calendar range exceeds 366 days." });
});

test("corrected and validation filters never send country codes or sensor filters", async () => {
  const corrected = activityQuery({ ...correctedFilters, region: "EGY", sensor: "VIIRS" });
  assert.equal(corrected.get("region_pk"), "7");
  assert.equal(corrected.get("spatial_grid_id"), "grid-001");
  assert.equal(corrected.get("method_version"), "v1");
  assert.equal(corrected.has("region_id"), false);
  assert.equal(corrected.has("sensor"), false);
  const validation = activityQuery(correctedFilters, "validation");
  assert.equal(validation.has("spatial_grid_id"), false);
  assert.equal(validation.get("region_pk"), "7");
  assert.throws(() => activityQuery({ ...correctedFilters, regionPk: "EGY" }), /catalog region/);
  assert.throws(() => activityQuery({ ...correctedFilters, regionPk: "0" }), /catalog region/);
});

test("all new API calls use the correct paths and pagination", async () => {
  const paths = [];
  globalThis.fetch = async (url) => {
    const request = new URL(url);
    paths.push(request.pathname);
    if (request.pathname.endsWith("/harmonization") || request.pathname.endsWith("/validation")) {
      assert.equal(request.searchParams.get("limit"), "100");
      assert.equal(request.searchParams.get("offset"), "100");
      assert.equal(request.searchParams.get("region_pk"), "7");
    }
    if (request.pathname.endsWith("/validation")) assert.equal(request.searchParams.has("spatial_grid_id"), false);
    return Response.json({ data: [] });
  };
  await api.regionCatalog();
  await api.activity(correctedFilters, 2);
  await api.activityCalendar(correctedFilters);
  await api.activitySeasonal(correctedFilters);
  await api.activityComparison(correctedFilters);
  await api.activityAnomalies(correctedFilters);
  await api.validation(correctedFilters, 2);
  await api.fire(42);
  assert.deepEqual(paths, ["/api/v1/regions/catalog", "/api/v1/harmonization", "/api/v1/harmonization/calendar", "/api/v1/harmonization/analytics/seasonal", "/api/v1/harmonization/analytics/comparison", "/api/v1/harmonization/analytics/anomalies", "/api/v1/validation", "/api/v1/fires/42"]);
});

test("calendar chart keeps method versions distinct and preserves null activity", () => {
  const result = activitySeries([
    { date: "2025-07-02", method_version: "v2", harmonized_activity: null },
    { date: "2025-07-01", method_version: "v1", harmonized_activity: 2.7 },
    { date: "2025-07-01", method_version: "v2", harmonized_activity: 4.2 },
    { date: "2025-07-02", method_version: "v1", harmonized_activity: 0 },
  ]);
  assert.deepEqual(result.versions, ["v1", "v2"]);
  assert.deepEqual(result.points, [
    { date: "2025-07-01", method_0: 2.7, method_1: 4.2 },
    { date: "2025-07-02", method_0: 0, method_1: null },
  ]);
});

test("imported activity and QA use distinct methods with catalog IDs and dataset dates", async () => {
  assert.equal(ACTIVITY_METHOD, "daily-grid-modis-equivalent-v1");
  assert.equal(QA_METHOD, "pair-integrity-1km-30min-v1");
  const calendar = {
    status: "ok",
    data: [
      { date: "2020-12-29", method_version: ACTIVITY_METHOD, harmonized_activity: 1.1365, modis_count: 2, viirs_count: 3, grid_records: 1, uncertainty: 0.0045 },
      { date: "2020-12-30", method_version: ACTIVITY_METHOD, harmonized_activity: null, modis_count: 0, viirs_count: 0, grid_records: 0, uncertainty: null },
      { date: "2020-12-31", method_version: ACTIVITY_METHOD, harmonized_activity: 0, modis_count: 0, viirs_count: 0, grid_records: 1, uncertainty: 0 },
    ],
    meta: { start_date: "2020-12-02", end_date: "2020-12-31", total_harmonized_activity: null, method_versions: [ACTIVITY_METHOD] },
  };
  const report = { id: 9, method_version: QA_METHOD, region_id: 17, mae: null, rmse: null, bias: null, sample_size: 40808, notes: null };
  globalThis.fetch = async (url) => {
    const { pathname, searchParams } = new URL(url);
    if (pathname.endsWith("/regions/catalog")) return Response.json({ data: [{ id: 17, country_code: "EGY", name: "Egypt" }], total: 1 });
    assert.equal(searchParams.get("region_pk"), "17");
    assert.equal(searchParams.has("region_id"), false);
    assert.equal(searchParams.has("start_date"), false);
    assert.equal(searchParams.has("end_date"), false);
    if (pathname.endsWith("/calendar")) {
      assert.equal(searchParams.get("method_version"), ACTIVITY_METHOD);
      return Response.json(calendar);
    }
    assert.equal(pathname, "/api/v1/validation");
    assert.equal(searchParams.get("method_version"), QA_METHOD);
    assert.equal(searchParams.has("spatial_grid_id"), false);
    return Response.json({ status: "ok", data: [report], pagination: { limit: 100, offset: 0, total: 1 } });
  };
  const catalog = await api.regionCatalog();
  const regionPk = String(catalog.data.find((region) => region.country_code === "EGY").id);
  const shared = { regionPk, startDate: "", endDate: "" };
  const [activity, validation] = await Promise.all([
    api.activityCalendar({ ...shared, methodVersion: ACTIVITY_METHOD, spatialGridId: "" }),
    api.validation({ ...shared, methodVersion: QA_METHOD }),
  ]);
  assert.deepEqual(activity, calendar);
  assert.deepEqual(activitySeries(activity.data).points.map((point) => point.method_0), [1.1365, null, 0]);
  assert.deepEqual(validation.data[0], report);
});

test("raw detection details preserve source text IDs, native bands, and null values", async () => {
  const detection = { id: 42, source_detection_id: "00042-viirs-001", acq_time: 32, bright_t31: null, bright_ti4: 331.27, bright_ti5: 291.42, instrument: "VIIRS", source_file: "fires.csv", fire_type: 0, grid_lat: 0, created_at: null, confidence: "unknown", confidence_raw: null, version: "002" };
  globalThis.fetch = async () => Response.json(detection);
  const result = await api.fire(42);
  assert.deepEqual(result, detection);
  assert.equal(typeof result.source_detection_id, "string");
});

test("calendar and historical date limits are scoped to the appropriate views", () => {
  assert.equal(calendarError({ startDate: "2024-01-01", endDate: "2024-12-31" }), null);
  assert.match(calendarError({ startDate: "2024-01-01", endDate: "2025-01-01" }), /366 days/);
  assert.match(historyError({ startDate: "2024-12-31", endDate: "2025-01-01" }), /one calendar year/);
  assert.equal(historyError({ startDate: "", endDate: "" }), null);
});

test("raw geographic bounds must be complete, valid, and included in requests", () => {
  assert.throws(() => query({ ...filters, bounds: { min_latitude: "22" } }), /all four/);
  assert.throws(() => query({ ...filters, bounds: { min_latitude: "35", max_latitude: "22", min_longitude: "24", max_longitude: "37" } }), /south < north/);
  const params = query({ ...filters, bounds: { min_latitude: "22", max_latitude: "32", min_longitude: "24", max_longitude: "37" } });
  assert.equal(params.get("min_latitude"), "22");
  assert.equal(params.get("max_longitude"), "37");
});

test("available periods discover every dataset year while retaining country and sensor filters", async () => {
  globalThis.fetch = async (url) => {
    const request = new URL(url);
    assert.equal(request.pathname, "/api/v1/analytics/seasonal");
    assert.equal(request.searchParams.get("start_date"), "0001-01-01");
    assert.equal(request.searchParams.get("end_date"), "9999-12-31");
    assert.equal(request.searchParams.get("region_id"), "EGY");
    assert.equal(request.searchParams.get("sensor"), "VIIRS");
    return Response.json({ status: "ok", data: [] });
  };
  await api.availablePeriods(filters);
});

test("date choices include only observed months, merge hemispheres, and sort latest first", () => {
  assert.deepEqual(availableMonths([
    { year: 2018, month: 2, fire_count: 3 },
    { year: 2020, month: 1, fire_count: 2 },
    { year: 2018, month: 2, fire_count: 4 },
    { year: 2020, month: 2, fire_count: 0 },
    { year: 2020, month: 12, fire_count: 1 },
  ]), [
    { year: "2020", month: "12", count: 1 },
    { year: "2020", month: "01", count: 2 },
    { year: "2018", month: "02", count: 7 },
  ]);
  assert.deepEqual(availableMonths([]), []);
});

test("switching sensors preserves region and selected dates and reuses the same date availability", async () => {
  const selected = { region: "EGY", sensor: "ALL", ...periodDates({ year: "2019", month: "07", day: "15" }) };
  const dateScope = dateAvailabilityScope(selected);
  const requests = [];
  globalThis.fetch = async (url) => {
    const params = new URL(url).searchParams;
    assert.equal(params.get("region_id"), "EGY");
    assert.equal(params.get("start_date"), "2019-07-15");
    assert.equal(params.get("end_date"), "2019-07-15");
    requests.push(params.get("sensor"));
    // No matches for a sensor must remain an empty result, not clear filters.
    return Response.json({ data: [], pagination: { limit: 100, offset: 0, total: 0 } });
  };
  for (const sensor of ["MODIS", "VIIRS", "ALL"]) {
    const next = { ...selected, sensor };
    assert.deepEqual(dateAvailabilityScope(next), dateScope);
    assert.equal((await api.fires(next, 1)).pagination.total, 0);
    assert.equal(next.region, "EGY");
    assert.equal(next.startDate, "2019-07-15");
    assert.equal(next.endDate, "2019-07-15");
  }
  assert.deepEqual(requests, ["MODIS", "VIIRS", null]);
});

test("year, month, and day selections produce complete inclusive ranges, including leap days", () => {
  assert.deepEqual(periodDates({ year: "", month: "", day: "" }), { startDate: "", endDate: "" });
  assert.deepEqual(periodDates({ year: "2020", month: "", day: "" }), { startDate: "2020-01-01", endDate: "2020-12-31" });
  assert.deepEqual(periodDates({ year: "2020", month: "02", day: "" }), { startDate: "2020-02-01", endDate: "2020-02-29" });
  assert.deepEqual(periodDates({ year: "2019", month: "02", day: "" }), { startDate: "2019-02-01", endDate: "2019-02-28" });
  assert.deepEqual(periodDates({ year: "2020", month: "02", day: "29" }), { startDate: "2020-02-29", endDate: "2020-02-29" });
  assert.throws(() => periodDates({ year: "2019", month: "02", day: "29" }), /available day/);
});

test("catalog regions populate country choices before raw aggregates and retain country-code IDs", () => {
  const catalog = [{ id: 17, name: "Egypt", country_code: "EGY", min_latitude: 22, max_latitude: 32, min_longitude: 25, max_longitude: 35 }, { id: 1, name: "Unassigned", country_code: null }];
  const immediate = selectableRegions(catalog, []);
  assert.equal(immediate.length, 1);
  assert.equal(immediate[0].id, "EGY");
  assert.equal(immediate[0].name, "Egypt");
  assert.equal(immediate[0].bounding_box.min_latitude, 22);
  const enriched = selectableRegions(catalog, [
    { id: "EGY", country_code: "EGY", name: "Egypt", centroid: { latitude: 29, longitude: 30 }, bounding_box: null },
    { id: "ZAF", country_code: "ZAF", name: "South_Africa" },
  ]);
  assert.equal(enriched.length, 2);
  assert.equal(enriched[0].bounding_box.min_latitude, 22);
  assert.equal(enriched[0].centroid.latitude, 29);
  assert.equal(enriched[1].name, "South Africa");
});

test("browser region and date requests stay on the frontend origin", async () => {
  globalThis.window = {};
  const requests = [];
  globalThis.fetch = async (url) => { requests.push(String(url)); return Response.json({ data: [] }); };
  await api.regionCatalog();
  await api.availablePeriods(filters);
  assert.equal(requests[0], "/api/backend/regions/catalog");
  assert.ok(requests[1].startsWith("/api/backend/analytics/seasonal?"));
});

test("JSON proxy preserves API filters and error status without requiring browser CORS", async () => {
  process.env.FIRELENS_API_BASE_URL = "http://backend.test:8000/api/v1/";
  globalThis.fetch = async (url, options) => {
    const upstream = new URL(url);
    assert.equal(upstream.pathname, "/api/v1/regions/catalog");
    assert.equal(upstream.searchParams.get("region_pk"), "17");
    assert.equal(options.cache, "no-store");
    return Response.json({ detail: "Database is unavailable." }, { status: 503 });
  };
  const response = await backendRoute({ nextUrl: new URL("http://localhost:3000/api/backend/regions/catalog?region_pk=17"), signal: new AbortController().signal }, { params: Promise.resolve({ path: ["regions", "catalog"] }) });
  assert.equal(response.status, 503);
  assert.deepEqual(await response.json(), { detail: "Database is unavailable." });
});

test("JSON proxy rejects unsupported routes and explains connection failures", async () => {
  globalThis.fetch = async () => { throw new Error("offline"); };
  const request = { nextUrl: new URL("http://localhost:3000/api/backend/fires"), signal: new AbortController().signal };
  const unknown = await backendRoute(request, { params: Promise.resolve({ path: ["exports", "fires"] }) });
  assert.equal(unknown.status, 404);
  const offline = await backendRoute(request, { params: Promise.resolve({ path: ["fires"] }) });
  assert.equal(offline.status, 502);
  assert.match((await offline.json()).detail, /Could not connect/);
});

test("CSV proxy streams matching filters, attachment filename, and server-only auth", async () => {
  process.env.FIRELENS_API_KEY = "test-only-key";
  process.env.FIRELENS_API_BASE_URL = "http://backend.test:8000";
  const csv = "id,latitude,longitude\n1,30.1,31.5\n";
  globalThis.fetch = async (url, options) => {
    const upstream = new URL(url);
    assert.equal(upstream.origin, "http://backend.test:8000");
    assert.equal(upstream.pathname, "/api/v1/exports/fires");
    assert.equal(upstream.searchParams.get("region_id"), "EGY");
    assert.equal(upstream.searchParams.get("sensor"), "VIIRS");
    assert.equal(upstream.searchParams.get("start_date"), "2025-07-01");
    assert.equal(upstream.searchParams.get("end_date"), "2025-07-31");
    assert.equal(upstream.searchParams.has("limit"), false);
    assert.equal(options.headers.get("X-API-Key"), "test-only-key");
    assert.equal(options.cache, "no-store");
    return new Response(csv, { headers: { "Content-Type": "text/csv", "Content-Disposition": 'attachment; filename="backend-export.csv"' } });
  };
  const response = await GET({ nextUrl: new URL(`http://localhost:3000/api/exports/fires?${query(filters)}&limit=1`), signal: new AbortController().signal });
  assert.equal(response.status, 200);
  assert.equal(response.headers.get("Content-Disposition"), 'attachment; filename="backend-export.csv"');
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  assert.equal(response.headers.has("X-API-Key"), false);
  assert.equal(await response.text(), csv);
});

test("CSV proxy preserves error status and explains missing export access", async () => {
  globalThis.fetch = async () => Response.json({ detail: "Unauthorized" }, { status: 401 });
  const response = await GET({ nextUrl: new URL("http://localhost:3000/api/exports/fires"), signal: new AbortController().signal });
  assert.equal(response.status, 401);
  assert.match((await response.json()).error, /FIRELENS_API_KEY/);
});

test("CSV proxy reports connection failures without returning a CSV attachment", async () => {
  globalThis.fetch = async () => { throw new Error("offline"); };
  const response = await GET({ nextUrl: new URL("http://localhost:3000/api/exports/fires"), signal: new AbortController().signal });
  assert.equal(response.status, 502);
  assert.equal(response.headers.has("Content-Disposition"), false);
});

test("corrected and validation CSV proxies whitelist their own filters and normalize API base URLs", async () => {
  process.env.FIRELENS_API_BASE_URL = "http://backend.test:8000/api/v1/";
  for (const product of ["harmonization", "validation"]) {
    globalThis.fetch = async (url) => {
      const upstream = new URL(url);
      assert.equal(upstream.pathname, `/api/v1/exports/${product}`);
      assert.equal(upstream.searchParams.get("region_pk"), "7");
      assert.equal(upstream.searchParams.get("method_version"), "v1");
      assert.equal(upstream.searchParams.has("region_id"), false);
      assert.equal(upstream.searchParams.has("sensor"), false);
      assert.equal(upstream.searchParams.has("limit"), false);
      assert.equal(upstream.searchParams.has("spatial_grid_id"), product === "harmonization");
      return new Response("id,method_version\n1,v1\n", { headers: { "Content-Type": "text/csv" } });
    };
    const response = await GET({ nextUrl: new URL(`http://localhost:3000/api/exports/${product}?region_pk=7&method_version=v1&spatial_grid_id=grid-001&sensor=VIIRS&region_id=EGY&limit=1`), signal: new AbortController().signal }, product);
    assert.equal(response.status, 200);
    assert.match(response.headers.get("Content-Disposition"), new RegExp(`firelens-${product}\\.csv`));
  }
});

test("unknown CSV products are rejected before calling the backend", async () => {
  globalThis.fetch = async () => { throw new Error("Must not be called"); };
  for (const product of ["unknown", "__proto__", "constructor"]) {
    const response = await GET({ nextUrl: new URL("http://localhost:3000/api/exports/unknown"), signal: new AbortController().signal }, product);
    assert.equal(response.status, 404);
  }
});

test("live region and date selectors use the same-origin API and observed dates", { skip: !process.env.FIRELENS_LIVE_TEST }, async (t) => {
  const base = process.env.FIRELENS_PREVIEW_URL || "http://localhost:3000";
  async function get(path) {
    const response = await originalFetch(`${base}/api/backend${path}`, { signal: AbortSignal.timeout(60000) });
    assert.equal(response.status, 200, `${path}: ${await response.clone().text()}`);
    return response.json();
  }
  const catalog = await get("/regions/catalog");
  const countries = selectableRegions(catalog.data, []);
  assert.ok(countries.length > 0);
  const country = countries.find((region) => region.country_code === "EGY") ?? countries[0];
  const query = new URLSearchParams({ region_id: country.id, start_date: "0001-01-01", end_date: "9999-12-31" });
  const seasonal = await get(`/analytics/seasonal?${query}`);
  const months = availableMonths(seasonal.data);
  assert.ok(months.length > 0);
  const year = months[0].year;
  const range = periodDates({ year, month: "", day: "" });
  const yearQuery = new URLSearchParams({ region_id: country.id, start_date: range.startDate, end_date: range.endDate });
  const calendar = await get(`/calendar?${yearQuery}`);
  const observed = calendar.data.filter((day) => day.fire_count > 0);
  assert.ok(observed.length > 0);
  assert.ok(observed.every((day) => months.some((month) => `${month.year}-${month.month}` === day.date.slice(0, 7))));
  const date = observed[0].date;
  const detections = await get(`/fires?${new URLSearchParams({ region_id: country.id, start_date: date, end_date: date, limit: "2" })}`);
  assert.ok(detections.data.length > 0);
  assert.ok(detections.data.every((fire) => fire.acq_date === date && fire.country_code === country.id));
  const page = await originalFetch(`${base}/dashboard`, { signal: AbortSignal.timeout(30000) });
  assert.equal(page.status, 200);
  const html = await page.text();
  const [head, body] = html.split("</head>");
  assert.match(head, /<title>FireLens \| Fire Activity Dashboard<\/title>/);
  assert.doesNotMatch(body, /<title>|<meta name="description"/);
  assert.doesNotMatch(html, /<input[^>]*type="date"/);
  for (const label of ["AVAILABLE YEAR", "AVAILABLE MONTH", "AVAILABLE DAY"]) assert.ok(html.includes(label));
  t.diagnostic(`${countries.length} catalog countries; available years ${[...new Set(months.map((row) => row.year))].join(", ")}; ${observed.length} observed days in ${year}; verified detections for ${date}.`);
});

test("live backend and Next.js CSV route follow the documented contract", { skip: !process.env.FIRELENS_LIVE_TEST }, async () => {
  const all = { region: "", startDate: "", endDate: "", sensor: "ALL" };
  assert.equal((await api.health()).status, "ok");
  const regions = await api.regions();
  assert.ok(Array.isArray(regions.data));
  const first = await api.fires(all, 1, 2);
  const second = await api.fires(all, 2, 2);
  assert.equal(first.pagination.limit, 2);
  assert.equal(second.pagination.offset, 2);
  if (second.data.length) assert.notEqual(first.data[0].id, second.data[0].id);
  const calendar = await api.calendar(all);
  assert.ok(calendar.data.every((day) => Number.isFinite(day.fire_count)));
  assert.equal(calendar.data.reduce((sum, day) => sum + day.fire_count, 0), calendar.meta.total_fires);
  const seasonal = await api.seasonal(all);
  assert.ok(Array.isArray(seasonal.seasonal));
  assert.ok(seasonal.seasonal.every((season) => Number.isFinite(season.fire_count)));
  if (first.data[0]) assert.equal((await api.fire(first.data[0].id)).id, first.data[0].id);
  const catalog = await api.regionCatalog();
  assert.ok(catalog.data.every((region) => Number.isInteger(region.id)));
  const region = catalog.data.find((row) => row.country_code === "EGY") ?? catalog.data[0];
  const corrected = { regionPk: region ? String(region.id) : "", methodVersion: ACTIVITY_METHOD, spatialGridId: "", startDate: "", endDate: "" };
  const activity = await api.activity(corrected, 1, 2);
  assert.equal(activity.pagination.limit, 2);
  assert.ok(activity.data.every((row) => row.method_version === ACTIVITY_METHOD));
  const correctedCalendar = await api.activityCalendar(corrected);
  assert.ok(Array.isArray(correctedCalendar.meta.method_versions));
  if (correctedCalendar.meta.method_versions.length > 1) assert.equal(correctedCalendar.meta.total_harmonized_activity, null);
  assert.ok(correctedCalendar.data.every((day) => day.harmonized_activity == null || Number.isFinite(day.harmonized_activity)));
  const correctedSeasons = await api.activitySeasonal(corrected);
  assert.ok(Array.isArray(correctedSeasons.seasonal));
  for (const result of [await api.activityComparison(corrected), await api.activityAnomalies(corrected), await api.comparison(all), await api.anomalies(all)]) {
    assert.ok(["ok", "no_data", "insufficient_history"].includes(result.status));
    assert.ok(Array.isArray(result.data));
  }
  const qa = { ...corrected, methodVersion: QA_METHOD };
  const reports = await api.validation(qa, 1, 2);
  assert.equal(reports.pagination.limit, 2);
  assert.ok(reports.data.every((row) => row.method_version === QA_METHOD));

  // Exercise the real Next.js proxy using a single existing detection day.
  const fire = first.data[0];
  const exportFilters = fire ? { ...all, region: fire.country_code ?? "", startDate: fire.acq_date, endDate: fire.acq_date } : all;
  const previewBase = process.env.FIRELENS_PREVIEW_URL || "http://localhost:3000";
  const response = await originalFetch(`${previewBase}/api/exports/fires?${query(exportFilters)}`, { signal: AbortSignal.timeout(60000) });
  assert.equal(response.status, 200, await response.clone().text());
  assert.match(response.headers.get("Content-Type"), /text\/csv/);
  assert.match(response.headers.get("Content-Disposition"), /attachment.*\.csv/);
  assert.equal(response.headers.get("Cache-Control"), "no-store");
  const csv = await response.text();
  assert.ok(csv.split(/\r?\n/).length >= 2);
  for (const product of ["harmonization", "validation"]) {
    const exportScope = product === "validation" ? qa : {
      ...corrected,
      startDate: activity.data[0]?.activity_date ?? "",
      endDate: activity.data[0]?.activity_date ?? "",
    };
    const download = await originalFetch(`${previewBase}/api/exports/${product}?${activityQuery(exportScope, product)}`, { signal: AbortSignal.timeout(60000) });
    assert.equal(download.status, 200, await download.clone().text());
    assert.match(download.headers.get("Content-Type"), /text\/csv/);
    assert.match(download.headers.get("Content-Disposition"), /attachment.*\.csv/);
    assert.equal(download.headers.get("Cache-Control"), "no-store");
    assert.ok((await download.text()).length > 0);
  }
  const page = await originalFetch(`${previewBase}/dashboard`, { signal: AbortSignal.timeout(30000) });
  assert.equal(page.status, 200);
});
