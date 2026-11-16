"use client";

import { useId, useState } from "react";
import { ArrowDownToLine, ChevronDown, ChevronLeft, ChevronRight } from "lucide-react";
import { activityQuery, query } from "@/lib/api/client";
import type { ActivityFilters, ActivityAnomalyResult, ActivityComparisonResult, AnomalyResult, ComparisonResult, Filters, ValidationFilters } from "@/lib/api/types";

export function formatNumber(value: number | null | undefined, digits = 2) {
  return value == null ? "—" : value.toLocaleString("en", { maximumFractionDigits: digits });
}

export function Panel({ title, eyebrow, children, className = "", id, open, onOpenChange }: {
  title: string; eyebrow?: string; children: React.ReactNode; className?: string; id?: string;
  open?: boolean; onOpenChange?: (open: boolean) => void;
}) {
  const bodyId = useId();
  return <section id={id} className={`panel ${className}`}>
    {eyebrow && <p className="panel-eyebrow">{eyebrow}</p>}
    <h2 className="panel-title">{onOpenChange
      ? <button className="panel-toggle" type="button" aria-expanded={!!open} aria-controls={bodyId} onClick={() => onOpenChange(!open)}>
          {title}<ChevronDown size={16} aria-hidden="true" />
        </button>
      : title}</h2>
    <div id={bodyId} className="panel-body" hidden={!!onOpenChange && !open}>{(!onOpenChange || open) && children}</div>
  </section>;
}

export function ErrorNote({ error }: { error: unknown }) {
  return <div className="empty-state error-state" role="alert">
    {error instanceof Error ? error.message : "Unable to load data."}
    <span>Try again or adjust your selection.</span>
  </div>;
}

type ExportProps = { disabled?: boolean } & ({ product?: "fires"; filters: Filters; label?: string } |
  { product: "harmonization"; filters: ActivityFilters; label?: string } |
  { product: "validation"; filters: ValidationFilters; label?: string });

export function ExportButton(props: ExportProps) {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const product = props.product ?? "fires";
  let params: URLSearchParams | null = null;
  try {
    params = props.product === "harmonization" || props.product === "validation"
      ? activityQuery(props.filters, props.product) : query(props.filters as Filters);
  } catch { /* Invalid filters are explained alongside their controls. */ }

  async function download() {
    if (!params || props.disabled) return;
    setLoading(true);
    setError("");
    try {
      const response = await fetch(`/api/exports/${product}?${params}`);
      if (!response.ok) {
        const body = await response.json().catch(() => null);
        throw new Error(body?.error || "CSV export failed. Please try again.");
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = response.headers.get("content-disposition")?.match(/filename="?([^";]+)"?/)?.[1] || `firelens-${product}.csv`;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "CSV export failed.");
    } finally { setLoading(false); }
  }

  return <div className="export-wrap">
    <button className="btn-primary" disabled={props.disabled || loading || !params} onClick={download}>
      <ArrowDownToLine size={14} />{loading ? "Exporting…" : props.label || "Export CSV"}
    </button>
    {error && <span className="export-error" role="alert">{error}</span>}
  </div>;
}

export function Pagination({ page, total, pageSize = 100, fetching, onChange, label = "records" }: {
  page: number; total: number; pageSize?: number; fetching: boolean; onChange: (page: number) => void; label?: string;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  return <div className="pagination">
    <span>Page {page} of {pages} · {total.toLocaleString()} {label}</span>
    <div>
      <button aria-label={`Previous ${label} page`} disabled={fetching || page <= 1} onClick={() => onChange(page - 1)}><ChevronLeft size={16} /></button>
      <button aria-label={`Next ${label} page`} disabled={fetching || page >= pages} onClick={() => onChange(page + 1)}><ChevronRight size={16} /></button>
    </div>
  </div>;
}

export function AnalyticsResults({ kind, loading, error, result }: {
  kind: "comparison" | "anomalies"; loading: boolean; error: unknown; result?: ComparisonResult | AnomalyResult | ActivityComparisonResult | ActivityAnomalyResult;
}) {
  if (loading) return <div className="loading-box">Loading historical analytics…</div>;
  if (error) return <ErrorNote error={error} />;
  if (!result) return <div className="empty-state">Historical results are not available.</div>;
  const withVersions = result.data.some((row) => "method_version" in row);
  return <>
    <p className={`result-notice ${result.status === "insufficient_history" ? "history-notice" : ""}`}>{result.message}</p>
    <p className="panel-note">{result.meta.observed_start_date ?? "—"} — {result.meta.observed_end_date ?? "—"} · {result.meta.available_prior_years} prior years available / {result.meta.required_prior_years} required</p>
    {result.data.length > 0 && <div className="table-scroll analytics-table"><table>
      <thead><tr><th>PERIOD</th>{withVersions && <th>METHOD</th>}<th>OBSERVED</th><th>MEAN</th><th>MEDIAN</th>
        {kind === "comparison" ? <th>CHANGE %</th> : <><th>MAD</th><th>Z-SCORE</th><th>SEVERITY</th><th>DIRECTION</th></>}
        <th>BASELINE YEARS</th><th>STATUS</th>
      </tr></thead>
      <tbody>{result.data.map((row, index) => <tr key={`${row.period}-${"method_version" in row ? row.method_version : "raw"}-${index}`}>
        <td>{row.period}</td>{withVersions && <td>{"method_version" in row ? row.method_version : "—"}</td>}
        <td>{formatNumber("observed_activity" in row ? row.observed_activity : row.observed_count, 4)}</td><td>{formatNumber(row.historical_mean, 4)}</td><td>{formatNumber(row.historical_median, 4)}</td>
        {!("date" in row) ? <td>{formatNumber(row.difference_percent)}</td> : <>
          <td>{formatNumber(row.mad)}</td><td>{formatNumber(row.anomaly_score)}</td>
          <td><span className={`status-badge ${row.severity === "high" || row.severity === "moderate" ? "status-warning" : ""}`}>{row.severity ?? "Unavailable"}</span></td><td>{row.direction ?? "—"}</td>
        </>}
        <td>{row.baseline_years}</td><td>{row.status.replaceAll("_", " ")}</td>
      </tr>)}</tbody>
    </table></div>}
    <p className="panel-note">{"baseline_method" in result.meta ? result.meta.baseline_method : result.meta.method}</p>
    {"score_formula" in result.meta && <p className="panel-note">{result.meta.score_formula} · Moderate threshold: {formatNumber(result.meta.moderate_threshold)} · High threshold: {formatNumber(result.meta.high_threshold)}</p>}
    <p className="panel-note">— indicates a statistic the API has not computed.</p>
  </>;
}
