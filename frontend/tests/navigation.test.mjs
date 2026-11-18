import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { test } from "node:test";
import { act, createElement as h, StrictMode } from "react";
import { JSDOM } from "jsdom";
import ts from "typescript";

const require = createRequire(import.meta.url);
const project = fileURLToPath(new URL("../", import.meta.url));
const delay = () => new Promise((done) => setTimeout(done, 20));
async function waitFor(check) {
  const deadline = Date.now() + 2000;
  while (!check() && Date.now() < deadline) await act(delay);
  assert.ok(check(), "Expected launch state before timeout");
}

async function mount(hash = "", { landing = false, apiGate } = {}) {
  const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', { url: `http://localhost/${hash}`, pretendToBeVisual: true });
  dom.window.scrollTo = () => {};
  dom.window.HTMLDialogElement.prototype.showModal = function () { this.open = true; this.querySelector("button")?.focus(); };
  dom.window.HTMLDialogElement.prototype.close = function () { this.open = false; };
  const globals = { window: dom.window, self: dom.window, document: dom.window.document, Element: dom.window.Element, HTMLElement: dom.window.HTMLElement, localStorage: dom.window.localStorage, requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window), IS_REACT_ACT_ENVIRONMENT: true };
  const saved = new Map(Object.keys(globals).map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const [key, value] of Object.entries(globals)) Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
  const calls = [];
  const prefetchedRoutes = [];
  const pushedRoutes = [];
  const router = { prefetch: (path) => prefetchedRoutes.push(path), push: (path) => pushedRoutes.push(path) };
  const catalog = [{ id: 17, country_code: "EGY", name: "Egypt", slug: "egypt" }];
  const history = { status: "insufficient_history", message: "More history is required.", data: [], meta: { observed_start_date: "2020-01-01", observed_end_date: "2020-12-31", available_prior_years: 2, required_prior_years: 3 } };
  const mocks = {
    health: () => ({ status: "ok" }),
    regionCatalog: () => ({ data: catalog, total: 1 }),
    regions: () => ({ data: [{ id: "EGY", country_code: "EGY", name: "Egypt", hotspot_count: 201 }], total: 1 }),
    availablePeriods: () => ({ data: [{ year: 2019, month: 7, fire_count: 20 }, { year: 2020, month: 1, fire_count: 30 }] }),
    fires: (filters, page = 1, limit = 100) => ({ data: Array.from({ length: Math.max(0, Math.min(limit, 201 - (page - 1) * limit)) }, (_, index) => ({ id: (page - 1) * limit + index + 1, latitude: 30, longitude: 31, acq_date: filters.startDate || "2020-01-15", sensor: "MODIS", confidence: "high", country_code: "EGY" })), pagination: { total: 201, limit, offset: (page - 1) * limit } }),
    calendar: (filters) => ({ status: "ok", data: [{ date: `${(filters.startDate || "2020-01-01").slice(0, 7)}-15`, fire_count: 3 }], meta: { start_date: filters.startDate || "2020-01-01", end_date: filters.endDate || "2020-01-31", total_fires: 3 } }),
    seasonal: () => ({ status: "ok", data: [], seasonal: [] }),
    comparison: () => history,
    anomalies: () => history,
    activity: () => ({ status: "ok", data: [], pagination: { limit: 100, offset: 0, total: 0 } }),
    activityCalendar: () => ({ status: "ok", data: [], meta: { method_versions: [], total_harmonized_activity: null } }),
    activitySeasonal: () => ({ status: "ok", data: [], seasonal: [], meta: {} }),
    activityComparison: () => history,
    activityAnomalies: () => history,
    validation: () => ({ status: "ok", data: [], pagination: { limit: 100, offset: 0, total: 0 } }),
  };
  const api = Object.fromEntries(Object.entries(mocks).map(([name, implementation]) => [name, async (...args) => { calls.push({ name, args }); if (apiGate) await (typeof apiGate === "function" ? apiGate(name) : apiGate); return implementation(...args); }]));
  const modules = new Map();
  function load(filename) {
    if (modules.has(filename)) return modules.get(filename).exports;
    const module = { exports: {} };
    modules.set(filename, module);
    const output = ts.transpileModule(readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
    function localRequire(id) {
      if (id === "next/navigation") return { useRouter: () => router };
      if (id === "next/link") return ({ href, children, ...props }) => h("a", { href, ...props }, children);
      if (id === "./fire-map") return { default: () => null };
      if (id === "next/dynamic") return () => ({ filters }) => {
        const { useInfiniteQuery } = require("@tanstack/react-query");
        const { dashboardQueries } = load(resolve(project, "lib/dashboard-queries.ts"));
        const result = useInfiniteQuery(dashboardQueries.map(filters));
        return h("div", { "data-testid": "fire-map" }, `Map: ${result.data?.pages[0]?.data.length ?? 0}`);
      };
      if (id === "recharts") return new Proxy({}, { get: () => ({ children }) => h("div", null, children) });
      if (!id.startsWith(".") && !id.startsWith("@/")) return require(id);
      const target = id.startsWith("@/") ? resolve(project, id.slice(2)) : resolve(dirname(filename), id);
      const source = [target, `${target}.tsx`, `${target}.ts`].find((candidate) => existsSync(candidate));
      assert.ok(source, `Cannot resolve ${id}`);
      return load(source);
    }
    new Function("require", "module", "exports", output)(localRequire, module, module.exports);
    if (filename === resolve(project, "lib/api/client.ts")) module.exports.api = api;
    return module.exports;
  }
  const Dashboard = load(resolve(project, "components/dashboard.tsx")).default;
  const Preloader = load(resolve(project, "components/dashboard-preloader.tsx")).default;
  const LandingPage = load(resolve(project, "components/landing-page.tsx")).default;
  const { dashboardCacheOptions, preloadDashboardData } = load(resolve(project, "lib/dashboard-queries.ts"));
  const { QueryClient, QueryClientProvider } = require("@tanstack/react-query");
  const { createRoot } = require("react-dom/client");
  const client = new QueryClient({ defaultOptions: { queries: { ...dashboardCacheOptions, retry: false } } });
  const root = createRoot(dom.window.document.getElementById("app"));
  async function showLanding() {
    await act(async () => root.render(h(QueryClientProvider, { client }, h(StrictMode, null, h(Preloader), h(LandingPage)))));
    await act(delay);
  }
  async function showDashboard() {
    await act(async () => root.render(h(QueryClientProvider, { client }, h(Dashboard))));
    await act(delay);
  }
  await (landing ? showLanding() : showDashboard());
  const document = dom.window.document;
  const select = (label) => [...document.querySelectorAll("label")].find((node) => node.querySelector("span")?.textContent === label)?.querySelector("select");
  async function change(label, value) {
    const element = select(label);
    assert.ok(element, label);
    await act(async () => { element.value = value; element.dispatchEvent(new dom.window.Event("change", { bubbles: true })); });
    await act(delay);
  }
  async function navigate(view) {
    await act(async () => document.querySelector(`.sidebar-nav a[href="#${view}"]`).click());
    await act(delay);
  }
  return {
    dom, document, calls, select, change, navigate, client, prefetchedRoutes, pushedRoutes, showLanding, showDashboard,
    preload: () => preloadDashboardData(client),
    async close() {
      await act(async () => root.unmount());
      client.clear();
      dom.window.close();
      for (const [key, descriptor] of saved) {
        if (descriptor) Object.defineProperty(globalThis, key, descriptor);
        else delete globalThis[key];
      }
    },
  };
}

test("landing warms every default workspace once and cached data survives navigation and elapsed time", async () => {
  const app = await mount("", { landing: true });
  try {
    assert.deepEqual(app.prefetchedRoutes, ["/dashboard"]);
    assert.equal(app.calls.length, 16, "Strict Mode must not duplicate preload requests");
    assert.equal(new Set(app.calls.map(({ name }) => name)).size, 15, "Includes all products and separate map/table pages");
    assert.equal(app.preload(), app.preload(), "Repeated landing visits share one preload promise");
    for (const { args } of app.calls) {
      const filters = args[0];
      if (filters && !(filters instanceof AbortSignal)) {
        assert.equal(filters.startDate, "");
        assert.equal(filters.endDate, "");
        if ("region" in filters) { assert.equal(filters.region, ""); assert.equal(filters.sensor, "ALL"); }
        if ("regionPk" in filters) assert.equal(filters.regionPk, "");
      }
    }
    // Move successful results beyond both former expiry times without waiting.
    for (const query of app.client.getQueryCache().getAll()) {
      app.client.setQueryData(query.queryKey, query.state.data, { updatedAt: Date.now() - 10 * 60_000 });
      assert.equal(query.gcTime, Infinity);
    }
    await app.showDashboard();
    assert.equal(app.select("REGION").value, "");
    for (const view of ["activity", "analytics", "data", "harmonization", "validation", "map"]) await app.navigate(view);
    assert.match(app.document.querySelector('[data-testid="fire-map"]').textContent, /Map: 201/);
    await app.showLanding();
    await app.showDashboard();
    assert.equal(app.calls.length, 16, "Returning to either page must reuse completed results");
    assert.deepEqual(app.prefetchedRoutes, ["/dashboard"], "Returning must not restart route prefetching");

    await app.navigate("data");
    await app.change("REGION", "EGY");
    assert.equal(app.calls.length, 17, "A new selection still loads its own data");
    assert.equal(app.calls.at(-1).args[0].region, "EGY");
    await app.change("REGION", "");
    assert.equal(app.calls.length, 17, "Restoring the default selection reuses its original data");
  } finally { await app.close(); }
});

test("opening the dashboard during preload shares its in-flight default request", async () => {
  let release;
  const apiGate = new Promise((done) => { release = done; });
  const app = await mount("", { landing: true, apiGate });
  try {
    await app.showDashboard();
    assert.equal(app.calls.length, 16);
    await act(async () => { release(); await app.preload(); });
    await act(delay);
    assert.match(app.document.querySelector(".metric-value").textContent, /201/);
    assert.equal(app.calls.length, 16);
  } finally { release(); await app.close(); }
});

test("an early launch shows actual progress, then opens the requested dashboard view once", async () => {
  let release;
  const pending = new Promise((done) => { release = done; });
  const app = await mount("", { landing: true, apiGate: (name) => name === "calendar" ? pending : undefined });
  try {
    assert.equal(app.document.querySelector("dialog"), null, "Background preload must stay unobtrusive");
    const link = app.document.querySelector('a[href="/dashboard#map"]');
    await act(async () => link.click());
    const dialog = app.document.querySelector("dialog");
    assert.ok(dialog.open);
    assert.match(dialog.textContent, /Launching your dashboard/);
    assert.equal(app.document.body.style.overflow, "hidden");
    assert.equal(app.document.activeElement, dialog.querySelector("button"));
    const progress = dialog.querySelector('[role="progressbar"]');
    assert.equal(progress.getAttribute("aria-valuenow"), "0", "Every launch starts with an empty bar");
    await waitFor(() => progress.getAttribute("aria-valuenow") === "94");
    assert.deepEqual(app.pushedRoutes, [], "Navigation must wait for preload completion");
    await act(async () => { release(); await app.preload(); });
    await waitFor(() => progress.getAttribute("aria-valuenow") === "100");
    await waitFor(() => app.pushedRoutes.length === 1);
    assert.deepEqual(app.pushedRoutes, ["/dashboard#map"]);
    assert.equal(app.calls.length, 16, "Waiting for launch must not duplicate API calls");
    await app.showDashboard();
    assert.equal(app.document.querySelector("dialog"), null);
    assert.equal(app.document.body.style.overflow, "");
  } finally { release(); await app.close(); }
});

test("a fully preloaded dashboard still shows a quick fill before navigating", async () => {
  const app = await mount("", { landing: true });
  try {
    await act(async () => { await app.preload(); });
    const event = new app.dom.window.MouseEvent("click", { bubbles: true, cancelable: true });
    await act(async () => app.document.querySelector('a[href="/dashboard"]').dispatchEvent(event));
    assert.equal(event.defaultPrevented, true);
    assert.ok(app.document.querySelector("dialog").open);
    const progress = app.document.querySelector('[role="progressbar"]');
    assert.equal(progress.getAttribute("aria-valuenow"), "0");
    assert.deepEqual(app.pushedRoutes, []);
    await waitFor(() => Number(progress.getAttribute("aria-valuenow")) > 0);
    assert.ok(Number(progress.getAttribute("aria-valuenow")) < 100, "The bar visibly fills between zero and completion");
    assert.deepEqual(app.pushedRoutes, []);
    await waitFor(() => progress.getAttribute("aria-valuenow") === "100");
    assert.deepEqual(app.pushedRoutes, [], "Navigation waits for the final fill transition");
    await waitFor(() => app.pushedRoutes.length === 1);
    assert.deepEqual(app.pushedRoutes, ["/dashboard"]);
    assert.equal(app.calls.length, 16, "Replaying the bar must reuse preloaded data");
  } finally { await app.close(); }
});

test("launch can be cancelled with its button or Escape while preload continues", async () => {
  let release;
  const apiGate = new Promise((done) => { release = done; });
  const app = await mount("", { landing: true, apiGate });
  try {
    const link = app.document.querySelector('a[href="/dashboard"]');
    link.focus();
    await act(async () => link.click());
    await act(async () => app.document.querySelector("dialog button").click());
    assert.equal(app.document.querySelector("dialog"), null);
    assert.equal(app.document.body.style.overflow, "");
    assert.equal(app.document.activeElement, link);
    await act(async () => link.click());
    await act(async () => app.document.querySelector("dialog").dispatchEvent(new app.dom.window.Event("cancel", { cancelable: true })));
    assert.equal(app.document.querySelector("dialog"), null);
    await act(async () => { release(); await app.preload(); });
    await act(delay);
    assert.deepEqual(app.pushedRoutes, [], "Cancelled launches must never navigate later");
    assert.equal(app.calls.length, 16);
  } finally { release(); await app.close(); }
});

test("modified clicks keep browser navigation behavior and API failures do not trap the launch", async () => {
  let release;
  const pending = new Promise((done) => { release = done; });
  const app = await mount("", { landing: true, apiGate: async () => { await pending; throw new Error("Backend unavailable"); } });
  try {
    const link = app.document.querySelector('a[href="/dashboard"]');
    for (const modifiers of [{ ctrlKey: true }, { metaKey: true }, { shiftKey: true }, { altKey: true }]) {
      const event = new app.dom.window.MouseEvent("click", { bubbles: true, cancelable: true, ...modifiers });
      await act(async () => link.dispatchEvent(event));
      assert.equal(event.defaultPrevented, false);
      assert.equal(app.document.querySelector("dialog"), null);
    }
    await act(async () => link.click());
    await act(async () => { release(); await app.preload(); });
    await waitFor(() => app.pushedRoutes.length === 1);
    assert.deepEqual(app.pushedRoutes, ["/dashboard"], "Failed requests settle so the workspace can show its retry controls");
  } finally { release(); await app.close(); }
});

test("sidebar switches related views and preserves raw dates, sensor, and product region", async () => {
  const app = await mount();
  try {
    assert.equal(app.document.querySelectorAll(".sidebar-nav a").length, 7);
    assert.equal(app.document.querySelector("h1").textContent, "Workspace overview");
    assert.equal(app.calls.some((call) => call.name === "activity" || call.name === "calendar" || call.name === "validation"), false);
    await app.change("REGION", "EGY");
    const details = app.document.querySelector(".date-filters").closest("details");
    await act(async () => { details.open = true; details.dispatchEvent(new app.dom.window.Event("toggle")); });
    await act(delay);
    await app.change("AVAILABLE YEAR", "2019");
    await app.change("AVAILABLE MONTH", "07");
    await app.change("AVAILABLE DAY", "15");
    await app.change("SENSOR", "VIIRS");
    await app.navigate("activity");
    assert.ok(app.document.querySelector('.workspace-view[aria-label="Fire activity"]'));
    assert.equal(app.document.querySelector(".map-view"), null);
    assert.ok(app.document.querySelector(".season-panel"));
    await app.navigate("data");
    assert.equal(app.select("REGION").value, "EGY");
    assert.equal(app.select("SENSOR").value, "VIIRS");
    assert.equal(app.select("AVAILABLE YEAR").value, "2019");
    assert.equal(app.select("AVAILABLE MONTH").value, "07");
    assert.equal(app.select("AVAILABLE DAY").value, "15");
    assert.equal(app.dom.window.location.hash, "#data");
    assert.equal(app.document.querySelector('.sidebar-link[aria-current="page"]').getAttribute("href"), "#data");
    await act(async () => app.document.querySelector('[aria-label="Next page"]').click());
    await act(delay);
    assert.match(app.document.querySelector(".pagination").textContent, /Page 2 of 3/);
    await app.navigate("harmonization");
    await app.change("CATALOG REGION", "17");
    await act(async () => app.document.querySelector('.product-filters button[type="submit"]').click());
    await act(delay);
    await app.navigate("validation");
    assert.equal(app.select("CATALOG REGION").value, "17");
    assert.ok([...app.document.querySelectorAll("h2")].some((node) => node.textContent.includes("Candidate-pair Validation")));
    assert.equal(app.select("ACTIVITY METHOD"), undefined);
    assert.equal(app.calls.filter((call) => call.name === "validation").at(-1).args[0].regionPk, "17");
    await app.navigate("map");
    assert.ok(app.document.querySelector('[data-testid="fire-map"]'));
    await app.navigate("harmonization");
    assert.equal(app.select("CATALOG REGION").value, "17");
    assert.equal(app.select("AVAILABLE DAY").value, "15");
    await app.navigate("data");
    assert.match(app.document.querySelector(".pagination").textContent, /Page 2 of 3/);
  } finally { await app.close(); }
});

test("direct sidebar URLs and browser navigation activate only their related API requests", async () => {
  const app = await mount("#validation");
  try {
    assert.equal(app.document.querySelector("h1").textContent, "Validation reports");
    assert.ok(app.calls.some((call) => call.name === "validation"));
    assert.equal(app.calls.some((call) => ["fires", "activity", "activityCalendar", "comparison"].includes(call.name)), false);
    await act(async () => {
      app.dom.window.history.replaceState(null, "", "#analytics");
      app.dom.window.dispatchEvent(new app.dom.window.PopStateEvent("popstate"));
    });
    await act(delay);
    assert.equal(app.document.querySelector("h1").textContent, "Historical analytics");
    assert.ok(app.calls.some((call) => call.name === "comparison"));
    assert.ok(app.calls.some((call) => call.name === "anomalies"));
  } finally { await app.close(); }
});

test("mobile navigation opens, confines keyboard focus, and closes with Escape", async () => {
  const app = await mount();
  try {
    const menu = app.document.querySelector('[aria-label="Open navigation"]');
    menu.focus();
    await act(async () => menu.click());
    assert.equal(menu.getAttribute("aria-expanded"), "true");
    assert.equal(app.document.body.style.overflow, "hidden");
    const last = app.document.querySelector('.sidebar-home-link');
    last.focus();
    await act(async () => app.document.dispatchEvent(new app.dom.window.KeyboardEvent("keydown", { key: "Tab", bubbles: true, cancelable: true })));
    assert.equal(app.document.activeElement, app.document.querySelector(".sidebar-brand-row a"));
    await act(async () => app.document.dispatchEvent(new app.dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true, cancelable: true })));
    assert.equal(menu.getAttribute("aria-expanded"), "false");
    assert.equal(app.document.body.style.overflow, "");
    assert.equal(app.document.activeElement, menu);
  } finally { await app.close(); }
});

test("landing page navigation correctly maps and scrolls to corresponding sections", async () => {
  const dom = new JSDOM('<!doctype html><html><body><div id="app"></div></body></html>', { url: "http://localhost/", pretendToBeVisual: true });
  const scrollCalls = [];
  dom.window.scrollTo = (options) => { scrollCalls.push(options); };
  const globals = { window: dom.window, self: dom.window, document: dom.window.document, HTMLElement: dom.window.HTMLElement, localStorage: dom.window.localStorage, requestAnimationFrame: dom.window.requestAnimationFrame.bind(dom.window), IS_REACT_ACT_ENVIRONMENT: true };
  const saved = new Map(Object.keys(globals).map((key) => [key, Object.getOwnPropertyDescriptor(globalThis, key)]));
  for (const [key, value] of Object.entries(globals)) Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });

  const modules = new Map();
  function load(filename) {
    if (modules.has(filename)) return modules.get(filename).exports;
    const module = { exports: {} };
    modules.set(filename, module);
    const output = ts.transpileModule(readFileSync(filename, "utf8"), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, esModuleInterop: true } }).outputText;
    function localRequire(id) {
      if (!id.startsWith(".") && !id.startsWith("@/")) return require(id);
      const target = id.startsWith("@/") ? resolve(project, id.slice(2)) : resolve(dirname(filename), id);
      const source = [target, `${target}.tsx`, `${target}.ts`].find((candidate) => existsSync(candidate));
      assert.ok(source, `Cannot resolve ${id}`);
      return load(source);
    }
    new Function("require", "module", "exports", output)(localRequire, module, module.exports);
    return module.exports;
  }

  const LandingPage = load(resolve(project, "components/landing-page.tsx")).default;
  const { createRoot } = require("react-dom/client");
  const root = createRoot(dom.window.document.getElementById("app"));
  try {
    await act(async () => root.render(h(LandingPage)));
    await act(delay);

    const doc = dom.window.document;
    // Verify target sections exist
    assert.ok(doc.getElementById("mission"));
    assert.ok(doc.getElementById("explore"));
    assert.ok(doc.getElementById("workflow"));

    // Verify header nav mappings
    const headerNavLinks = [...doc.querySelectorAll(".landing-nav a")];
    assert.equal(headerNavLinks.length, 3);
    assert.equal(headerNavLinks[0].getAttribute("href"), "#mission");
    assert.equal(headerNavLinks[0].textContent, "The mission");
    assert.equal(headerNavLinks[1].getAttribute("href"), "#explore");
    assert.equal(headerNavLinks[1].textContent, "Explore the data");
    assert.equal(headerNavLinks[2].getAttribute("href"), "#workflow");
    assert.equal(headerNavLinks[2].textContent, "How it works");

    // Verify footer nav mappings
    const footerNavLinks = [...doc.querySelectorAll(".landing-footer nav a")];
    const footerSectionLinks = footerNavLinks.filter((a) => a.getAttribute("href")?.startsWith("#"));
    assert.equal(footerSectionLinks.length, 3);
    assert.equal(footerSectionLinks[0].getAttribute("href"), "#mission");
    assert.equal(footerSectionLinks[1].getAttribute("href"), "#explore");
    assert.equal(footerSectionLinks[2].getAttribute("href"), "#workflow");

    // Verify observation strip mappings
    const stripLinks = [...doc.querySelectorAll(".landing-observation-strip a")];
    assert.equal(stripLinks.length, 3);
    assert.equal(stripLinks[0].getAttribute("href"), "#mission");
    assert.equal(stripLinks[1].getAttribute("href"), "#explore");
    assert.equal(stripLinks[2].getAttribute("href"), "#workflow");

    // Click "Explore the data" nav link and verify smooth scroll & hash update
    await act(async () => headerNavLinks[1].click());
    await act(delay);
    assert.equal(dom.window.location.hash, "#explore");
    assert.ok(scrollCalls.length > 0);
    assert.equal(scrollCalls.at(-1).behavior, "smooth");

    // Click "The mission" nav link and verify smooth scroll & hash update
    await act(async () => headerNavLinks[0].click());
    await act(delay);
    assert.equal(dom.window.location.hash, "#mission");
    assert.equal(scrollCalls.at(-1).behavior, "smooth");

    // Click "How it works" nav link and verify smooth scroll & hash update
    await act(async () => headerNavLinks[2].click());
    await act(delay);
    assert.equal(dom.window.location.hash, "#workflow");
    assert.equal(scrollCalls.at(-1).behavior, "smooth");
  } finally {
    await act(async () => root.unmount());
    dom.window.close();
    for (const [key, descriptor] of saved) {
      if (descriptor) Object.defineProperty(globalThis, key, descriptor);
      else delete globalThis[key];
    }
  }
});
