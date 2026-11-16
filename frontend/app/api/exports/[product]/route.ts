import type { NextRequest } from "next/server";

const allowedFilters: Record<string, string[]> = {
  fires: ["start_date", "end_date", "region_id", "sensor", "min_latitude", "max_latitude", "min_longitude", "max_longitude"],
  harmonization: ["start_date", "end_date", "region_pk", "spatial_grid_id", "method_version"],
  validation: ["start_date", "end_date", "region_pk", "method_version"],
};

export async function GET(request: NextRequest, context: { params: Promise<{ product: string }> }) {
  const { product } = await context.params;
  if (!Object.hasOwn(allowedFilters, product)) return Response.json({ error: "Unknown export product." }, { status: 404 });
  const base = (process.env.FIRELENS_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000")
    .replace(/\/+$/, "").replace(/\/api\/v1$/, "");
  const upstream = new URLSearchParams();
  for (const key of allowedFilters[product]) {
    const value = request.nextUrl.searchParams.get(key);
    if (value) upstream.set(key, value);
  }
  const headers = new Headers({ Accept: "text/csv" });
  if (process.env.FIRELENS_API_KEY) headers.set("X-API-Key", process.env.FIRELENS_API_KEY);
  try {
    const response = await fetch(`${base}/api/v1/exports/${product}?${upstream}`, {
      headers, cache: "no-store", signal: AbortSignal.any([request.signal, AbortSignal.timeout(120000)]),
    });
    if (!response.ok) {
      const messages: Record<number, string> = {
        401: "Export access requires a valid server-side FIRELENS_API_KEY.",
        404: "The selected region was not found.",
        422: "Selected filters are invalid. Check the date range and region.",
        503: "The FireLens API is temporarily unavailable.",
      };
      return Response.json({ error: messages[response.status] || "CSV export failed. Please try again." }, { status: response.status });
    }
    return new Response(response.body, { headers: {
      "Content-Type": response.headers.get("content-type") || "text/csv; charset=utf-8",
      "Content-Disposition": response.headers.get("content-disposition") || `attachment; filename="firelens-${product}.csv"`,
      "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
    } });
  } catch {
    return Response.json({ error: "Could not connect to the FireLens API. Please try again." }, { status: 502 });
  }
}
