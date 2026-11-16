"use client";

import { useEffect, type MouseEvent } from "react";
import Link from "next/link";
import { Activity, ArrowDown, ArrowRight, ArrowUpRight, ChevronRight, Crosshair, Flame, Layers, Satellite, ScanLine, ShieldCheck } from "lucide-react";
import LandingThemeToggle from "./landing-theme-toggle";
import { MapPreview, OrbitalEarth, SensorLayers, TrendPreview } from "./landing-illustrations";

function Brand() {
  return <Link href="/" className="brand landing-brand" aria-label="FireLens home">
    <span className="brand-mark"><Flame size={20} /></span>
    <span className="brand-name">fire<em>lens</em><small>EARTH OBSERVATION</small></span>
  </Link>;
}

export default function LandingPage() {
  const docsUrl = process.env.NEXT_PUBLIC_API_DOCS_URL || "http://127.0.0.1:8000/docs";

  const scrollToSection = (e: MouseEvent<HTMLAnchorElement>, id: string) => {
    if (e.metaKey || e.ctrlKey || e.shiftKey || e.altKey || e.button !== 0) return;
    e.preventDefault();
    const element = document.getElementById(id);
    if (element) {
      const header = document.querySelector(".landing-header");
      const headerHeight = header ? header.getBoundingClientRect().height : 88;
      const elementTop = element.getBoundingClientRect().top + window.scrollY;
      const targetPosition = elementTop - headerHeight - 16;
      window.scrollTo({
        top: Math.max(0, targetPosition),
        behavior: "smooth",
      });
      window.history.pushState(null, "", `#${id}`);
    }
  };

  useEffect(() => {
    const handleHash = () => {
      const hash = window.location.hash.replace(/^#/, "");
      if (!hash) return;
      const element = document.getElementById(hash);
      if (element) {
        const header = document.querySelector(".landing-header");
        const headerHeight = header ? header.getBoundingClientRect().height : 88;
        const elementTop = element.getBoundingClientRect().top + window.scrollY;
        window.scrollTo({
          top: Math.max(0, elementTop - headerHeight - 16),
          behavior: "smooth",
        });
      }
    };
    handleHash();
    window.addEventListener("hashchange", handleHash);
    return () => window.removeEventListener("hashchange", handleHash);
  }, []);

  return <div className="landing-page">
    <a className="landing-skip-link" href="#landing-main">Skip to content</a>
    <header className="landing-header">
      <div className="landing-container landing-header-inner">
        <Brand />
        <nav className="landing-nav" aria-label="Main navigation">
          <a href="#mission" onClick={(e) => scrollToSection(e, "mission")}>The mission</a>
          <a href="#explore" onClick={(e) => scrollToSection(e, "explore")}>Explore the data</a>
          <a href="#workflow" onClick={(e) => scrollToSection(e, "workflow")}>How it works</a>
        </nav>
        <div className="landing-header-actions"><LandingThemeToggle /><Link href="/dashboard" className="landing-header-cta">Launch dashboard <ArrowUpRight size={15} /></Link></div>
      </div>
    </header>

    <main id="landing-main">
      <section className="landing-hero landing-container" aria-labelledby="landing-title">
        <div className="landing-hero-copy">
          <p className="landing-mission-badge"><span /> NASA SPACE APPS CAIRO 2026</p>
          <h1 id="landing-title">A clearer view<br />of a world<br /><em>on fire.</em></h1>
          <p className="landing-hero-description">Explore satellite fire observations, reveal seasonal patterns, and connect MODIS and VIIRS data through one shared perspective.</p>
          <div className="landing-hero-actions">
            <Link href="/dashboard" className="landing-button landing-button-primary">Explore the dashboard <ArrowUpRight size={18} /></Link>
            <a className="landing-text-link" href="#mission" onClick={(e) => scrollToSection(e, "mission")}>Discover the mission <ArrowDown size={14} /></a>
          </div>
          <p className="landing-source-note"><Satellite size={15} /> Built around NASA FIRMS observations</p>
        </div>
        <div className="landing-hero-art"><OrbitalEarth /><p className="landing-illustration-caption">An illustrative perspective. Explore the actual observations in the dashboard.</p></div>
      </section>

      <div className="landing-container">
        <div className="landing-observation-strip" aria-label="From observation to understanding">
          <a href="#mission" onClick={(e) => scrollToSection(e, "mission")} className="landing-strip-item">
            <Satellite size={22} />
            <span><small>01 / OBSERVE</small><strong>Two satellite perspectives</strong><span>MODIS & VIIRS observations</span></span>
          </a>
          <a href="#explore" onClick={(e) => scrollToSection(e, "explore")} className="landing-strip-item">
            <Layers size={22} />
            <span><small>02 / CONNECT</small><strong>A shared view of activity</strong><span>Raw data & corrected estimates</span></span>
          </a>
          <a href="#workflow" onClick={(e) => scrollToSection(e, "workflow")} className="landing-strip-item">
            <Activity size={22} />
            <span><small>03 / UNDERSTAND</small><strong>Context behind the patterns</strong><span>Seasonality, baselines & quality</span></span>
          </a>
        </div>
      </div>

      <section id="mission" className="landing-mission-section landing-container" aria-labelledby="mission-title">
        <div className="landing-mission-visual"><span className="landing-visual-index">01 — THE MISSION</span><SensorLayers /><p className="landing-illustration-caption">Different observations. Connected layers of context.</p></div>
        <div className="landing-section-copy"><p className="landing-eyebrow"><span /> A PLANET WORTH UNDERSTANDING</p><h2 id="mission-title">Different sensors.<br />One shared perspective.</h2><p>Every fire detection is a piece of a bigger story. Resolution, coverage, and timing shape what each satellite sees.</p><p>FireLens brings satellite observations, harmonized activity, and quality reports into one workspace, making those patterns easier to explore with context.</p><div className="landing-mission-principle"><ScanLine size={20} /><span><strong>Start with the observations.</strong><span>Follow the patterns. Ask better questions.</span></span></div><Link href="/dashboard#harmonization" className="landing-inline-link">Discover harmonized activity <ArrowRight size={16} /></Link></div>
      </section>

      <section id="explore" className="landing-explore-section" aria-labelledby="explore-title">
        <div className="landing-container">
          <div className="landing-section-heading"><div><p className="landing-eyebrow"><span /> YOUR WORKSPACE, CONNECTED</p><h2 id="explore-title">Follow your curiosity.<br />Find the evidence.</h2></div><p>Move from a global perspective to the details that matter, with dedicated tools for every part of the story.</p></div>
          <div className="landing-explore-grid">
            <Link href="/dashboard#map" className="landing-feature landing-feature-map"><div className="landing-feature-top"><span className="landing-feature-label"><Crosshair size={15} /> GEOSPATIAL EXPLORATION</span><ArrowUpRight size={20} /></div><h3>Put observations<br />on the map.</h3><p>Explore where activity appears. Inspect individual detections and focus on the region you want to understand.</p><MapPreview /><span className="landing-feature-link">Explore the fire map <ArrowRight size={16} /></span></Link>
            <Link href="/dashboard#activity" className="landing-feature landing-feature-trends"><div className="landing-feature-top"><span className="landing-feature-label"><Activity size={15} /> PATTERNS OVER TIME</span><ArrowUpRight size={20} /></div><h3>See the rhythm of fire.</h3><p>Find daily patterns and seasonal shifts through calendars, trends, and historical views.</p><TrendPreview /><span className="landing-feature-link">Explore activity <ArrowRight size={16} /></span></Link>
            <Link href="/dashboard#validation" className="landing-feature landing-feature-quality"><div className="landing-feature-top"><span className="landing-feature-label"><ShieldCheck size={15} /> CONTEXT & QUALITY</span><ArrowUpRight size={20} /></div><h3>Look beyond a single number.</h3><p>Review the method, validation reports, and available metrics behind your analysis.</p><div className="landing-quality-graphic" aria-hidden="true"><span><i /> Observations</span><div /><span><i /> Method</span><div /><span><i /> Context</span></div><span className="landing-feature-link">Review validation <ArrowRight size={16} /></span></Link>
          </div>
          <p className="landing-preview-note">Preview graphics are illustrative. Open the dashboard to explore the connected dataset.</p>
        </div>
      </section>

      <section id="workflow" className="landing-workflow-section landing-container" aria-labelledby="workflow-title">
        <div className="landing-section-heading"><div><p className="landing-eyebrow"><span /> FROM ORBIT TO YOUR NEXT QUESTION</p><h2 id="workflow-title">A little perspective<br />goes a long way.</h2></div><Link href="/dashboard" className="landing-inline-link">Find your starting point <ArrowUpRight size={16} /></Link></div>
        <ol className="landing-workflow">
          <li><div className="landing-step-heading"><span>01</span><Crosshair size={20} /></div><h3>Choose your focus.</h3><p>Pick a region and an available period. Start with a place or a question that interests you.</p><span className="landing-step-detail">REGION / PERIOD / SENSOR</span></li>
          <li><div className="landing-step-heading"><span>02</span><Satellite size={20} /></div><h3>Change your perspective.</h3><p>Switch between the map, calendar, and detection records. Your selection stays with you.</p><span className="landing-step-detail">MAP / CALENDAR / RECORDS</span></li>
          <li><div className="landing-step-heading"><span>03</span><Layers size={20} /></div><h3>Connect the context.</h3><p>Compare historical patterns, explore corrected activity, and review the available quality reports.</p><span className="landing-step-detail">COMPARE / HARMONIZE / VALIDATE</span></li>
        </ol>
      </section>

      <section className="landing-launch-section landing-container" aria-labelledby="launch-title">
        <div className="landing-launch-card"><div className="landing-launch-orbits" aria-hidden="true"><i /><i /><i /><span>+</span></div><div className="landing-launch-copy"><p className="landing-eyebrow"><span /> NEXT STOP / YOUR WORKSPACE</p><h2 id="launch-title">The planet has a story.<br />Take a closer look.</h2><p>Bring an explorer’s curiosity. Leave with a clearer perspective.</p><div className="landing-launch-actions"><Link href="/dashboard" className="landing-button landing-button-light">Launch FireLens <ArrowUpRight size={18} /></Link><a href={docsUrl} target="_blank" rel="noreferrer" className="landing-launch-docs">Explore the API <ArrowUpRight size={14} /></a></div></div><div className="landing-launch-coordinate" aria-hidden="true"><span>EARTH OBSERVATION</span><span>ONE PLANET. MANY PERSPECTIVES.</span></div></div>
      </section>
    </main>

    <footer className="landing-footer landing-container">
      <div className="landing-footer-brand"><Brand /><p>Earth observation. Clearer perspective.</p></div>
      <nav aria-label="Footer navigation">
        <Link href="/dashboard">Dashboard <ChevronRight size={12} /></Link>
        <a href={docsUrl} target="_blank" rel="noreferrer">API reference <ArrowUpRight size={12} /></a>
        <a href="#mission" onClick={(e) => scrollToSection(e, "mission")}>The mission</a>
        <a href="#explore" onClick={(e) => scrollToSection(e, "explore")}>Explore the data</a>
        <a href="#workflow" onClick={(e) => scrollToSection(e, "workflow")}>How it works</a>
      </nav>
      <span className="landing-footer-project">A NASA SPACE APPS<br /><strong>CAIRO 2026 PROJECT</strong></span>
    </footer>
  </div>;
}
