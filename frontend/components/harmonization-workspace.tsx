"use client";

import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { Activity, Layers, Satellite } from "lucide-react";
import { ACTIVITY_METHOD, QA_METHOD, activityQuery, api, calendarError, filterError, historyError } from "@/lib/api/client";
import { activitySeries } from "@/lib/api/activity-series";
import type { ActivityCalendarDay, ActivityFilters, DateFilters, ValidationFilters } from "@/lib/api/types";
import { AnalyticsResults, ErrorNote, ExportButton, formatNumber, Pagination, Panel } from "./dashboard-ui";

const defaultScope = { regionPk: "", methodVersion: ACTIVITY_METHOD, validationMethodVersion: QA_METHOD, spatialGridId: "" };
const seriesColors = ["#b35d27", "#3a7d59", "#617ea4", "#a36d99", "#a18a35", "#548a94"];
const tooltipStyle = { fontSize: 11, borderRadius: 4, background: "var(--fl-surface)", color: "var(--fl-ink)", border: "1px solid var(--fl-border)" };

function ActivityHeatmaps({ days, startDate, endDate, selected, onSelect }: {
  days: ActivityCalendarDay[]; startDate: string | null; endDate: string | null;
  selected: string | null; onSelect: (key: string) => void;
}) {
  const versions = [...new Set(days.map((day) => day.method_version))].sort();
  const ordered = [...days].sort((a, b) => a.date.localeCompare(b.date));
  if (!ordered.length) return <div className="empty-state">No corrected daily activity matches this selection.</div>;
  const start = new Date(`${startDate || ordered[0].date}T00:00:00Z`);
  const end = new Date(`${endDate || ordered[ordered.length - 1].date}T00:00:00Z`);
  start.setUTCDate(start.getUTCDate() - start.getUTCDay());
  end.setUTCDate(end.getUTCDate() + 6 - end.getUTCDay());
  const cells: string[] = [];
  for (const day = new Date(start); day <= end; day.setUTCDate(day.getUTCDate() + 1)) cells.push(day.toISOString().slice(0, 10));
  const max = Math.max(1, ...days.map((day) => day.harmonized_activity ?? 0));
  const months = [...new Set(cells.map((day) => day.slice(0, 7)))];
  return <div className="method-calendars">{versions.map((version) => {
    const byDate = new Map(days.filter((day) => day.method_version === version).map((day) => [day.date, day]));
    return <div key={version} className="method-calendar">
      <div className="calendar-toolbar"><strong>Method {version}</strong><span>{startDate} — {endDate}</span></div>
      <div className="calendar">
        <div className="week-labels">{["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"].map((day) => <span key={day}>{day}</span>)}</div>
        <div className="calendar-scroll"><div className="calendar-grid">{cells.map((date) => {
          const item = byDate.get(date);
          const value = item?.harmonized_activity;
          const key = JSON.stringify([date, version]);
          const level = value == null ? "unknown" : value === 0 ? 0 : value / max < .2 ? 1 : value / max < .4 ? 2 : value / max < .7 ? 3 : 4;
          const label = `${date} · ${version}: ${value == null ? "activity unavailable" : `${formatNumber(value, 4)} corrected activity`}`;
          return <button key={date} className={`day-cell heat-${level}${selected === key ? " is-selected" : ""}`} disabled={!item}
            aria-label={label} title={label} aria-pressed={selected === key} onClick={() => onSelect(key)} />;
        })}</div><div className="month-labels">{months.map((month) => <span key={month}>{month}</span>)}</div></div>
      </div>
    </div>;
  })}<div className="heat-legend"><i className="heat-unknown" /><span>Unavailable</span><span>0</span><i className="heat-0" /><i className="heat-1" /><i className="heat-2" /><i className="heat-3" /><i className="heat-4" /><span>{formatNumber(max, 4)}+</span></div></div>;
}

export default function HarmonizationWorkspace({ dates, view, enabled: workspaceEnabled = true, notice }: { dates: DateFilters; view: "harmonization" | "validation" | null; enabled?: boolean; notice?: string | null }) {
  const [draft, setDraft] = useState(defaultScope);
  const [scope, setScope] = useState(defaultScope);
  const [activityPage, setActivityPage] = useState({ key: "", page: 1 });
  const [reportPage, setReportPage] = useState({ key: "", page: 1 });
  const [panels, setPanels] = useState({ calendar: true, trend: true, seasonal: true, records: true, comparison: true, anomalies: true, validation: true });
  function setPanel(key: keyof typeof panels, open: boolean) {
    setPanels((current) => ({ ...current, [key]: open }));
  }
  const [selected, setSelected] = useState<string | null>(null);
  const filters: ActivityFilters = { ...dates, regionPk: scope.regionPk, methodVersion: scope.methodVersion, spatialGridId: scope.spatialGridId };
  const validationFilters: ValidationFilters = { ...dates, regionPk: scope.regionPk, methodVersion: scope.validationMethodVersion };
  const scopeKey = JSON.stringify(filters);
  const validationKey = JSON.stringify(validationFilters);
  const page = activityPage.key === scopeKey ? activityPage.page : 1;
  const validationPage = reportPage.key === validationKey ? reportPage.page : 1;
  const selectionError = filterError(filters) || (!workspaceEnabled ? notice || "Choose available observation dates to load this section." : null);
  const rangeError = calendarError(filters);
  const historicError = historyError(filters);
  const enabled = !selectionError;
  const activityEnabled = enabled && view === "harmonization";
  const validationEnabled = enabled && view === "validation";
  const catalog = useQuery({ queryKey: ["region-catalog"], queryFn: ({ signal }) => api.regionCatalog(signal) });
  const records = useQuery({ queryKey: ["activity-records", filters, page], queryFn: ({ signal }) => api.activity(filters, page, 100, signal), enabled: activityEnabled && panels.records });
  const calendar = useQuery({ queryKey: ["activity-calendar", filters], queryFn: ({ signal }) => api.activityCalendar(filters, signal), enabled: activityEnabled && !rangeError && (panels.calendar || panels.trend) });
  const seasonal = useQuery({ queryKey: ["activity-seasonal", filters], queryFn: ({ signal }) => api.activitySeasonal(filters, signal), enabled: activityEnabled && panels.seasonal });
  const comparison = useQuery({ queryKey: ["activity-comparison", filters], queryFn: ({ signal }) => api.activityComparison(filters, signal), enabled: activityEnabled && !historicError && panels.comparison });
  const anomalies = useQuery({ queryKey: ["activity-anomalies", filters], queryFn: ({ signal }) => api.activityAnomalies(filters, signal), enabled: activityEnabled && !historicError && panels.anomalies });
  const validation = useQuery({ queryKey: ["validation", validationFilters, validationPage], queryFn: ({ signal }) => api.validation(validationFilters, validationPage, 100, signal), enabled: validationEnabled && panels.validation });
  const daily = useMemo(() => calendar.data?.data ?? [], [calendar.data]);
  const chart = useMemo(() => activitySeries(daily), [daily]);
  const selectedDay = daily.find((day) => JSON.stringify([day.date, day.method_version]) === selected);
  const seasonalRows = (seasonal.data?.seasonal ?? []).map((point) => ({ ...point, label: `${point.season_year} ${point.season} · ${point.method_version}` }));
  const activeRegion = catalog.data?.data.find((region) => String(region.id) === scope.regionPk);
  const pendingChanges = JSON.stringify(draft) !== JSON.stringify(scope);
  const activeMethod = view === "validation" ? scope.validationMethodVersion : scope.methodVersion;
  const multiVersion = (calendar.data?.meta.method_versions?.length ?? 0) > 1;
  const draftError = draft.methodVersion.trim().length > 100 || draft.validationMethodVersion.trim().length > 100 ? "Method version must contain at most 100 characters."
    : draft.spatialGridId.trim().length > 255 ? "Grid ID must contain at most 255 characters." : null;

  function applyScope() {
    const next = { regionPk: draft.regionPk, methodVersion: draft.methodVersion.trim(), validationMethodVersion: draft.validationMethodVersion.trim(), spatialGridId: draft.spatialGridId.trim() };
    activityQuery({ ...dates, ...next });
    setDraft(next); setScope(next); setSelected(null);
  }

  return <div hidden={!view} data-view={view ?? undefined} className="product-workspace workspace-view">
    <form className="filter-bar product-filters" aria-label={view === "validation" ? "Validation filters" : "Harmonized activity filters"} onSubmit={(event) => { event.preventDefault(); if (!selectionError && !draftError) applyScope(); }}>
      <div className="filter-bar-top"><span className="filter-bar-label">{view === "validation" ? "VALIDATION FILTERS" : "HARMONIZED ACTIVITY FILTERS"}</span><span className="scope-badge">{activeRegion?.name ?? "All catalog regions"}{activeMethod ? ` · ${activeMethod}` : " · All methods"}</span></div>
      <div className="filters corrected-filters">
        <label className="filter-field"><span>CATALOG REGION</span><select value={draft.regionPk} onChange={(event) => setDraft({ ...draft, regionPk: event.target.value })} disabled={catalog.isLoading || catalog.isError}>
          <option value="">All catalog regions</option>{catalog.data?.data.map((region) => <option key={region.id} value={region.id}>{region.name}{region.country_code ? ` (${region.country_code})` : ""} · {region.slug}</option>)}
        </select></label>
        {view === "harmonization" && <label className="filter-field"><span>ACTIVITY METHOD</span><input value={draft.methodVersion} maxLength={100} placeholder="All activity methods" onChange={(event) => setDraft({ ...draft, methodVersion: event.target.value })} /></label>}
        {view === "validation" && <label className="filter-field"><span>VALIDATION METHOD</span><input value={draft.validationMethodVersion} maxLength={100} placeholder="All validation methods" onChange={(event) => setDraft({ ...draft, validationMethodVersion: event.target.value })} /></label>}
        {view === "harmonization" && <label className="filter-field"><span>SPATIAL GRID</span><input value={draft.spatialGridId} maxLength={255} placeholder="All grids" onChange={(event) => setDraft({ ...draft, spatialGridId: event.target.value })} /></label>}
        <div className="filter-field filter-apply"><button className="btn-primary" type="submit" disabled={!!selectionError || !!draftError}>Apply filters</button></div>
      </div>
      <div className="filter-bar-foot">Uses the date range above. Select a catalog region for corrected activity and QA. Each product uses its own method; validation covers all grids.
        <button className="text-button" type="button" onClick={() => { setDraft(defaultScope); setScope(defaultScope); setSelected(null); }}>Reset product filters</button>
      </div>
      {activeRegion?.description && <p className="scope-description">{activeRegion.description}</p>}
      {pendingChanges && <p className="scope-description" role="status">Filter changes will take effect when you select Apply filters.</p>}
      {(selectionError || draftError) && <p className="filter-error" role="alert">{selectionError || draftError}</p>}
      {catalog.isError && <div className="catalog-error"><ErrorNote error={catalog.error} /><button className="text-button" type="button" onClick={() => catalog.refetch()}>Retry catalog</button></div>}
    </form>

    {view === "harmonization" && <>
    <div className="metrics-grid activity-metrics">
      {[
        { icon: Layers, label: "Corrected grid records", value: records.isLoading ? "…" : records.isError || selectionError ? "Unavailable" : formatNumber(records.data?.pagination.total), detail: "Across corrected activity filters" },
        { icon: Activity, label: "Harmonized activity", value: calendar.isLoading ? "…" : calendar.isError || selectionError || rangeError ? "Unavailable" : multiVersion ? "Choose one method" : formatNumber(calendar.data?.meta.total_harmonized_activity, 4), detail: "Calendar total · fractional hotspot detection index" },
        { icon: Satellite, label: "Source observations", value: multiVersion ? "By method version" : calendar.isError || selectionError || rangeError ? "Unavailable" : `MODIS ${formatNumber(calendar.data?.meta.total_modis_count)} / VIIRS ${formatNumber(calendar.data?.meta.total_viirs_count)}`, detail: "API calendar totals · counts" },
      ].map(({ icon: Icon, label, value, detail }) => <article key={label} className="metric"><div className="metric-header"><Icon size={15} className="metric-icon" /><span className="metric-label">{label}</span></div><strong className="metric-value">{value}</strong><small className="metric-detail">{detail}</small></article>)}
    </div>

    <div className="activity-stack">
      <Panel title="Corrected Activity Calendar" open={panels.calendar} onOpenChange={(open) => setPanel("calendar", open)} eyebrow="SEPARATE RESULTS FOR EACH METHOD VERSION">
        {selectionError || rangeError ? <div className="empty-state">{selectionError || rangeError}</div> : calendar.isLoading ? <div className="loading-box">Loading corrected calendar…</div> : calendar.isError ? <ErrorNote error={calendar.error} /> : <>
          <ActivityHeatmaps days={daily} startDate={calendar.data?.meta.start_date ?? null} endDate={calendar.data?.meta.end_date ?? null} selected={selected} onSelect={setSelected} />
          <div className="calendar-foot" aria-live="polite">{selectedDay ? <>
            <strong>{selectedDay.date} · {selectedDay.method_version}</strong><span>Activity: {formatNumber(selectedDay.harmonized_activity, 4)}</span>
            <span>MODIS: {selectedDay.modis_count} · VIIRS: {selectedDay.viirs_count}</span><span>{selectedDay.grid_records} grid records · Uncertainty: {formatNumber(selectedDay.uncertainty)}</span>
          </> : <span>Select a day to inspect corrected activity and source counts.</span>}</div>
        </>}
        {calendar.data && <p className="panel-note">{calendar.data.meta.aggregation_method}</p>}
        <p className="panel-note">Activity is a fractional hotspot detection index. Unavailable days remain gaps. Uncertainty covers variation in the country correction factor; it excludes clouds, coverage, missed detections, and grid prediction error. Multi-grid uncertainty remains unavailable.</p>
      </Panel>

      <div className="two-col-grid analytics-grid">
        <Panel title="Corrected Daily Trend" open={panels.trend} onOpenChange={(open) => setPanel("trend", open)} eyebrow="ACTIVITY BY METHOD VERSION">
          {selectionError || rangeError ? <div className="empty-state">{selectionError || rangeError}</div> : calendar.isLoading ? <div className="loading-box">Loading corrected trend…</div> : calendar.isError ? <ErrorNote error={calendar.error} /> : !chart.points.length ? <div className="empty-state">No corrected trend data.</div> : <div className="chart product-chart"><ResponsiveContainer width="100%" height="100%"><LineChart data={chart.points}>
            <CartesianGrid stroke="var(--fl-border)" vertical={false} /><XAxis dataKey="date" tick={{ fontSize: 9, fill: "var(--fl-muted)" }} interval="preserveStartEnd" /><YAxis tick={{ fontSize: 10, fill: "var(--fl-muted)" }} width={45} /><Tooltip contentStyle={tooltipStyle} /><Legend wrapperStyle={{ fontSize: 10 }} />
            {chart.versions.map((version, index) => <Line key={version} dataKey={`method_${index}`} name={version} type="linear" stroke={seriesColors[index % seriesColors.length]} strokeWidth={2} connectNulls={false} dot={chart.points.length < 8} />)}
          </LineChart></ResponsiveContainer></div>}
        </Panel>
        <Panel title="Corrected Seasonal Activity" open={panels.seasonal} onOpenChange={(open) => setPanel("seasonal", open)} eyebrow="DJF / MAM / JJA / SON">
          {selectionError ? <div className="empty-state">{selectionError}</div> : seasonal.isLoading ? <div className="loading-box">Loading corrected seasons…</div> : seasonal.isError ? <ErrorNote error={seasonal.error} /> : !seasonalRows.length ? <div className="empty-state">No corrected seasonal data.</div> : <div className="chart product-chart"><ResponsiveContainer width="100%" height="100%"><BarChart data={seasonalRows}>
            <CartesianGrid stroke="var(--fl-border)" vertical={false} /><XAxis dataKey="label" tick={{ fontSize: 9, fill: "var(--fl-muted)" }} /><YAxis tick={{ fontSize: 10, fill: "var(--fl-muted)" }} width={45} /><Tooltip contentStyle={tooltipStyle} /><Bar dataKey="harmonized_activity" name="Corrected activity" fill="#d88b44" radius={[3, 3, 0, 0]} />
          </BarChart></ResponsiveContainer></div>}
          {seasonal.data && <p className="panel-note">{seasonal.data.meta.start_date} — {seasonal.data.meta.end_date} · {seasonal.data.meta.season_method}</p>}
        </Panel>
      </div>

      <Panel title="Harmonized Activity Records" open={panels.records} onOpenChange={(open) => setPanel("records", open)} eyebrow="CORRECTED GRID / DAY DATA" className="table-panel">
        <div className="panel-actions"><p className="panel-note">Stored corrections and uncertainty retain their supplied meaning and units. — means unavailable.</p><ExportButton product="harmonization" filters={filters} label="Export corrected CSV" disabled={!enabled} /></div>
        {selectionError ? <div className="empty-state">{selectionError}</div> : records.isLoading ? <div className="loading-box">Loading corrected records…</div> : records.isError ? <ErrorNote error={records.error} /> : !records.data?.data.length ? <div className="empty-state">No corrected activity records match these filters.</div> : <div className="table-scroll"><table>
          <thead><tr>{["DATE", "REGION", "COUNTRY", "GRID", "METHOD", "MODIS", "VIIRS", "CORRECTED ACTIVITY", "CORRECTION FACTOR", "UNCERTAINTY", "CREATED (UTC)"].map((label) => <th key={label}>{label}</th>)}</tr></thead>
          <tbody>{records.data.data.map((row) => <tr key={row.id}>
            <td>{row.activity_date}</td><td>{catalog.data?.data.find((region) => region.id === row.region_id)?.name ?? (row.region_id == null ? "Unassigned" : `Region ${row.region_id}`)}</td><td>{row.country_code ?? "—"}</td><td>{row.spatial_grid_id ?? "—"}</td><td>{row.method_version}</td><td>{formatNumber(row.modis_count)}</td><td>{formatNumber(row.viirs_count)}</td><td>{formatNumber(row.harmonized_count, 4)}</td><td>{formatNumber(row.correction_factor, 4)}</td><td>{formatNumber(row.uncertainty, 4)}</td><td>{row.created_at}</td>
          </tr>)}</tbody>
        </table></div>}
        {records.data && <Pagination page={page} total={records.data.pagination.total} fetching={records.isFetching} onChange={(next) => setActivityPage({ key: scopeKey, page: next })} label="corrected records" />}
      </Panel>
      <div className="two-col-grid analytics-grid">
        <Panel title="Corrected Historical Comparison" open={panels.comparison} onOpenChange={(open) => setPanel("comparison", open)} eyebrow="MONTHLY BASELINES BY METHOD">
          {selectionError || historicError ? <div className="empty-state">{selectionError || historicError}</div> : <AnalyticsResults kind="comparison" loading={comparison.isLoading} error={comparison.error} result={comparison.data} />}
        </Panel>
        <Panel title="Corrected Activity Anomalies" open={panels.anomalies} onOpenChange={(open) => setPanel("anomalies", open)} eyebrow="ROBUST SCORES BY METHOD">
          {selectionError || historicError ? <div className="empty-state">{selectionError || historicError}</div> : <AnalyticsResults kind="anomalies" loading={anomalies.isLoading} error={anomalies.error} result={anomalies.data} />}
        </Panel>
      </div>
    </div>

    </>}
    {view === "validation" && <>
    <Panel title="Candidate-pair Validation" open={panels.validation} onOpenChange={(open) => setPanel("validation", open)} eyebrow="BACKEND-REPORTED QA" className="table-panel">
      <div className="panel-actions"><p className="panel-note">Validation method: {scope.validationMethodVersion || "All validation methods"}. Uses the selected catalog region and overlapping dates, across all grids. Missing metrics remain unavailable.</p><ExportButton product="validation" filters={validationFilters} label="Export validation CSV" disabled={!enabled} /></div>
      {selectionError ? <div className="empty-state">{selectionError}</div> : validation.isLoading ? <div className="loading-box">Loading validation reports…</div> : validation.isError ? <ErrorNote error={validation.error} /> : !validation.data?.data.length ? <div className="empty-state">No validation reports match these filters. Metrics will appear when reports are available.</div> : <div className="table-scroll"><table>
        <thead><tr>{["METHOD", "REGION", "COUNTRY", "PERIOD START", "PERIOD END", "MAE", "RMSE", "BIAS", "SAMPLE SIZE", "NOTES", "CREATED (UTC)"].map((label) => <th key={label}>{label}</th>)}</tr></thead>
        <tbody>{validation.data.data.map((report) => <tr key={report.id}>
          <td>{report.method_version}</td><td>{catalog.data?.data.find((region) => region.id === report.region_id)?.name ?? (report.region_id == null ? "Unassigned" : `Region ${report.region_id}`)}</td><td>{report.country_code ?? "—"}</td><td>{report.validation_period_start ?? "—"}</td><td>{report.validation_period_end ?? "—"}</td><td>{formatNumber(report.mae, 4)}</td><td>{formatNumber(report.rmse, 4)}</td><td>{formatNumber(report.bias, 4)}</td><td>{formatNumber(report.sample_size, 0)}</td><td className="report-notes">{report.notes ?? "—"}</td><td>{report.created_at}</td>
        </tr>)}</tbody>
      </table></div>}
      {validation.data && <Pagination page={validationPage} total={validation.data.pagination.total} fetching={validation.isFetching} onChange={(next) => setReportPage({ key: validationKey, page: next })} label="validation reports" />}
      <p className="panel-note">Sample size counts validated overlap pairs. These reports summarize candidate-pair QA; their nullable MAE, RMSE, and bias are not held-out 2020 calibration metrics.</p>
    </Panel>
    </>}
  </div>;
}
