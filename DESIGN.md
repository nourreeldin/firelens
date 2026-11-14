# FireLens — DESIGN.md

> Source: [Figma design](https://www.figma.com/design/88S9DxavHRoDQVjwMo2SM4/Untitled?node-id=0-1). Extracted from the **API documentation · Mobile** (`2:73509`) and **Interaction state companions** (`2:73718`) frames through Figma design context. This is a verified **partial design-system extraction**, not an exhaustive audit of every frame in the file. Figma's variable lookup returned no definitions for the inspected mobile frame; values below are observed layer styles, not necessarily published variables.

## 1. Product and design direction

**Product:** FireLens — a scientific geospatial analytics workspace for historical fire hotspot exploration. Its interface is a restrained, light-mode, data-first dashboard. Use navy for hierarchy, slate for secondary text, off-white for the workspace, white for cards, thin cool-gray borders, and warm amber/orange for illustrative warnings and hotspot intensity.

**Principles:** Dense information should remain readable. Keep filters and context visible. Make data states explicit. Distinguish sample/illustrative data from live production data. Prefer subtle borders and whitespace over heavy shadows. Avoid decoration that competes with maps, charts, and data tables.

## 2. Color system

Observed exact values from the inspected Figma frames:

| Role | Hex | Use |
|---|---|---|
| Workspace background | `#F7F8FA` | Main page canvas |
| Surface | `#FFFFFF` | Cards, controls, top navigation |
| Primary ink / brand navy | `#14283F` | Brand mark, titles, primary values, selected outlines |
| Secondary ink | `#253A50` | Control text, section labels |
| Muted text | `#64748B` | Descriptions, metadata, secondary labels |
| Border / divider | `#DEE4EB` | Card borders, input borders, separators |
| Subtle neutral fill | `#EDF1F5` | Avatar, neutral status pills |
| Warning background | `#FFF2E6` | Illustrative notices, selected state pills |
| Warning foreground | `#A94C12` | Warning text and status labels |
| Heatmap low | `#EBC28B` | Lower-intensity calendar cells (observed) |
| Heatmap medium | `#D88B44` | Mid-intensity calendar cells (observed) |
| Heatmap high | `#984817` | Higher-intensity calendar cells (observed) |

Do not interpret the three observed heatmap colors as the complete scientific legend; thresholds and remaining bins are not established by these inspected frames.

## 3. Typography

**Family:** Inter, with sans-serif fallback. Observed weights: Regular (400), Medium (500), Semi Bold (600), Bold (700). Observed line height is frequently `1.45`.

| Role | Observed size / weight |
|---|---|
| Brand name | 20px / 700 |
| Mobile page heading | 23px / 400 |
| State-reference heading | 24px / 400 |
| Large selected metric | 25px / 400 |
| Card title | 15px / 600 |
| Body text | 12–13px / 400 |
| Controls | 12px / 600 |
| Eyebrow and metadata | 10–11px / 400–600 |
| Compact endpoint method | 9px / 700 |

Use sentence case for headings, uppercase for short eyebrow labels and compact statuses. Maintain readable contrast; small text sizes are observed in Figma, but should be increased where accessibility requires it.

## 4. Layout and spacing

Observed mobile API docs frame: **390px wide**. Top navigation: **72px high**, with **16px horizontal padding** and **16px item gap**. Main content: **16px padding**, **20px vertical section gap**. API documentation content uses **24px major vertical gaps**. White cards typically have **16px or 20px internal padding** and **1px borders**.

Observed spacing values include `3, 5, 6, 7, 8, 9, 10, 12, 14, 16, 18, 20, 24, 28px`. Treat these as observed dimensions rather than a formally defined spacing scale.

**Layout rules:**
- Preserve clear separation between global navigation, workspace context filters, page heading, notices, and data panels.
- Mobile: stack content vertically; endpoint navigation becomes a full-width card before endpoint details.
- Maintain filter visibility and selected context when data is loading.
- Do not invent desktop breakpoints or grid widths from the mobile frame; derive them by inspecting desktop frames before implementation.

## 5. Shape, border, and elevation

| Element | Observed radius |
|---|---|
| Primary panel/card | 6px |
| Controls, notices, status pills | 4px |
| Endpoint navigation item | 3px |
| Heatmap cell | 2px |
| Brand mark | 4px |
| Circular avatar | 14px on a 28px square |

Cards: 1px solid `#DEE4EB` on white. Dividers: 1px `#DEE4EB`. No prominent drop shadow was observed in inspected frames; prefer border-defined elevation.

## 6. Component anatomy

### Global header
White background, bottom border, navy brand mark with flame icon, bold FireLens wordmark, utility actions and circular user avatar. Mobile includes a menu icon.

### Workspace context
Show active workspace, location filter, period filter and a small coverage line. Controls use white backgrounds, cool-gray borders, compact labels, chevrons or calendar icons.

### Page heading
Small uppercase muted breadcrumb/eyebrow, prominent navy title, concise muted description.

### Data notice
Warm warning background `#FFF2E6`, foreground `#A94C12`, info icon, compact explanatory copy. Explicitly distinguish planned/illustrative data from live functionality.

### Cards and panels
White surface, subtle border, 6px corners, 16–20px padding, title/subtitle header, restrained internal dividers. Keep charts and tables as the main visual focus.

### Endpoint navigation
Compact list of REST endpoints with method, path, and secondary description. Selected endpoint uses warm-tinted background; other items remain white. The Figma API docs mockup labels endpoints as proposed and not live.

### Burning activity calendar
Small month labels above colored cells. Selected cell uses a **2px navy outline** and a visible numeric count, not color alone. Use a numerical legend and preserve year/month context.

### Status badges
Compact 10px semibold text, 8px horizontal / 4px vertical padding, 4px radius. Warm palette for illustrative/selected indicators; muted neutral fill for passive context.

## 7. Interaction states

Inspected companion frame explicitly documents:

- **Selected:** Navy outline on heatmap cell, visible count, selected badge, details and link to records. Never rely solely on color.
- **Loading:** Visible spinner/status, skeleton rows, preserved active filter badges, and explanatory copy. Do not blank the entire workspace.
- **Empty:** Distinct empty-state icon, concise explanation, recovery action (e.g. clear filters), and contextual help.

The reference frames are static. Actual animation timings, hover transitions, keyboard behavior, and focus-ring dimensions were not established and must be specified separately during implementation.

## 8. Responsive and accessibility guidance

The inspected mobile screen is 390px wide. Prioritize vertical stacking, compact top navigation, and full-width panels. Provide accessible text labels for icon-only actions. Ensure focus indicators, keyboard navigation, semantic controls, and sufficient text contrast. Pair all heatmap colors with numeric values, legends, or outlines. These are implementation recommendations, not all directly specified in the inspected design.

## 9. CSS starter tokens

```css
:root {
  --fl-bg: #f7f8fa;
  --fl-surface: #ffffff;
  --fl-ink: #14283f;
  --fl-ink-secondary: #253a50;
  --fl-muted: #64748b;
  --fl-border: #dee4eb;
  --fl-neutral: #edf1f5;
  --fl-warning-bg: #fff2e6;
  --fl-warning-fg: #a94c12;
  --fl-heat-low: #ebc28b;
  --fl-heat-mid: #d88b44;
  --fl-heat-high: #984817;
  --fl-font: Inter, system-ui, sans-serif;
  --fl-radius-card: 6px;
  --fl-radius-control: 4px;
  --fl-radius-cell: 2px;
}
```

## 10. Implementation rules for AI coding agents

1. Use this file as a **visual reference**, not proof that every token is a Figma variable.
2. Build reusable primitives for cards, controls, badges, headings, notices, and calendar cells.
3. Keep visual hierarchy calm and scientific; avoid heavy gradients, excessive shadows, and oversized rounded corners.
4. Preserve data provenance, sample-data warnings, coverage context, and loading/empty/selected states.
5. Use exact values above where they are observed; do not invent undocumented breakpoints or scientific color thresholds.
6. Validate the implemented UI against the relevant Figma desktop and mobile frames before calling it pixel-accurate.

## 11. Extraction coverage and open items

**Inspected:** `2:73509` API documentation · Mobile; `2:73718` Interaction state companions. **Metadata overview:** Figma Page 1, which contains many more screens. **Unverified:** full desktop screen system, all component variants, all token collections, chart/map color thresholds, interaction timing, breakpoint rules, and accessibility testing. Figma variable definitions returned `{}` for the inspected mobile frame.
