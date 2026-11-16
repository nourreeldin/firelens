export const workspaceViews = [
  { id: "overview", label: "Overview", title: "Workspace overview", description: "Your current selection at a glance. Choose a workspace to explore the data.", group: "Explore" },
  { id: "activity", label: "Fire activity", title: "Fire activity", description: "Follow daily detections, seasonal patterns, and activity over time.", group: "Explore" },
  { id: "map", label: "Fire map", title: "Fire activity map", description: "Explore satellite detections and their geographic distribution.", group: "Explore" },
  { id: "data", label: "Detection records", title: "Detection records", description: "Inspect individual satellite observations and export your selection.", group: "Explore" },
  { id: "analytics", label: "Historical analytics", title: "Historical analytics", description: "Compare observed activity with prior years and inspect anomaly scores.", group: "Analysis" },
  { id: "harmonization", label: "Harmonization", title: "Harmonized activity", description: "Explore corrected grid and daily activity by region and method.", group: "Analysis" },
  { id: "validation", label: "Validation", title: "Validation reports", description: "Review candidate-pair quality reports and the metrics supplied by the backend.", group: "Analysis" },
] as const;

export type WorkspaceView = typeof workspaceViews[number]["id"];

export function workspaceViewFromHash(hash: string): WorkspaceView {
  return workspaceViews.find((view) => `#${view.id}` === hash)?.id ?? "overview";
}
