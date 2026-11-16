"use client";

import { useEffect, useRef, useState, type MouseEvent } from "react";
import { Activity, ArrowLeft, ChartNoAxesCombined, ChevronRight, Flame, Layers, LayoutDashboard, MapPinned, ShieldCheck, TableProperties, X, type LucideIcon } from "lucide-react";
import { workspaceViews, type WorkspaceView } from "@/lib/workspace-navigation";

export const workspaceIcons: Record<WorkspaceView, LucideIcon> = {
  overview: LayoutDashboard, activity: Activity, map: MapPinned, data: TableProperties,
  analytics: ChartNoAxesCombined, harmonization: Layers, validation: ShieldCheck,
};

export default function WorkspaceSidebar({ activeView, open, onNavigate, onClose }: {
  activeView: WorkspaceView; open: boolean; onNavigate: (view: WorkspaceView) => void; onClose: () => void;
}) {
  const sidebar = useRef<HTMLElement>(null);
  const [homeLinkReady, setHomeLinkReady] = useState(false);
  // Keep the server and first client footer identical. Add this navigation
  // enhancement only after hydration, including during development refreshes.
  useEffect(() => setHomeLinkReady(true), []);
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    sidebar.current?.querySelector<HTMLElement>('[aria-current="page"]')?.focus();
    function keyboard(event: KeyboardEvent) {
      if (event.key === "Escape") { event.preventDefault(); onClose(); }
      if (event.key !== "Tab") return;
      const targets = sidebar.current?.querySelectorAll<HTMLElement>('a[href], button:not([disabled])');
      if (!targets?.length) return;
      const first = targets[0], last = targets[targets.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
    }
    document.addEventListener("keydown", keyboard);
    return () => {
      document.body.style.overflow = overflow;
      document.removeEventListener("keydown", keyboard);
      if (previous instanceof HTMLElement && previous.isConnected) previous.focus();
    };
  }, [open, onClose]);

  function select(event: MouseEvent<HTMLAnchorElement>, view: WorkspaceView) {
    if (event.metaKey || event.ctrlKey || event.shiftKey || event.altKey || event.button !== 0) return;
    event.preventDefault();
    onNavigate(view);
  }

  return <>
    {open && <button className="sidebar-backdrop" type="button" onClick={onClose} aria-label="Close navigation" tabIndex={-1} />}
    <aside ref={sidebar} id="workspace-sidebar" className="workspace-sidebar" data-open={open} aria-label="Workspace navigation">
      <div className="sidebar-brand-row">
        <a href="#overview" className="brand" aria-label="FireLens overview" onClick={(event) => select(event, "overview")}>
          <span className="brand-mark"><Flame size={19} /></span>
          <span className="brand-name">fire<em>lens</em><small>EARTH OBSERVATION</small></span>
        </a>
        <button className="sidebar-close" type="button" onClick={onClose} aria-label="Close navigation"><X size={18} /></button>
      </div>
      <div className="sidebar-intro"><span className="sidebar-kicker">FIRE INTELLIGENCE</span><p>Explore. Compare. Understand.</p></div>
      <nav className="sidebar-nav" aria-label="Dashboard sections">
        {(["Explore", "Analysis"] as const).map((group) => <div className="sidebar-group" key={group}>
          <p className="sidebar-group-label">{group}</p>
          {workspaceViews.filter((view) => view.group === group).map((view) => {
            const Icon = workspaceIcons[view.id];
            return <a key={view.id} href={`#${view.id}`} className="sidebar-link" aria-current={activeView === view.id ? "page" : undefined} onClick={(event) => select(event, view.id)}>
              <Icon size={17} aria-hidden="true" /><span>{view.label}</span>{activeView === view.id && <ChevronRight size={14} className="sidebar-active-arrow" aria-hidden="true" />}
            </a>;
          })}
        </div>)}
      </nav>
      <div className="sidebar-footer">{homeLinkReady && <a href="/" className="sidebar-home-link"><ArrowLeft size={13} /> Back to home</a>}<span className="sidebar-satellite"><ShieldCheck size={16} /> SATELLITE OBSERVATIONS</span><p>NASA Space Apps<br /><strong>Cairo · 2026</strong></p></div>
    </aside>
  </>;
}
