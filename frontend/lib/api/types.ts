import type { components } from "./schema";

type Schemas = components["schemas"];

// UI filters use camelCase; response models come directly from OpenAPI.
export type Sensor = Schemas["Sensor"];
export type DateFilters = { startDate: string; endDate: string };
export type Filters = DateFilters & { region: string; sensor: "ALL" | Sensor; bounds?: Partial<Record<keyof BoundingBox, string>> };
export type ValidationFilters = DateFilters & { regionPk: string; methodVersion: string };
export type ActivityFilters = ValidationFilters & { spatialGridId: string };
export type ExportProduct = "fires" | "harmonization" | "validation";

export type BoundingBox = Schemas["BoundingBox"];
export type Region = Schemas["RegionRecord"];
export type RegionOption = Pick<Region, "id" | "country_code" | "name" | "bounding_box" | "centroid">;
export type RegionListResult = Schemas["RegionListResponse"];
export type CatalogRegion = Schemas["RegionCatalogRecord"];
export type RegionCatalogResult = Schemas["RegionCatalogResponse"];
export type HealthResult = Schemas["HealthResponse"];
export type FireDetection = Schemas["FireRecord"];
export type FireListResult = Schemas["FireListResponse"];
export type CalendarDay = Schemas["CalendarDay"];
export type CalendarResult = Schemas["CalendarResponse"];
export type SeasonalResult = Schemas["SeasonalResponse"];
export type ComparisonResult = Schemas["ComparisonResponse"];
export type AnomalyResult = Schemas["AnomalyResponse"];
export type ActivityRecord = Schemas["ActivityRecord"];
export type ActivityListResult = Schemas["ActivityListResponse"];
export type ActivityCalendarDay = Schemas["ActivityCalendarDay"];
export type ActivityCalendarResult = Schemas["ActivityCalendarResponse"];
export type ActivitySeasonalResult = Schemas["HarmonizedSeasonalResponse"];
export type ActivityComparisonResult = Schemas["HarmonizedComparisonResponse"];
export type ActivityAnomalyResult = Schemas["HarmonizedAnomalyResponse"];
export type ValidationReport = Schemas["ValidationRecord"];
export type ValidationListResult = Schemas["ValidationListResponse"];
