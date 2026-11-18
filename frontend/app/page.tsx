import type { Metadata } from "next";
import LandingPage from "@/components/landing-page";
import DashboardPreloader from "@/components/dashboard-preloader";
import "./landing.css";

export const metadata: Metadata = {
  title: "FireLens | A Clearer View of Fire on Earth",
  description: "Explore satellite fire observations, seasonal patterns, harmonized activity, and quality reports. A NASA Space Apps Cairo 2026 project built around MODIS and VIIRS observations.",
};

export default function Page() { return <><DashboardPreloader /><LandingPage /></>; }
