"use client";

import { useCallback, useEffect, useRef, useState, useSyncExternalStore } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { useRouter } from "next/navigation";
import { getDashboardPreloadProgress, initialPreloadProgress, preloadDashboardData, subscribeDashboardPreload } from "@/lib/dashboard-queries";
import DashboardLaunch from "./dashboard-launch";

let dashboardCode: Promise<unknown> | undefined;
let mapCode: Promise<unknown> | undefined;
const prefetchedClients = new WeakSet<ReturnType<typeof useQueryClient>>();

export default function DashboardPreloader() {
  const client = useQueryClient();
  const router = useRouter();
  const [destination, setDestination] = useState<string | null>(null);
  const [codeReady, setCodeReady] = useState(false);
  const [launchComplete, setLaunchComplete] = useState(false);
  const completeLaunch = useCallback(() => setLaunchComplete(true), []);
  const navigating = useRef(false);
  const progress = useSyncExternalStore(
    useCallback((listener) => subscribeDashboardPreload(client, listener), [client]),
    useCallback(() => getDashboardPreloadProgress(client), [client]),
    () => initialPreloadProgress,
  );

  useEffect(() => {
    let mounted = true;
    if (!prefetchedClients.has(client)) {
      router.prefetch("/dashboard");
      prefetchedClients.add(client);
    }
    // Import the browser-only map here rather than evaluating Leaflet during SSR.
    dashboardCode ??= import("./dashboard").catch(() => { dashboardCode = undefined; });
    mapCode ??= import("./fire-map").catch(() => { mapCode = undefined; });
    void Promise.all([dashboardCode, mapCode]).then(() => { if (mounted) setCodeReady(true); });
    void preloadDashboardData(client);
    return () => { mounted = false; };
  }, [client, router]);

  useEffect(() => {
    const interceptLaunch = (event: MouseEvent) => {
      if (event.defaultPrevented || event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
      const anchor = event.target instanceof Element ? event.target.closest<HTMLAnchorElement>("a[href]") : null;
      if (!anchor || anchor.hasAttribute("download") || (anchor.target && anchor.target !== "_self")) return;
      const url = new URL(anchor.href, window.location.href);
      if (url.origin !== window.location.origin || url.pathname !== "/dashboard") return;
      event.preventDefault();
      setLaunchComplete(false);
      setDestination(`${url.pathname}${url.search}${url.hash}`);
    };
    // Capture before Next's Link handler so ordinary links, keyboard activation,
    // and the feature cards all share the same launch transition.
    document.addEventListener("click", interceptLaunch, true);
    return () => document.removeEventListener("click", interceptLaunch, true);
  }, []);

  useEffect(() => {
    if (!destination || !progress.ready || !codeReady || !launchComplete || navigating.current) return;
    navigating.current = true;
    router.push(destination);
  }, [destination, progress.ready, codeReady, launchComplete, router]);

  const cancelLaunch = () => { navigating.current = false; setLaunchComplete(false); setDestination(null); };
  return destination ? <DashboardLaunch completed={progress.completed + (codeReady ? 2 : 0)} total={progress.total + 2} onComplete={completeLaunch} onCancel={cancelLaunch} /> : null;
}
