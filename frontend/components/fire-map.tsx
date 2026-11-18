"use client";

import { useEffect, useMemo, useState } from "react";
import { useInfiniteQuery, useQueryClient, type InfiniteData } from "@tanstack/react-query";
import { CircleMarker, MapContainer, Popup, TileLayer, useMap } from "react-leaflet";
import { geoJSON, latLngBounds, type LatLngBounds } from "leaflet";
import { LocateFixed } from "lucide-react";
import { dashboardQueries } from "@/lib/dashboard-queries";
import type { FireDetection, FireListResult, Filters } from "@/lib/api/types";
import countries from "@/lib/fire-map-countries.json";
import "leaflet/dist/leaflet.css";

type StudyRegion = Omit<(typeof countries.features)[number], "type"> & { type: "Feature" };
const studyRegions = countries.features as StudyRegion[];
const africaBounds = latLngBounds([[-35, -18], [38, 52]]);
const cartoApiKey = process.env.NEXT_PUBLIC_CARTO_API_KEY?.trim();
const sensorColors = { MODIS: "#cf551b", VIIRS: "#256ab8", Unknown: "#657388" };

function sensorName(sensor: string | null | undefined) {
  return sensor === "MODIS" || sensor === "VIIRS" ? sensor : "Unknown";
}

function printableTime(fire: FireDetection) {
  if (fire.acq_datetime_utc) {
    return new Date(fire.acq_datetime_utc).toLocaleString(undefined, {
      dateStyle: "medium",
      timeStyle: "short",
      timeZone: "UTC",
    }) + " UTC";
  }
  if (fire.acq_time == null) return fire.acq_date;
  const time = String(fire.acq_time).padStart(4, "0");
  return `${fire.acq_date} at ${time.slice(0, 2)}:${time.slice(2)} UTC`;
}

function validLocation(fire: FireDetection) {
  return Number.isFinite(fire.latitude) && Number.isFinite(fire.longitude)
    && Math.abs(fire.latitude) <= 90 && Math.abs(fire.longitude) <= 180;
}

function MapViewport({ bounds, reset }: { bounds: LatLngBounds; reset: number }) {
  const map = useMap();

  useEffect(() => {
    if (bounds.isValid()) map.fitBounds(bounds, { padding: [24, 24], maxZoom: 9 });
  }, [map, bounds, reset]);

  useEffect(() => {
    const observer = new ResizeObserver(() => map.invalidateSize());
    observer.observe(map.getContainer());
    return () => observer.disconnect();
  }, [map]);

  return null;
}

export default function FireMap({ filters, dark }: { filters: Filters; dark: boolean }) {
  const [reset, setReset] = useState(0);
  const [tileError, setTileError] = useState(false);
  const regions = useMemo(() => (
    filters.region ? studyRegions.filter(({ properties }) => properties.code === filters.region) : studyRegions
  ), [filters.region]);
  const queryClient = useQueryClient();
  const mapQuery = dashboardQueries.map(filters);
  const queryKey = mapQuery.queryKey;
  const detections = useInfiniteQuery(mapQuery);
  const loadedPages = detections.data?.pages.length ?? 0;

  function showFewerHotspots() {
    queryClient.setQueryData<InfiniteData<FireListResult, number>>(queryKey, (current) => {
      if (!current || current.pages.length <= 1) return current;
      return { pages: current.pages.slice(0, -1), pageParams: current.pageParams.slice(0, -1) };
    });
  }

  const firstPage = detections.data?.pages[0];
  const fires = useMemo(() => detections.data?.pages.flatMap((page) => page.data.filter(validLocation)) ?? [], [detections.data]);
  const { min_latitude, min_longitude, max_latitude, max_longitude } = filters.bounds ?? {};
  const fallbackFires = filters.region && !regions.length ? firstPage?.data : undefined;
  const bounds = useMemo(() => {
    if (min_latitude && min_longitude && max_latitude && max_longitude) {
      return latLngBounds([[Number(min_latitude), Number(min_longitude)], [Number(max_latitude), Number(max_longitude)]]);
    }
    if (!filters.region) return africaBounds;
    const selection = latLngBounds([]);
    for (const region of regions) selection.extend(geoJSON(region).getBounds());
    if (!selection.isValid()) {
      for (const fire of fallbackFires ?? []) {
        if (validLocation(fire)) selection.extend([fire.latitude, fire.longitude]);
      }
    }
    return selection.isValid() ? selection : africaBounds;
  }, [fallbackFires, filters.region, regions, min_latitude, min_longitude, max_latitude, max_longitude]);
  const legend = useMemo(() => new Set([
    ...(filters.sensor === "ALL" ? ["MODIS", "VIIRS"] as const : [filters.sensor]),
    ...fires.map((fire) => sensorName(fire.sensor)),
  ]), [filters.sensor, fires]);

  return (
    <div className="map-explorer">
      <div className="map-toolbar">
        <span>Each dot is one satellite hotspot detection. Click a dot to see where and when it was detected.</span>
        <button className="map-fit-button" type="button" onClick={() => setReset((value) => value + 1)}>
          <LocateFixed size={13} /> Fit to selection
        </button>
      </div>
      <div className="map-wrap" aria-label="Map of individual satellite hotspot detections">
        <MapContainer center={africaBounds.getCenter()} zoom={2} minZoom={1} zoomControl scrollWheelZoom={false} preferCanvas className="fire-map">
          <MapViewport bounds={bounds} reset={reset} />
          <TileLayer
            key={cartoApiKey ? `carto-${dark ? "dark" : "light"}` : "openstreetmap"}
            attribution={cartoApiKey
              ? '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>'
              : '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'}
            url={cartoApiKey
              ? `https://{s}.basemaps.cartocdn.com/${dark ? "dark_all" : "light_all"}/{z}/{x}/{y}{r}.png?key=${encodeURIComponent(cartoApiKey)}`
              : "https://tile.openstreetmap.org/{z}/{x}/{y}.png"}
            maxZoom={cartoApiKey ? 20 : 19}
            eventHandlers={{ tileerror: () => setTileError(true), load: () => setTileError(false) }}
          />
          {fires.map((fire) => {
            const sensor = sensorName(fire.sensor);
            return (
              <CircleMarker key={fire.id} center={[fire.latitude, fire.longitude]} radius={4.5} pathOptions={{
                color: dark ? "#182332" : "#fff", weight: 1, fillColor: sensorColors[sensor], fillOpacity: 0.9,
              }}>
                <Popup>
                  <div className="fire-popup">
                    <strong>{fire.country_name?.replaceAll("_", " ") || fire.country_code || "Hotspot detection"}</strong>
                    <dl>
                      <div><dt>Detected</dt><dd>{printableTime(fire)}</dd></div>
                      <div><dt>Sensor</dt><dd>{sensor}</dd></div>
                      <div><dt>Location</dt><dd>{fire.latitude.toFixed(4)}, {fire.longitude.toFixed(4)}</dd></div>
                    </dl>
                  </div>
                </Popup>
              </CircleMarker>
            );
          })}
        </MapContainer>
        {tileError && <div className="map-notice" role="status">Basemap unavailable. Hotspot dots are still visible.</div>}
      </div>
      <div className="map-legend" aria-label="Satellite sensor legend">
        <strong>Detected by</strong>
        {[...legend].map((sensor) => <span key={sensor}><i aria-hidden="true" style={{ backgroundColor: sensorColors[sensor] }} />{sensor === "Unknown" ? "Unknown sensor" : sensor}</span>)}
      </div>
      <div className="map-toolbar map-results">
        <span role="status">{detections.isPending ? "Loading hotspots…" : !firstPage ? "Hotspots could not be loaded."
          : firstPage.pagination.total === 0 ? "No hotspots match these filters."
          : `Showing ${fires.length.toLocaleString()} of ${firstPage.pagination.total.toLocaleString()} matching detections. Use the date or region filters to narrow the map.`}</span>
        <div className="map-pagination">
          {loadedPages > 1 && <button type="button" className="map-fit-button" disabled={detections.isFetching} onClick={showFewerHotspots}>
            Show fewer hotspots
          </button>}
          {detections.isError && <button type="button" className="text-button" onClick={() => detections.isFetchNextPageError ? detections.fetchNextPage() : detections.refetch()}>
            {detections.isFetchNextPageError ? "Retry loading more" : "Retry"}
          </button>}
          {detections.hasNextPage && !detections.isError && <button type="button" className="map-fit-button" disabled={detections.isFetching} onClick={() => detections.fetchNextPage()}>
            {detections.isFetchingNextPage ? "Loading…" : "Show more hotspots"}
          </button>}
        </div>
      </div>
      {!!regions.length && <a className="map-boundary-source" href="https://www.naturalearthdata.com/downloads/110m-cultural-vectors/110m-admin-0-countries/" target="_blank" rel="noreferrer">Country zoom extents: Natural Earth</a>}
    </div>
  );
}
