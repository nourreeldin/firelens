"use client";

import { useEffect, useRef } from "react";
import { useQuery } from "@tanstack/react-query";
import { X } from "lucide-react";
import { api } from "@/lib/api/client";
import { ErrorNote, formatNumber } from "./dashboard-ui";

export default function FireDetails({ id, onClose }: { id: number; onClose: () => void }) {
  const dialog = useRef<HTMLDialogElement>(null);
  const fire = useQuery({ queryKey: ["fire-detail", id], queryFn: ({ signal }) => api.fire(id, signal) });
  useEffect(() => {
    const element = dialog.current;
    element?.showModal();
    return () => element?.close();
  }, []);
  const record = fire.data;
  const fields = record ? [
    ["Source detection ID", record.source_detection_id ?? "—"],
    ["Acquisition date", record.acq_date], ["Acquisition time (HHMM UTC)", record.acq_time == null ? "—" : String(record.acq_time).padStart(4, "0")],
    ["Acquisition datetime (UTC)", record.acq_datetime_utc ?? "—"],
    ["Sensor", record.sensor ?? "—"], ["Satellite", record.satellite ?? "—"], ["Collection version", record.version ?? "—"],
    ["Confidence", record.confidence], ["Original confidence", record.confidence_raw ?? "—"],
    ["Latitude", formatNumber(record.latitude, 6)], ["Longitude", formatNumber(record.longitude, 6)],
    ["Country", record.country_name ?? record.country_code ?? "—"], ["Continent", record.continent ?? "—"],
    ["Day / night", record.daynight === "D" ? "Day" : record.daynight === "N" ? "Night" : record.daynight ?? "—"],
    ["Radiative power (MW)", formatNumber(record.frp)], ["Brightness temperature (K)", formatNumber(record.brightness)],
    ["Thermal brightness (K)", formatNumber(record.brightness_thermal)], ["Scan (km)", formatNumber(record.scan)], ["Track (km)", formatNumber(record.track)],
    ["MODIS bright T31 (K)", formatNumber(record.bright_t31)], ["VIIRS bright TI4 (K)", formatNumber(record.bright_ti4)], ["VIIRS bright TI5 (K)", formatNumber(record.bright_ti5)],
    ["Instrument", record.instrument ?? "—"], ["Source file", record.source_file ?? "—"], ["Fire type", record.fire_type == null ? "—" : String(record.fire_type)],
    ["Coordinate reference system", record.coordinate_reference_system ?? "—"], ["Grid latitude", formatNumber(record.grid_lat, 0)], ["Grid longitude", formatNumber(record.grid_lon, 0)],
    ["Year", formatNumber(record.year, 0)], ["Month", formatNumber(record.month, 0)], ["Day", formatNumber(record.day, 0)], ["Day of year", formatNumber(record.day_of_year, 0)],
    ["Hour (UTC)", formatNumber(record.hour, 0)], ["Minute (UTC)", formatNumber(record.minute, 0)], ["Created (UTC)", record.created_at ?? "—"],
    ["Spatial grid", record.spatial_grid_id ?? "—"],
  ] : [];
  return <dialog ref={dialog} className="fire-details" aria-labelledby="fire-details-title" onCancel={(event) => { event.preventDefault(); onClose(); }} onClick={(event) => { if (event.target === event.currentTarget) onClose(); }}>
    <div className="fire-details-inner"><div className="panel-actions"><div><p className="panel-eyebrow">RAW SATELLITE OBSERVATION</p><h2 className="panel-title" id="fire-details-title">Fire detection #{id}</h2></div><button className="dialog-close" aria-label="Close detection details" onClick={onClose}><X size={18} /></button></div>
      {fire.isLoading ? <div className="loading-box">Loading detection details…</div> : fire.isError ? <ErrorNote error={fire.error} /> : <dl className="detection-fields">{fields.map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value}</dd></div>)}</dl>}
      <p className="panel-note">— means the value was not provided by the satellite dataset. Source detection IDs remain text and are distinct from the numeric detection ID.</p>
    </div>
  </dialog>;
}
