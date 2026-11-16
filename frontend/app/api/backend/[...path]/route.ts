import type { NextRequest } from "next/server";

const routes = new Set([
  "health", "regions", "regions/catalog", "fires", "calendar",
  "analytics/seasonal", "analytics/comparison", "analytics/anomalies",
  "harmonization", "harmonization/calendar", "harmonization/analytics/seasonal",
  "harmonization/analytics/comparison", "harmonization/analytics/anomalies", "validation",
]);

export async function GET(request: NextRequest, context: { params: Promise<{ path: string[] }> }) {
  const { path } = await context.params;
  const route = path.join("/");
  if (!routes.has(route) && !/^fires\/\d+$/.test(route)) {
    return Response.json({ detail: "Unknown API route." }, { status: 404 });
  }
  const base = (process.env.FIRELENS_API_BASE_URL || process.env.NEXT_PUBLIC_API_BASE_URL || "http://127.0.0.1:8000")
    .replace(/\/+$/, "").replace(/\/api\/v1$/, "");
  try {
    const response = await fetch(`${base}/api/v1/${route}${request.nextUrl.search}`, {
      headers: { Accept: "application/json" },
      cache: "no-store",
      signal: AbortSignal.any([request.signal, AbortSignal.timeout(60000)]),
    });
    return new Response(response.body, {
      status: response.status,
      headers: {
        "Content-Type": response.headers.get("content-type") || "application/json",
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
      },
    });
  } catch (error) {
    if (request.signal.aborted) throw error;
    return Response.json({ detail: "Could not connect to the FireLens API. Please try again." }, { status: 502 });
  }
}
