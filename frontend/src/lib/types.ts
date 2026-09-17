/**
 * HydroWatch Frontend Type Definitions
 * Directly mirrors backend Pydantic models from FastAPI OpenAPI specification.
 */

export interface Coordinates {
  latitude: floatNumber;
  longitude: floatNumber;
}

type floatNumber = number;

export interface GeoBoundingBox {
  min_lat: number;
  max_lat: number;
  min_lon: number;
  max_lon: number;
}

export type RiskLevel = 'LOW' | 'MODERATE' | 'HIGH' | 'EXTREME';
export type WarningStatus = 'NO_ALERT' | 'MONITOR' | 'PREPARE' | 'ACTION' | 'INSUFFICIENT_DATA';
export type WarningUrgency = 'NONE' | 'MONITOR' | 'PREPARE' | 'ACTION';

export interface FeatureShapContribution {
  feature_name: string;
  display_name: string;
  category: 'moisture' | 'instability_pressure' | 'antecedent_rainfall' | 'temperature_wind' | 'climatology' | string;
  observed_value: number;
  shap_value: number;
  impact: 'increases_risk' | 'decreases_risk' | 'neutral';
  percentage_contribution: number;
  description: string;
}

export interface RainfallXaiSummary {
  base_margin: number;
  model_score_margin: number;
  top_positive_drivers: FeatureShapContribution[];
  top_negative_drivers: FeatureShapContribution[];
  all_contributions: FeatureShapContribution[];
  narrative: string;
  causality_chain: string[];
}

export interface UnifiedRainfallSummary {
  probability: number;
  predicted: boolean;
  threshold: number;
  observation_date: string;
  model_version: string;
  historical_records_used: number;
  latest_precipitation_mm: number;
  xai?: RainfallXaiSummary | null;
}

export interface NWPForecastSummary {
  forecast_start_time: string;
  forecast_end_time: string;
  forecast_horizon_hours: number;
  mean_precipitation_mm_hr: number;
  max_hourly_precipitation_mm_hr: number;
  total_precipitation_mm: number;
  max_cape_j_kg?: number | null;
  mean_temperature_c?: number | null;
  mean_humidity_pct?: number | null;
}

export interface UnifiedNwpSummary {
  source: string;
  model_name: string;
  forecast_summary: NWPForecastSummary;
  forecast_horizon_hours: number;
  valid_times: string[];
  peak_hourly_precipitation_mm_hr: number;
  accumulated_precipitation_mm: number;
  max_cape_j_kg?: number | null;
  hourly_precipitation: number[];
}

export interface UnifiedRadarSummary {
  source: string;
  timestamp?: string | null;
  max_reflectivity_dbz: number;
  mean_reflectivity_dbz: number;
  estimated_rain_rate_mm_hr: number;
  coverage_percentage: number;
  tile_url?: string | null;
}

export interface InundationPolygonProperties {
  flooded_area_sq_m: number;
  perimeter_m: number;
  scene_id?: string;
  source?: string;
  acquisition_date?: string;
  water_type?: string;
  is_permanent_water?: boolean;
  [key: string]: unknown;
}

export interface GeoJSONFeature {
  type: 'Feature';
  geometry: {
    type: 'Polygon' | 'MultiPolygon';
    coordinates: number[][][] | number[][][][];
  };
  properties: InundationPolygonProperties;
}

export interface GeoJSONFeatureCollection {
  type: 'FeatureCollection';
  features: GeoJSONFeature[];
}

export interface UnifiedInundationSummary {
  source: string;
  scene: {
    scene_id?: string;
    acquisition_datetime?: string;
    cloud_coverage_percentage?: number;
    sensor?: string;
    resolution_m?: number;
    [key: string]: unknown;
  };
  flooded_area_sq_km: number;
  valid_area_sq_km: number;
  flooded_percentage: number;
  polygon_count: number;
  geojson: GeoJSONFeatureCollection;
  metadata?: {
    raw_water_area_sq_km?: number;
    raw_polygon_count?: number;
    excluded_permanent_water_sq_km?: number;
    permanent_water_polygon_count?: number;
    water_label?: string;
    [key: string]: unknown;
  };
}

export interface SourceExplanation {
  source: string;
  name: string;
  description: string;
  raw_value: unknown;
  normalized_score: number;
  original_weight: number;
  effective_weight: number;
  contribution: number;
  timestamp?: string | null;
  status: string;
}

export interface FusionMetadata {
  policy_applied: 'FULL_EVIDENCE' | 'PARTIAL_EVIDENCE' | 'INSUFFICIENT_EVIDENCE' | string;
  original_weights: Record<string, number>;
  effective_weights: Record<string, number>;
  available_sources: string[];
  unavailable_sources: string[];
  freshness: Record<string, unknown>;
}

export interface UnifiedRiskSummary {
  score: number;
  level: RiskLevel;
  thresholds: Record<string, number>;
  fusion: FusionMetadata;
  explanations: SourceExplanation[];
}

export interface PhysicalTrigger {
  source: string;
  metric: string;
  observed_value: unknown;
  threshold: number;
  triggered: boolean;
  unit: string;
  timestamp?: string | null;
  description: string;
}

export interface WarningDecision {
  status: WarningStatus;
  risk_level: RiskLevel;
  urgency: WarningUrgency;
  triggered: boolean;
  trigger_reasons: string[];
  triggers: PhysicalTrigger[];
  generated_at: string;
  valid_until?: string | null;
  validity_reason: string;
  prototype_only: boolean;
  official_warning_issued: boolean;
  disclaimer: string;
  escalation_notes?: string | null;
}

export interface SourceStatusDetail {
  available: boolean;
  status: 'success' | 'unavailable' | 'failed' | string;
  source: string;
  latency_ms: number;
  timestamp?: string | null;
  error?: string | null;
}

export interface UnifiedTimingDetail {
  weather_model1_ms: number;
  nwp_ms: number;
  radar_ms: number;
  satellite_model2_ms: number;
  fusion_ms: number;
  warning_ms: number;
  total_ms: number;
}

export interface WarningProvenance {
  risk_assessment_id?: string | null;
  model_versions: Record<string, string>;
  source_providers: Record<string, string>;
  source_timestamps: Record<string, string | null>;
  configured_thresholds: Record<string, number>;
  configured_risk_weights: Record<string, number>;
  rules_version: string;
}

export interface UnifiedPredictionResponse {
  status: string;
  request: {
    latitude: number;
    longitude: number;
    prediction_date?: string | null;
    analysis_datetime?: string | null;
    nwp_horizon_hours?: number;
    satellite_date?: string | null;
    satellite_max_cloud?: number;
    min_polygon_area_sq_m?: number;
    location_name?: string | null;
    [key: string]: unknown;
  };
  generated_at: string;
  rainfall_prediction?: UnifiedRainfallSummary | null;
  nwp?: UnifiedNwpSummary | null;
  radar?: UnifiedRadarSummary | null;
  inundation?: UnifiedInundationSummary | null;
  risk: UnifiedRiskSummary;
  warning: WarningDecision;
  source_status: Record<string, SourceStatusDetail>;
  timing: UnifiedTimingDetail;
  provenance: WarningProvenance;
}

export interface UnifiedPredictionRequest {
  latitude: number;
  longitude: number;
  prediction_date?: string;
  analysis_datetime?: string;
  nwp_horizon_hours?: number;
  satellite_date?: string;
  satellite_max_cloud?: number;
  min_polygon_area_sq_m?: number;
  location_name?: string;
}

export interface PresetLocation {
  id: string;
  name: string;
  state: string;
  latitude: number;
  longitude: number;
  defaultZoomAltitude: number;
}
