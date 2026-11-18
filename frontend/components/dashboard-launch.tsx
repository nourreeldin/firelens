"use client";

import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Flame, Globe2, Rocket, Satellite } from "lucide-react";

const scenes = [
  { Icon: Rocket, label: "Setting a course for discovery", detail: "Your next perspective is just ahead." },
  { Icon: Satellite, label: "Connecting the observations", detail: "From satellite signals to a shared view." },
  { Icon: Globe2, label: "Bringing Earth into focus", detail: "One planet. A clearer perspective." },
];

export default function DashboardLaunch({ completed, total, onComplete, onCancel }: {
  completed: number; total: number; onComplete: () => void; onCancel: () => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [scene, setScene] = useState(0);
  const [percent, setPercent] = useState(0);
  const startedAt = useRef<number | null>(null);
  const { Icon, label, detail } = scenes[scene];
  const targetPercent = Math.round(completed / total * 100);

  useEffect(() => {
    let frame: number;
    const advance = (now: number) => {
      startedAt.current ??= now;
      // Replay a short fill on every launch, capped by actual loading progress.
      const next = Math.min(targetPercent, Math.floor((now - startedAt.current) / 600 * 100));
      setPercent(next);
      if (next < targetPercent) frame = window.requestAnimationFrame(advance);
    };
    frame = window.requestAnimationFrame(advance);
    return () => window.cancelAnimationFrame(frame);
  }, [targetPercent]);

  useEffect(() => {
    if (percent !== 100) return;
    // Let the bar finish its CSS transition before entering the workspace.
    const timer = window.setTimeout(onComplete, 150);
    return () => window.clearTimeout(timer);
  }, [percent, onComplete]);

  useEffect(() => {
    const element = dialog.current;
    const previousFocus = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    if (element && !element.open) element.showModal();
    const timer = window.setInterval(() => setScene((current) => (current + 1) % scenes.length), 2600);
    return () => {
      window.clearInterval(timer);
      element?.close();
      document.body.style.overflow = previousOverflow;
      if (previousFocus instanceof HTMLElement && previousFocus.isConnected) previousFocus.focus({ preventScroll: true });
    };
  }, []);

  return <dialog ref={dialog} className="dashboard-launch" aria-labelledby="dashboard-launch-title" aria-describedby="dashboard-launch-description" onCancel={(event) => { event.preventDefault(); onCancel(); }}>
    <div className="dashboard-launch-topbar">
      <span className="dashboard-launch-brand"><Flame size={20} /> fire<span>lens</span></span>
      <button type="button" onClick={onCancel} autoFocus><ArrowLeft size={15} /> Back to landing</button>
    </div>
    <div className="dashboard-launch-content">
      <p className="dashboard-launch-eyebrow"><span /> YOUR WORKSPACE IS ON THE HORIZON</p>
      <div className="dashboard-launch-art" aria-hidden="true">
        <svg viewBox="0 0 400 260" fill="none" className="dashboard-launch-orbits">
          <ellipse cx="200" cy="130" rx="169" ry="65" transform="rotate(-24 200 130)" />
          <ellipse cx="200" cy="130" rx="135" ry="100" transform="rotate(30 200 130)" />
          <circle cx="200" cy="130" r="91" strokeDasharray="2 9" />
          <path d="M51 65h10m-5-5v10M333 186h12m-6-6v12M305 37h8m-4-4v8" />
          <g className="dashboard-launch-stars"><circle cx="92" cy="183" r="2" /><circle cx="313" cy="99" r="2.5" /><circle cx="130" cy="42" r="1.5" /><circle cx="253" cy="222" r="2" /><circle cx="40" cy="141" r="1.5" /></g>
          <g className="dashboard-launch-orbiter"><circle cx="200" cy="39" r="5" fill="currentColor" stroke="none" /></g>
        </svg>
        <div className="dashboard-launch-planet" key={scene} data-scene={scene}>
          <span className="dashboard-launch-icon"><Icon size={76} strokeWidth={1.1} /></span>
          <span className="dashboard-launch-icon-ring" />
        </div>
        <span className="dashboard-launch-coordinate">ORBIT / {String(scene + 1).padStart(2, "0")}</span>
      </div>
      <h1 id="dashboard-launch-title">Launching your dashboard<span className="dashboard-launch-dots">...</span></h1>
      <p id="dashboard-launch-description">{label}</p>
      <div className="dashboard-launch-progress-label"><span>{percent === 100 ? "Opening your workspace" : "Preparing your workspace"}</span><span>{percent}<small>%</small></span></div>
      <div className="dashboard-launch-progress" role="progressbar" aria-label="Dashboard loading progress" aria-valuemin={0} aria-valuemax={100} aria-valuenow={percent}>
        <span style={{ width: `${percent}%` }} />
      </div>
      <p className="dashboard-launch-detail">{detail}</p>
    </div>
    <div className="dashboard-launch-footer"><span>EARTH OBSERVATION / FIRELENS</span><span><i /> ALL REGIONS · MODIS + VIIRS</span></div>
  </dialog>;
}
