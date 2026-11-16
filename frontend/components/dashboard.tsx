"use client";
import dynamic from "next/dynamic";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  Bar, BarChart, CartesianGrid, Line, LineChart,
  ResponsiveContainer, Tooltip, XAxis, YAxis,
} from "recharts";
import {
  Activity, CalendarDays, ChevronLeft,
  ArrowUpRight, ChevronRight, Flame, MapPinned, Menu, Moon, Satellite, Sun,
} from "lucide-react";
import { api, calendarError, filterError, historyError, query } from "@/lib/api/client";
import { availableMonths, dateAvailabilityScope, periodDates, selectableRegions, type PeriodSelection } from "@/lib/api/availability";
import { AnalyticsResults, ErrorNote, ExportButton, Panel } from "./dashboard-ui";
import HarmonizationWorkspace from "./harmonization-workspace";
import FireDetails from "./fire-details";
import WorkspaceSidebar, { workspaceIcons } from "./workspace-sidebar";
import { workspaceViews, workspaceViewFromHash, type WorkspaceView } from "@/lib/workspace-navigation";
import type {
  CalendarDay, Filters,
} from "@/lib/api/types";

const FireMap = dynamic(() => import("./fire-map"), {
  ssr: false,
  loading: () => <div className="map-loading">Loading interactive map…</div>,
});

/* ── constants ──────────────────────────────────────────────── */
const initial: Filters = { region: "", startDate: "", endDate: "", sensor: "ALL" };
const monthNames = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"];

/* ── helpers ────────────────────────────────────────────────── */
function acquiredAt(fire: { acq_date: string; acq_time?: number | null; acq_datetime_utc?: string | null }) {
  if (fire.acq_datetime_utc) return fire.acq_datetime_utc.replace("T", " ").replace("Z", " UTC");
  const time = fire.acq_time == null ? "" : String(fire.acq_time).padStart(4, "0");
  return `${fire.acq_date}${time ? ` ${time.slice(0, 2)}:${time.slice(2)} UTC` : ""}`;
}

function SeasonalAxisTick({ x = 0, y = 0, payload }: { x?: number; y?: number; payload?: { value: string } }) {
  const [season, hemisphere, year] = (payload?.value ?? "").split(" · ");
  return <g transform={`translate(${x},${y})`}>
    <text textAnchor="middle" fill="var(--fl-muted)" fontSize={10}>
      <tspan x={0} dy={12}>{season}</tspan>
      <tspan x={0} dy={14}>{hemisphere}</tspan>
      <tspan x={0} dy={14}>{year}</tspan>
    </text>
  </g>;
}

/* ── small components ───────────────────────────────────────── */
function Metric({
  icon: Icon, label, value, detail,
}: {
  icon: typeof Flame; label: string; value: string; detail: string;
}) {
  return (
    <article className="metric">
      <div className="metric-header">
        <Icon size={15} className="metric-icon" />
        <span className="metric-label">{label}</span>
      </div>
      <strong className="metric-value">{value}</strong>
      <small className="metric-detail">{detail}</small>
    </article>
  );
}

function DarkToggle({ dark, toggle }: { dark: boolean; toggle: () => void }) {
  return (
    <button
      className="dark-toggle"
      onClick={toggle}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      title={dark ? "Light mode" : "Dark mode"}
    >
      {dark ? <Sun size={15} /> : <Moon size={15} />}
    </button>
  );
}

/* ── Calendar heatmap ───────────────────────────────────────── */
function Calendar({
  days, selected, onSelect,
}: {
  days: CalendarDay[];
  selected: CalendarDay | null;
  onSelect: (day: CalendarDay) => void;
}) {
  const byDate = new Map(days.map((d) => [d.date, d]));
  const max    = Math.max(1, ...days.map((d) => d.fire_count));
  const sorted = [...days].sort((a, b) => a.date.localeCompare(b.date));

  if (!sorted.length) return <div className="empty-state">No calendar days available.</div>;
  const start = new Date(sorted[0].date + "T00:00:00Z");
  start.setUTCDate(start.getUTCDate() - start.getUTCDay());
  const end = new Date(sorted[sorted.length - 1].date + "T00:00:00Z");
  end.setUTCDate(end.getUTCDate() + (6 - end.getUTCDay()));

  const cells: Date[] = [];
  for (let d = new Date(start); d <= end; d.setUTCDate(d.getUTCDate() + 1))
    cells.push(new Date(d));

  const months = [...new Set(
    cells.map((d) => d.toLocaleDateString("en", { month: "short", year: "numeric", timeZone: "UTC" })),
  )];

  return (
    <div className="calendar">
      <div className="week-labels">
        {["Sun","Mon","Tue","Wed","Thu","Fri","Sat"].map((l) => (
          <span key={l}>{l}</span>
        ))}
      </div>
      <div className="calendar-scroll">
        <div className="calendar-grid">
          {cells.map((d) => {
            const key   = d.toISOString().slice(0, 10);
            const item  = byDate.get(key);
            const count = item?.fire_count ?? 0;
            const level = count === 0 ? 0
              : count / max < 0.2 ? 1
              : count / max < 0.4 ? 2
              : count / max < 0.7 ? 3 : 4;
            return (
              <button
                key={key}
                title={`${key}: ${count} detections`}
                aria-label={`${key}: ${count} detections`}
                aria-pressed={selected?.date === key}
                disabled={!item || count === 0}
                onClick={() => item && onSelect(item)}
                className={`day-cell heat-${level}${selected?.date === key ? " is-selected" : ""}`}
              />
            );
          })}
        </div>
        <div className="month-labels">
          {months.map((m) => <span key={m}>{m}</span>)}
        </div>
      </div>
    </div>
  );
}

/* ── Dashboard ──────────────────────────────────────────────── */
export default function Dashboard() {
  const [activeView, setActiveView] = useState<WorkspaceView>("overview");
  const [navigationReady, setNavigationReady] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const heading = useRef<HTMLHeadingElement>(null);
  const closeSidebar = useCallback(() => setSidebarOpen(false), []);
  const view = workspaceViews.find((item) => item.id === activeView)!;
  const productView = activeView === "harmonization" || activeView === "validation";
  useEffect(() => {
    const syncView = () => { setActiveView(workspaceViewFromHash(window.location.hash)); setSidebarOpen(false); setNavigationReady(true); };
    syncView();
    window.addEventListener("hashchange", syncView);
    window.addEventListener("popstate", syncView);
    return () => { window.removeEventListener("hashchange", syncView); window.removeEventListener("popstate", syncView); };
  }, []);
  useEffect(() => {
    const desktop = window.matchMedia?.("(min-width: 901px)");
    if (!desktop) return;
    const closeOnDesktop = () => { if (desktop.matches) setSidebarOpen(false); };
    desktop.addEventListener("change", closeOnDesktop);
    return () => desktop.removeEventListener("change", closeOnDesktop);
  }, []);
  function navigate(next: WorkspaceView) {
    setActiveView(next); setSidebarOpen(false);
    setSelectedFireId(null);
    if (window.location.hash !== `#${next}`) window.history.pushState(null, "", `#${next}`);
    window.scrollTo({ top: 0, behavior: "instant" });
    requestAnimationFrame(() => heading.current?.focus({ preventScroll: true }));
  }
  /* dark mode — stored in localStorage, applied as class on <html> */
  const [dark, setDark] = useState(false);

  useEffect(() => {
    const stored = localStorage.getItem("firelens-dark");
    if (stored === "1") { document.documentElement.classList.add("dark"); setDark(true); }
  }, []);

  function toggleDark() {
    const next = !dark;
    setDark(next);
    document.documentElement.classList.toggle("dark", next);
    localStorage.setItem("firelens-dark", next ? "1" : "0");
  }

  /* queries */
  const [scope,       setScope]       = useState(initial);
  const [period, setPeriod] = useState<PeriodSelection & { key: string }>({ key: "", year: "", month: "", day: "" });
  const [page,        setPage]        = useState(1);
  const [selectedDay, setSelectedDay] = useState<CalendarDay | null>(null);
  const [panels, setPanels] = useState({ calendar: true, trend: true, seasonal: true, comparison: true, anomalies: true });
  function setPanel(key: keyof typeof panels, open: boolean) {
    setPanels((current) => ({ ...current, [key]: open }));
  }
  const [selectedFireId, setSelectedFireId] = useState<number | null>(null);
  const [datesOpen, setDatesOpen] = useState(false);
  let scopeError = filterError(scope);
  try { query(scope); } catch (error) { scopeError = error instanceof Error ? error.message : "Invalid filters."; }
  const dateScope = dateAvailabilityScope(scope);
  const availabilityKey = JSON.stringify(dateScope);
  const availability = useQuery({
    queryKey: ["available-periods", dateScope],
    queryFn: ({ signal }) => api.availablePeriods(dateScope, signal),
    enabled: datesOpen && !scopeError,
    staleTime: 5 * 60_000,
  });
  const observedMonths = useMemo(() => availableMonths(availability.data?.data ?? []), [availability.data]);
  const years = [...new Set(observedMonths.map((row) => row.year))];
  const currentPeriod = period.key === availabilityKey;
  const year = currentPeriod && years.includes(period.year) ? period.year : "";
  const months = observedMonths.filter((row) => row.year === year);
  const month = currentPeriod && months.some((row) => row.month === period.month) ? period.month : "";
  const monthFilters = { ...dateScope, ...periodDates({ year, month, day: "" }) };
  const availableCalendar = useQuery({
    queryKey: ["available-days", monthFilters],
    queryFn: ({ signal }) => api.calendar(monthFilters, signal),
    enabled: datesOpen && !scopeError && !!month,
    staleTime: 5 * 60_000,
  });
  const days = (availableCalendar.data?.data ?? [])
    .filter((row) => row.fire_count > 0 && row.date.startsWith(`${year}-${month}-`))
    .map((row) => row.date.slice(8, 10));
  const day = currentPeriod && days.includes(period.day) ? period.day : "";
  const filters: Filters = { ...scope, ...periodDates({ year, month, day }) };
  const selectionError = scopeError;
  const validFilters = !selectionError && navigationReady;
  const calendarRangeError = calendarError(filters);
  const historicalRangeError = historyError(filters);

  const healthQuery  = useQuery({ queryKey: ["health"],   queryFn: ({ signal }) => api.health(signal), refetchInterval: 30_000 });
  const catalog = useQuery({ queryKey: ["region-catalog"], queryFn: ({ signal }) => api.regionCatalog(signal), staleTime: 5 * 60_000 });
  const regionsQuery = useQuery({ queryKey: ["regions"],  queryFn: ({ signal }) => api.regions(signal) });

  const regions = useMemo(() => selectableRegions(catalog.data?.data ?? [], regionsQuery.data?.data ?? []), [catalog.data, regionsQuery.data]);

  function filtersChanged(next: Filters) {
    setScope({ ...next, startDate: "", endDate: "" });
    setPeriod({ key: "", year: "", month: "", day: "" });
    setPage(1); setSelectedDay(null);
  }
  function periodChanged(next: Partial<PeriodSelection>) {
    setPeriod({ key: availabilityKey, year, month, day, ...next });
    setPage(1); setSelectedDay(null);
  }
  function sensorChanged(sensor: Filters["sensor"]) {
    setScope((current) => ({ ...current, sensor }));
    setPage(1); setSelectedDay(null);
  }

  const firesQuery    = useQuery({ queryKey: ["fires", filters, page], queryFn: ({ signal }) => api.fires(filters, page, 100, signal), enabled: validFilters && (activeView === "overview" || activeView === "data") });
  const calendarQuery = useQuery({ queryKey: ["calendar", filters], queryFn: ({ signal }) => api.calendar(filters, signal), enabled: validFilters && activeView === "activity" && !calendarRangeError && (panels.calendar || panels.trend) });
  const seasonal      = useQuery({ queryKey: ["seasonal", filters], queryFn: ({ signal }) => api.seasonal(filters, signal), enabled: validFilters && activeView === "activity" && panels.seasonal });
  const comparison    = useQuery({ queryKey: ["comparison", filters], queryFn: ({ signal }) => api.comparison(filters, signal), enabled: validFilters && activeView === "analytics" && !historicalRangeError && panels.comparison });
  const anomalies     = useQuery({ queryKey: ["anomalies", filters], queryFn: ({ signal }) => api.anomalies(filters, signal), enabled: validFilters && activeView === "analytics" && !historicalRangeError && panels.anomalies });

  const fireResult  = { rows: firesQuery.data?.data ?? [], total: firesQuery.data?.pagination.total };
  const calendar    = useMemo(() => calendarQuery.data?.data ?? [], [calendarQuery.data]);
  const chartDays   = useMemo(() => calendar.map((x) => ({ ...x, label: x.date.slice(5) })), [calendar]);
  const seasonRows  = (seasonal.data?.seasonal ?? []).map((s) => ({ ...s, label: `${s.season_name} · ${s.hemisphere} · ${s.season_year}` }));
  const pages       = fireResult.total ? Math.max(1, Math.ceil(fireResult.total / 100)) : undefined;
  const activeRegion= regions.find((r) => r.id === filters.region);
  const total       = fireResult.total;

  /* shared tooltip style */
  const tooltipStyle = { fontSize: 11, borderRadius: 4 };

  return (
    <div className="dashboard-shell workspace-shell">
      <WorkspaceSidebar activeView={activeView} open={sidebarOpen} onNavigate={navigate} onClose={closeSidebar} />
      <div className="workspace-main">
      <header className="topbar workspace-topbar">
        <button className="sidebar-menu-button" type="button" aria-label="Open navigation" aria-controls="workspace-sidebar" aria-expanded={sidebarOpen} onClick={() => setSidebarOpen(true)}><Menu size={20} /></button>
        <div className="workspace-breadcrumb"><span>Workspace</span><ChevronRight size={13} aria-hidden="true" /><strong>{view.label}</strong></div>
        <div className="top-actions">
          <span className={`api-pill ${healthQuery.isError ? "api-offline" : ""}`}><i />{healthQuery.isSuccess ? "API connected" : healthQuery.isError ? "API unavailable" : "Checking..."}</span>
          <a className="docs-link" href={process.env.NEXT_PUBLIC_API_DOCS_URL || "http://127.0.0.1:8000/docs"} target="_blank" rel="noreferrer">API docs</a>
          <DarkToggle dark={dark} toggle={toggleDark} />
        </div>
      </header>
      <main className="page-content workspace-content" id="top">
        <div className="page-hero">
          <div className="page-hero-text">
            <p className="hero-eyebrow">
              <span className="eyebrow-dot" /> NASA SPACE APPS CAIRO 2026
              <span className="eyebrow-sep">/</span> WILDFIRE INTELLIGENCE
            </p>
            <h1 ref={heading} tabIndex={-1}>{view.title}</h1>
            <p className="hero-sub">
              {view.description}
            </p>
          </div>
          {!productView && <ExportButton filters={filters} disabled={!validFilters} />}
        </div>

        {/* ── Filters ── */}
        <section className="filter-bar" aria-label="Data filters">
          <div className="filter-bar-top">
            <span className="filter-bar-label">{productView ? "SHARED OBSERVATION DATES" : "REGION & AVAILABLE OBSERVATION DATES"}</span>
            <span className={`backend-status ${healthQuery.isError ? "offline" : ""}`}>
              <i />
              {healthQuery.isSuccess ? "Backend reachable" : healthQuery.isError ? "Backend unavailable" : "Checking backend"}
            </span>
          </div>
          <div className="filters observation-filters" hidden={productView}>
            <label className="filter-field">
              <span>REGION</span>
              <select
                value={filters.region}
                onChange={(e) => filtersChanged({ ...filters, region: e.target.value })}
                disabled={!regions.length}
              >
                <option value="">{!regions.length && (catalog.isPending || regionsQuery.isPending) ? "Loading regions…" : "All regions"}</option>
                {regions.map((r) => (
                  <option key={r.id} value={r.id}>{r.name}</option>
                ))}
              </select>
            </label>

            <label className="filter-field">
              <span>SENSOR</span>
              <select
                value={filters.sensor}
                onChange={(e) => sensorChanged(e.target.value as Filters["sensor"])}
              >
                <option value="ALL">All sensors</option>
                <option value="MODIS">MODIS</option>
                <option value="VIIRS">VIIRS</option>
              </select>
            </label>
          </div>
          <details className="bounds-filters" open={datesOpen} onToggle={(event) => setDatesOpen(event.currentTarget.open)}>
            <summary>{year ? "Observation dates · " + filters.startDate + " to " + filters.endDate : "Filter by observation date"}</summary>
            <div className="filters date-filters">
              <label className="filter-field">
                <span>AVAILABLE YEAR</span>
                <select value={year} disabled={!years.length || !!scopeError} onChange={(event) => periodChanged({ year: event.target.value, month: "", day: "" })}>
                  <option value="">{availability.isPending ? "Loading years…" : "All available years"}</option>
                  {years.map((value) => <option key={value} value={value}>{value}</option>)}
                </select>
              </label>
  
              <label className="filter-field">
                <span>AVAILABLE MONTH</span>
                <select value={month} disabled={!year || !!scopeError} onChange={(event) => periodChanged({ month: event.target.value, day: "" })}>
                  <option value="">All available months</option>
                  {[...months].reverse().map((row) => <option key={row.month} value={row.month}>{monthNames[Number(row.month) - 1]}</option>)}
                </select>
              </label>
  
              <label className="filter-field">
                <span>AVAILABLE DAY</span>
                <select value={day} disabled={!month || availableCalendar.isPending || availableCalendar.isError || !days.length} onChange={(event) => periodChanged({ day: event.target.value })}>
                  <option value="">{!month ? "Select a month first" : availableCalendar.isPending ? "Loading days…" : !days.length ? "No available days" : "All available days"}</option>
                  {days.map((value) => <option key={value} value={value}>{year}-{month}-{value}</option>)}
                </select>
              </label>
            </div>
            {availability.isError && <div className="catalog-error"><ErrorNote error={availability.error} /><button className="text-button" onClick={() => availability.refetch()}>Retry available dates</button></div>}
            {availableCalendar.isError && <div className="catalog-error"><ErrorNote error={availableCalendar.error} /><button className="text-button" onClick={() => availableCalendar.refetch()}>Retry available days</button></div>}
          </details>
          <div className="filter-bar-foot">
            {productView ? "Dates are shared across workspaces. Choose the catalog region and method below." : "Available dates cover both sensors. Changing the sensor keeps your region and selected dates."}
            <button className="text-button" onClick={() => productView ? periodChanged({ year: "", month: "", day: "" }) : filtersChanged(initial)}>{productView ? "Clear dates" : "Clear filters"}</button>
          </div>
          {scopeError && <p className="filter-error" role="alert">{scopeError}</p>}
          {!regions.length && catalog.isError && regionsQuery.isError && <div className="catalog-error"><ErrorNote error={catalog.error} /><button className="text-button" onClick={() => { catalog.refetch(); regionsQuery.refetch(); }}>Retry regions</button></div>}
        </section>

        {activeView === "overview" && <section className="workspace-view" aria-label="Overview">
        <div className="metrics-grid">
          <Metric
            icon={Flame}
            label="Fire detections"
            value={
              firesQuery.isLoading ? "…"
              : selectionError || firesQuery.isError ? "Unavailable"
              : total?.toLocaleString()
              ?? "—"
            }
            detail={total === undefined ? "Current page · total not reported" : "Across selected filters"}
          />
          <Metric
            icon={MapPinned}
            label="Geographic region"
            value={activeRegion?.name || "All regions"}
            detail={activeRegion?.id || "No region boundary applied"}
          />
          <Metric
            icon={CalendarDays}
            label="Time period"
            value={
              filters.startDate && filters.endDate
                ? day ? filters.startDate : month ? `${monthNames[Number(month) - 1]} ${year}` : year
                : "All available dates"
            }
            detail={year ? `${filters.startDate} — ${filters.endDate}` : "Dates come from available observations"}
          />
          <Metric
            icon={Satellite}
            label="Sensor coverage"
            value={filters.sensor === "ALL" ? "MODIS + VIIRS" : filters.sensor}
            detail="Satellite detections"
          />
          <Metric
            icon={Activity}
            label="Historical baseline"
            value={comparison.isLoading ? "Checking…" : comparison.data?.status === "ok" ? "Available" : comparison.data?.status === "insufficient_history" ? "Insufficient history" : comparison.data ? "Not available" : "Explore baselines"}
            detail="Comparison depends on backend history"
          />
        </div>

        <div className="overview-workspaces">
          <div className="overview-section-heading"><h2>Explore your workspace</h2><p>Choose a view to start working with your selection.</p></div>
          <div className="workspace-card-grid">{workspaceViews.filter((item) => item.id !== "overview").map((item) => {
            const Icon = workspaceIcons[item.id];
            return <button key={item.id} className="workspace-card" onClick={() => navigate(item.id)} type="button">
              <span className="workspace-card-icon"><Icon size={20} /></span><ArrowUpRight size={17} className="workspace-card-arrow" />
              <strong>{item.label}</strong><span className="workspace-card-description">{item.description}</span>
              <span className="workspace-card-action">Open workspace <ChevronRight size={13} /></span>
            </button>;
          })}</div>
        </div>
        </section>}

        {activeView === "activity" && <section className="workspace-view" aria-label="Fire activity">
        {/* Calendar and Trend — stacked vertically to prevent overlap */}
        <div className="activity-stack">
          <Panel title="Burning Activity Calendar" open={panels.calendar} onOpenChange={(open) => setPanel("calendar", open)} eyebrow="DAILY DETECTIONS" className="calendar-panel" id="calendar">
            <div className="calendar-toolbar">
              <span>Daily detections</span>
              <span>{calendarQuery.data?.meta.start_date ?? filters.startDate} — {calendarQuery.data?.meta.end_date ?? filters.endDate}</span>
            </div>
            {selectionError || calendarRangeError ? (
              <div className="empty-state">{selectionError || calendarRangeError}</div>
            ) : calendarQuery.isLoading ? (
              <div className="loading-box">Loading calendar…</div>
            ) : calendarQuery.isError ? (
              <ErrorNote error={calendarQuery.error} />
            ) : calendar.length === 0 ? (
              <div className="empty-state">No calendar data for this selection.</div>
            ) : (
              <>
                <Calendar days={calendar} selected={selectedDay} onSelect={setSelectedDay} />
                <div className="heat-legend">
                  <span>Fewer</span>
                  <i className="heat-0" /><i className="heat-1" /><i className="heat-2" />
                  <i className="heat-3" /><i className="heat-4" />
                  <span>More</span>
                </div>
                <div className="calendar-foot" aria-live="polite">
                  {selectedDay ? (
                    <>
                      <strong>
                        {new Date(selectedDay.date + "T00:00:00").toLocaleDateString("en", {
                          weekday: "long", month: "long", day: "numeric", year: "numeric",
                        })}
                      </strong>
                      <span>{selectedDay.fire_count.toLocaleString()} detections</span>
                      <button className="text-button" onClick={() => { setDatesOpen(true); periodChanged({ year: selectedDay.date.slice(0, 4), month: selectedDay.date.slice(5, 7), day: selectedDay.date.slice(8, 10) }); navigate("data"); }}>View this day&apos;s detections</button>
                    </>
                  ) : (
                    <span>Select a day to view detection count</span>
                  )}
                </div>
              </>
            )}
          </Panel>

          <Panel title="Daily Activity Trend" open={panels.trend} onOpenChange={(open) => setPanel("trend", open)} eyebrow="OBSERVED OVER TIME" className="trend-panel">
            {selectionError || calendarRangeError ? (
              <div className="empty-state">{selectionError || calendarRangeError}</div>
            ) : calendarQuery.isLoading ? (
              <div className="loading-box">Loading trend…</div>
            ) : calendarQuery.isError ? (
              <ErrorNote error={calendarQuery.error} />
            ) : chartDays.length === 0 ? (
              <div className="empty-state">No trend data available.</div>
            ) : (
              <div className="chart">
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={chartDays}>
                    <CartesianGrid stroke="var(--fl-border)" vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 10, fill: "var(--fl-muted)" }} interval="preserveStartEnd" />
                    <YAxis tick={{ fontSize: 10, fill: "var(--fl-muted)" }} width={38} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Line type="monotone" dataKey="fire_count" name="Detections" stroke="#a95420" strokeWidth={2} dot={false} activeDot={{ r: 4 }} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}
          </Panel>
        </div>


          <Panel title="Seasonal Activity" open={panels.seasonal} onOpenChange={(open) => setPanel("seasonal", open)} eyebrow="HEMISPHERE-AWARE SUMMARY" className="season-panel">
            {selectionError ? (
              <div className="empty-state">{selectionError}</div>
            ) : seasonal.isLoading ? (
              <div className="loading-box">Loading seasonal data…</div>
            ) : seasonal.isError ? (
              <ErrorNote error={seasonal.error} />
            ) : !seasonRows.length ? (
              <div className="empty-state">Seasonal breakdown not available.</div>
            ) : (
              <div className="seasonal-chart-scroll" role="region" aria-label="Seasonal activity chart" tabIndex={0}>
              <div className="chart" style={{ minWidth: Math.max(360, seasonRows.length * 104 + 80) }}>
                <ResponsiveContainer width="100%" height="100%">
                  <BarChart data={seasonRows as Array<Record<string, unknown>>} margin={{ top: 8, right: 16, bottom: 4, left: 0 }}>
                    <CartesianGrid stroke="var(--fl-border)" vertical={false} />
                    <XAxis dataKey="label" tick={<SeasonalAxisTick />} interval={0} height={64} tickMargin={8} tickLine={false} />
                    <YAxis tick={{ fontSize: 10, fill: "var(--fl-muted)" }} width={64} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="fire_count" name="Detections" fill="#d88b44" radius={[3, 3, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              </div>
            )}
            <p className="panel-note">Season labels and totals are provided by the API.</p>
          </Panel>        </section>}

        {activeView === "map" && <section className="workspace-view" aria-label="Fire map">
        <div className="map-view">
          <Panel title="Fire Activity Map" eyebrow="GEOSPATIAL DISTRIBUTION" className="map-panel">
            {selectionError ? (
              <div className="empty-state">{selectionError}</div>
            ) : (
              <FireMap filters={filters} dark={dark} />
            )}
          </Panel>


        </div>

        </section>}

        {activeView === "analytics" && <section className="workspace-view" aria-label="Historical analytics">
        <div className="two-col-grid analytics-grid">
          <Panel title="Historical Comparison" open={panels.comparison} onOpenChange={(open) => setPanel("comparison", open)} eyebrow="OBSERVED VS BASELINE">
            {selectionError || historicalRangeError ? <div className="empty-state">{selectionError || historicalRangeError}</div> : <AnalyticsResults kind="comparison" loading={comparison.isLoading} error={comparison.error} result={comparison.data} />}
          </Panel>
          <Panel title="Anomaly Analysis" open={panels.anomalies} onOpenChange={(open) => setPanel("anomalies", open)} eyebrow="SEVERITY & SCORES">
            {selectionError || historicalRangeError ? <div className="empty-state">{selectionError || historicalRangeError}</div> : <AnalyticsResults kind="anomalies" loading={anomalies.isLoading} error={anomalies.error} result={anomalies.data} />}
          </Panel>
        </div>

        </section>}

        {activeView === "data" && <section className="workspace-view" aria-label="Detection records">
        <Panel title="Raw Fire Observations" eyebrow="STANDARDIZED SATELLITE DETECTIONS" className="table-panel">
          {selectionError ? (
            <div className="empty-state">{selectionError}</div>
          ) : firesQuery.isLoading ? (
            <div className="loading-box">Loading records…</div>
          ) : firesQuery.isError ? (
            <ErrorNote error={firesQuery.error} />
          ) : fireResult.rows.length === 0 ? (
            <div className="empty-state">No detections match the selected filters.</div>
          ) : (
            <>
              <div className="table-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>ACQUIRED (UTC)</th>
                      <th>SENSOR</th>
                      <th>SATELLITE</th>
                      <th>LATITUDE</th>
                      <th>LONGITUDE</th>
                      <th>CONFIDENCE</th>
                      <th>COUNTRY</th>
                      <th>GRID ID</th>
                      <th>DETAILS</th>
                    </tr>
                  </thead>
                  <tbody>
                    {fireResult.rows.map((f, i) => (
                      <tr key={f.id ?? i}>
                        <td>{acquiredAt(f)}</td>
                        <td>{f.sensor      || "—"}</td>
                        <td>{f.satellite   || "—"}</td>
                        <td>{Number.isFinite(f.latitude)  ? f.latitude.toFixed(4)  : "—"}</td>
                        <td>{Number.isFinite(f.longitude) ? f.longitude.toFixed(4) : "—"}</td>
                        <td>{f.confidence  ?? "—"}</td>
                        <td>{f.country_name || f.country_code || "—"}</td>
                        <td>{f.spatial_grid_id || "—"}</td>
                        <td><button className="text-button" onClick={() => setSelectedFireId(f.id)}>View #{f.id}</button></td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <div className="pagination">
                <span>
                  Page {page}{pages ? ` of ${pages}` : ""}
                  {total !== undefined ? ` · ${total.toLocaleString()} records` : ""}
                </span>
                <div>
                  <button
                    aria-label="Previous page"
                    disabled={page <= 1 || firesQuery.isFetching}
                    onClick={() => setPage((p) => Math.max(1, p - 1))}
                  >
                    <ChevronLeft size={16} />
                  </button>
                  <button
                    aria-label="Next page"
                    disabled={fireResult.rows.length < 100 || (!!pages && page >= pages) || firesQuery.isFetching}
                    onClick={() => setPage((p) => p + 1)}
                  >
                    <ChevronRight size={16} />
                  </button>
                </div>
              </div>
            </>
          )}
        </Panel>

        <Panel title="Raw Observation Export" eyebrow="ALL MATCHING DETECTIONS">
          <div className="panel-actions"><p className="panel-note">Download all raw detections matching the country, sensor, and date filters, regardless of map or table pagination.</p><ExportButton filters={filters} label="Export raw CSV" disabled={!validFilters} /></div>
        </Panel>

        </section>}

        <HarmonizationWorkspace view={activeView === "harmonization" || activeView === "validation" ? activeView : null} dates={{ startDate: filters.startDate, endDate: filters.endDate }} enabled={validFilters} notice={selectionError} />
        {selectedFireId != null && <FireDetails id={selectedFireId} onClose={() => setSelectedFireId(null)} />}

        <footer className="footer">
          <span>FIRELENS <i /> NASA SPACE APPS CAIRO 2026</span>
          <span>Scientific results reflect the connected FastAPI dataset.</span>
        </footer>
      </main>
      </div>
    </div>
  );
}
