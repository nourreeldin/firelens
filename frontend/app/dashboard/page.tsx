import type { Metadata } from "next";
import Dashboard from "@/components/dashboard";

export const metadata: Metadata = {
  title: "FireLens | Fire Activity Dashboard",
  description: "Explore raw fire detections, maps, seasonal activity, harmonization, and validation in the FireLens workspace.",
};

export default function DashboardPage() { return <Dashboard />; }
