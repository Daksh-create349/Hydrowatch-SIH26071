# Backend — Heavy Rainfall & Inundation Prediction System (SIH 2026 PS 26071)

Production-grade FastAPI backend for the AI/ML-Based Integrated Heavy Rainfall Early Warning and Inundation Prediction System (MoES / IMD).

---

## Architectural Layout

```text
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                     # FastAPI application factory & lifecycle
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── router.py           # v1 route aggregator
│   │       └── endpoints/
│   │           ├── __init__.py
│   │           ├── health.py       # GET /health & GET /api/v1/health
│   │           ├── models.py       # ML raw inference & health endpoints
│   │           ├── prediction.py   # POST /api/v1/predict, /rainfall, /inundation, /risk, /warning
│   │           └── data.py         # GET /api/v1/data/nwp & GET /api/v1/data/radar
│   ├── core/
│   │   ├── __init__.py
│   │   ├── config.py               # Pydantic Settings configuration & weights
│   │   ├── logging.py              # Structured logging
│   │   └── errors.py               # Centralized exception models & handlers
│   ├── schemas/                    # Pydantic data contracts
│   │   ├── __init__.py
│   │   ├── common.py               # Coordinates, BoundingBox, Location, Statuses
│   │   ├── weather.py              # DailyWeatherRecord, WeatherFeatureVector
│   │   ├── nwp.py                  # NWPPointForecastResponse, NWPForecastItem
│   │   ├── radar.py                # RadarDataResponse, RadarTileReflectivity
│   │   ├── satellite.py            # SatellitePrecipitation, Sentinel-2 6-bands
│   │   ├── prediction.py           # Pipeline & model prediction schemas
│   │   ├── risk.py                 # RiskAssessmentRequest/Response, Evidence, Explanations
│   │   ├── warning.py              # WarningDecision, Triggers, Freshness, Provenance
│   │   ├── unified.py              # UnifiedPredictionRequest/Response, Status, Timing
│   │   └── response.py             # AnalysisResponse & BaseApiResponse
│   ├── services/                   # Service abstractions & adapters
│   │   ├── __init__.py
│   │   ├── base.py                 # BaseService class
│   │   ├── cache.py                # In-memory TTL data cache
│   │   ├── nasa_power_client.py    # NASA POWER Daily API async client & parser
│   │   ├── feature_builder.py      # Model 1 exact 37-feature engineering
│   │   ├── weather_service.py      # Meteorological ingestion & pipeline service
│   │   ├── nwp_client.py           # Open-Meteo NOAA GFS NWP async client
│   │   ├── nwp_service.py          # Numerical weather prediction service
│   │   ├── radar_client.py         # RainViewer Doppler radar tile client
│   │   ├── radar_service.py        # Doppler weather radar service
│   │   ├── sentinel_client.py      # Earth Search Sentinel-2 STAC client
│   │   ├── raster_processor.py     # COG windowing, tiling, resampling & vectorization
│   │   ├── satellite_imagery_service.py# Sentinel-2 multispectral pipeline
│   │   ├── risk_fusion_service.py  # Deterministic multi-source risk fusion engine
│   │   ├── risk_assessment_service.py # Parallel 4-stream orchestrator
│   │   ├── warning_service.py      # Warning decision & physical trigger engine
│   │   └── unified_prediction_service.py # Primary end-to-end unified orchestrator
│   ├── models/                     # Model architecture definitions (FloodUNet)
│   ├── data/                       # Ingestion & caching utilities
│   └── utils/                      # Geospatial & array helpers
├── tests/                          # Automated pytest suite (132 tests)
│   ├── conftest.py
│   ├── test_health.py
│   ├── test_config.py
│   ├── test_model_inference.py
│   ├── test_prediction_pipeline.py
│   ├── test_weather_service.py
│   ├── test_nwp_service.py
│   ├── test_radar_service.py
│   ├── test_sentinel_catalog.py
│   ├── test_raster_tiling.py
│   ├── test_inundation_pipeline.py
│   ├── test_risk_fusion.py
│   ├── test_risk_pipeline.py
│   ├── test_warning_decision.py
│   ├── test_warning_pipeline.py
│   ├── test_unified_prediction.py
│   ├── test_data_endpoints.py
│   ├── test_services.py
│   └── test_schemas.py
├── requirements.txt                # Pinned dependencies
├── .env.example                    # Environment variable template
└── README.md                       # Documentation
```

---

## Machine Learning Models

The repository contains real trained models:

1. **Model 1 — Heavy Rainfall Prediction (`best_heavy_rain_xgboost_v2.json` / `.pkl`):**
   - XGBoost binary classifier predicting next-day heavy rainfall probability.
   - Input: 37 leakage-safe historical weather features.
   - Untouched test metrics: Accuracy 92.27%, Precision 41.19%, Recall 61.13%, F1 0.4921, ROC-AUC 0.9228, PR-AUC 0.5138.
2. **Model 2 — Flood Inundation Segmentation (`best_model.pth`):**
   - 6-band Sentinel-2 U-Net architecture (`FloodUNet`).
   - Input bands: `B2`, `B3`, `B4`, `B8`, `B11`, `B12`.
   - Untouched test metrics: Pixel Accuracy 97.79%, IoU 83.84%, Dice/F1 91.21%, Precision 90.95%, Recall 91.47%.

---

## Running Backend Locally

### 1. Environment Setup

```bash
# Create and activate virtual environment (if not already active)
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r backend/requirements.txt
```

### 2. Configure Environment

Copy `.env.example` to `.env` or set environment variables:

```bash
cp backend/.env.example .env
```

### 3. Start Development Server

Run from the repository root:

```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Interactive API documentation will be available at:
- Swagger UI: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`
- Health Check: `http://127.0.0.1:8000/health` or `http://127.0.0.1:8000/api/v1/health`

---

## Environment Variables

| Variable | Type | Default | Description |
|:---|:---|:---|:---|
| `ENVIRONMENT` | string | `development` | Runtime environment (`development`, `production`, `testing`) |
| `API_PREFIX` | string | `/api/v1` | URL prefix for versioned endpoints |
| `LOG_LEVEL` | string | `INFO` | Logging level (`DEBUG`, `INFO`, `WARNING`, `ERROR`) |
| `MODEL1_PATH` | string | `best_heavy_rain_xgboost_v2.json` | Path to Model 1 weights file |
| `MODEL2_PATH` | string | `best_model.pth` | Path to Model 2 checkpoint file |
| `MODEL1_THRESHOLD` | float | `0.81` | Frozen validation decision threshold for Model 1 |
| `MODEL2_THRESHOLD` | float | `0.5` | Probability threshold for binary flood segmentation |
| `MODEL2_DEVICE` | string | `auto` | Execution device (`auto`, `cpu`, `cuda`, `mps`) |
| `DATA_CACHE_DIR` | string | `data_cache` | Local directory for cached geospatial rasters |
| `ALLOWED_ORIGINS` | string / list | `http://localhost:3000,http://localhost:5173` | Allowed CORS origins (comma-separated) |

---

## ML Model Inference Endpoints

### 1. Model Health Check
`GET /api/v1/models/health`

Returns real in-memory load state, model type, checkpoint path, device, and applied thresholds.

```json
{
  "status": "healthy",
  "models": {
    "model1_heavy_rain_xgboost": {
      "loaded": true,
      "path_configured": true,
      "model_type": "xgboost",
      "checkpoint_path": "/path/to/best_heavy_rain_xgboost_v2.json",
      "threshold": 0.81,
      "device": "cpu",
      "details": { "feature_count": 37, "last_error": null }
    },
    "model2_flood_unet": {
      "loaded": true,
      "path_configured": true,
      "model_type": "pytorch_unet",
      "checkpoint_path": "/path/to/best_model.pth",
      "threshold": 0.5,
      "device": "cpu",
      "details": { "input_bands": ["B2", "B3", "B4", "B8", "B11", "B12"], "input_channels": 6 }
    }
  }
}
```

### 1. Real End-to-End Heavy Rainfall Prediction Pipeline
`POST /api/v1/predict/rainfall`

Fetches real historical meteorological observations from NASA POWER Daily API (past 30+ days through $D-1$), computes the exact 37 Model 1 features without future leakage, and runs real XGBoost inference.

**Request:**
```json
{
  "latitude": 19.0760,
  "longitude": 72.8777,
  "prediction_date": "2024-07-15",
  "location_name": "Mumbai"
}
```

**Response:**
```json
{
  "status": "success",
  "prediction_date": "2024-07-15",
  "observation_date": "2024-07-14",
  "coordinates": { "latitude": 19.076, "longitude": 72.8777 },
  "location_name": "Mumbai",
  "heavy_rain_predicted": true,
  "heavy_rain_probability": 0.9689,
  "threshold": 0.81,
  "model_version": "heavy_rainfall_xgboost_v2",
  "historical_records_used": 41,
  "features_computed": 37,
  "latest_weather": {
    "date": "2024-07-14",
    "PRECTOTCORR": 53.06,
    "T2M": 27.19,
    "T2MDEW": 26.08,
    "RH2M": 93.61,
    "PS": 99.08,
    "WS2M": 4.3,
    "WS10M": 5.78,
    "ALLSKY_SFC_SW_DWN": 12.75
  },
  "metadata": {
    "frozen_threshold": 0.81,
    "lookback_window_days": 30,
    "data_source": "NASA_POWER_DAILY_POINT_API",
    "community": "AG"
  }
}
```

### 2. Heavy Rainfall Raw Feature Inference
`POST /api/v1/models/rainfall/predict`

Accepts JSON with pre-calculated 37 meteorological features in exact training order.

**Request:**
```json
{
  "location": { "latitude": 19.0760, "longitude": 72.8777 },
  "features": {
    "PRECTOTCORR": 14.2, "T2M": 29.1, "T2MDEW": 24.5, "RH2M": 84.0, "PS": 100.2,
    "WS2M": 4.1, "WS10M": 6.0, "ALLSKY_SFC_SW_DWN": 16.5,
    "rain_lag_1d": 8.0, "rain_lag_2d": 3.0, "rain_lag_3d": 0.0, "rain_lag_7d": 20.0, "rain_lag_14d": 45.0,
    "rain_sum_prev_3d": 11.0, "rain_sum_prev_7d": 31.0, "rain_sum_prev_14d": 76.0, "rain_sum_prev_30d": 160.0,
    "rain_mean_prev_7d": 4.43, "rain_max_prev_7d": 18.0,
    "T2M_lag_1d": 28.8, "T2MDEW_lag_1d": 24.2, "RH2M_lag_1d": 82.5, "PS_lag_1d": 100.3,
    "WS2M_lag_1d": 3.8, "WS10M_lag_1d": 5.5, "ALLSKY_SFC_SW_DWN_lag_1d": 16.0,
    "temperature_change_1d": 0.3, "humidity_change_1d": 1.5, "pressure_change_1d": -0.1, "wind_change_1d": 0.3,
    "month": 7, "month_sin": -0.5, "month_cos": -0.866, "doy_sin": 0.12, "doy_cos": 0.99,
    "latitude": 19.0760, "longitude": 72.8777
  }
}
```

**Response:**
```json
{
  "model": "heavy_rainfall_xgboost_v2",
  "probability": 0.8315,
  "threshold": 0.81,
  "heavy_rain": true,
  "prediction": "heavy_rain",
  "feature_count": 37,
  "metadata": { "frozen_threshold": 0.81 }
}
```

### 3. Flood Inundation Segmentation
`POST /api/v1/models/inundation/predict` (JSON array) or `POST /api/v1/models/inundation/predict-raster` (File upload `.npy` / `.tif`)

**Expected Sentinel-2 Band Order:**
`[B2, B3, B4, B8, B11, B12]`

**Preprocessing Applied:**
1. Cast to `float32`
2. Divide by `10000.0` (reflectance scale)
3. Non-finite values replaced with `0.0`
4. Clipped to `[0.0, 1.0]`

**Response:**
```json
{
  "model": "flood_unet_sentinel2_6band",
  "dimensions": [512, 512],
  "water_pixel_count": 45210,
  "total_valid_pixels": 262144,
  "flooded_area_percentage": 17.25,
  "threshold": 0.5,
  "device": "cpu",
  "probability_mask": [[...]],
  "binary_mask": [[...]]
}
```

### 4. Numerical Weather Prediction (NWP) Forecast
`GET /api/v1/data/nwp`

Fetches real hourly atmospheric forecasts from NOAA Global Forecast System (GFS 0.25° grid) via Open-Meteo API.

**Parameters:**
- `latitude` (float, -90 to 90)
- `longitude` (float, -180 to 180)
- `forecast_days` (int, 1 to 16, default: 3)

**Response:**
```json
{
  "status": "success",
  "source": "Open-Meteo GFS (NOAA 0.25° Seamless)",
  "model_name": "gfs_seamless",
  "coordinates": { "latitude": 19.076, "longitude": 72.8777 },
  "elevation_m": 14.0,
  "generated_at": "2026-09-16T13:25:00Z",
  "forecast_horizon_hours": 72,
  "forecast_count": 72,
  "units": {
    "precipitation": "mm/hour",
    "temperature": "°C",
    "relative_humidity": "%",
    "surface_pressure": "hPa / kPa",
    "wind_speed": "m/s",
    "cape": "J/kg"
  },
  "summary": {
    "total_precipitation_mm": 5.8,
    "max_hourly_precipitation_mm_hr": 0.9,
    "min_temperature_c": 25.6,
    "max_temperature_c": 31.4,
    "max_wind_speed_ms": 5.25,
    "max_cape_j_kg": 1210.0
  },
  "forecasts": [
    {
      "valid_time": "2026-09-16T00:00",
      "lead_hours": 0,
      "precipitation_mm_hr": 0.1,
      "temperature_2m_c": 25.8,
      "relative_humidity_pct": 86.0,
      "dew_point_2m_c": 23.3,
      "surface_pressure_hpa": 1010.0,
      "surface_pressure_kpa": 101.0,
      "wind_speed_10m_ms": 3.45,
      "cape_j_kg": 40.0
    }
  ]
}
```

### 5. Doppler Weather Radar (DWR) Reflectivity
`GET /api/v1/data/radar`

Fetches live operational Doppler weather radar composite from RainViewer Radar Network, decodes Web Mercator raster tiles, and extracts peak reflectivity (dBZ), echo coverage, and estimated rainfall intensity via Marshall-Palmer $Z = 200 R^{1.6}$.

**Parameters:**
- `latitude` (float, -90 to 90)
- `longitude` (float, -180 to 180)
- `zoom` (int, 0 to 14, default: 6)

---

### Inundation Prediction Pipeline Endpoint

`POST /api/v1/predict/inundation`

Discovers real Sentinel-2 Level-2A imagery from Element 84 Earth Search STAC catalog, streams the 6 required spectral bands via Cloud-Optimized GeoTIFF (COG) HTTP range requests, resamples 20m bands to 10m common grid using bilinear interpolation, runs real Model 2 PyTorch `FloodUNet` inference over 512x512 windows with 64px overlap, reconstructs a seamless probability mosaic, thresholds at 0.5, and vectorizes into WGS84 GeoJSON polygons with geodesic surface area calculations.

**Request:**
```json
{
  "latitude": 18.97,
  "longitude": 72.82,
  "date": "2024-02-01",
  "max_cloud_percentage": 20.0,
  "min_polygon_area_sq_m": 500.0,
  "location_name": "Mumbai Coastal Region"
}
```

**Response:**
```json
{
  "status": "success",
  "requested_location": { "latitude": 18.97, "longitude": 72.82 },
  "location_name": "Mumbai Coastal Region",
  "selected_scene": {
    "scene_id": "S2B_43QBB_20240201_0_L2A",
    "collection": "sentinel-2-l2a",
    "acquisition_datetime": "2024-02-01T05:53:37.692000Z",
    "processing_level": "Level-2A",
    "cloud_coverage": 6.02,
    "crs": "EPSG:32643",
    "selection_reason": "Deterministically selected from 10 candidates: closest to target (0.2 days delta), lowest cloud coverage (6.0%), verified all 6 required bands [B2, B3, B4, B8, B11, B12]."
  },
  "model_version": "flood_unet_sentinel2_6band",
  "threshold": 0.5,
  "grid_resolution_m": 10.0,
  "raster_dimensions": [1024, 1024],
  "valid_area_sq_km": 104.858,
  "flooded_area_sq_km": 87.165,
  "flooded_percentage": 83.13,
  "polygon_count": 86,
  "geojson": {
    "type": "FeatureCollection",
    "features": [
      {
        "type": "Feature",
        "geometry": {
          "type": "Polygon",
          "coordinates": [[[72.809843, 18.958834], ...]]
        },
        "properties": {
          "flooded_area_sq_m": 700.0,
          "perimeter_m": 108.28,
          "scene_id": "S2B_43QBB_20240201_0_L2A",
          "acquisition_time": "2024-02-01T05:53:37.692000Z",
          "source": "Sentinel-2 L2A",
          "model_version": "FloodUNet_v1"
        }
      }
    ]
  },
  "metadata": {
    "input_bands": ["B2", "B3", "B4", "B8", "B11", "B12"],
    "reflectance_scale": 10000.0,
    "crs": "EPSG:32643"
  }
}
```

---

### Integrated Multi-Source Risk Assessment Pipeline

`POST /api/v1/predict/risk`

Concurrently ingests real environmental data across 4 independent sources:
1. **Real Model 1 XGBoost Heavy-Rainfall Inference** (37 features constructed from NASA POWER Daily API records)
2. **Real NOAA GFS Numerical Weather Prediction** (0.25° grid via Open-Meteo GFS Seamless API)
3. **Real Doppler Weather Radar Nowcast** (RainViewer composite radar tile decoding and Marshall-Palmer conversion)
4. **Real Sentinel-2 Level-2A Flood Inundation Segmentation** (Earth Search STAC discovery, COG windowing, and Model 2 PyTorch FloodUNet inference)

#### Fusion Formulation & Missing-Source Policy
Baseline static weights configured in `backend/app/core/config.py`:
- Heavy Rainfall Model ($w_1$): `0.35`
- NWP Forecast ($w_2$): `0.25`
- Radar Nowcast ($w_3$): `0.20`
- Sentinel-2 Inundation ($w_4$): `0.20`
(Sum $\sum w_i = 1.0$)

When $K$ sources are available ($2 \le K < 4$), weights are dynamically renormalized:
$$w'_i = \frac{w_i}{\sum_{j \in \text{available}} w_j}, \quad S_{\text{composite}} = \sum_{i \in \text{available}} w'_i \cdot S_i \in [0.0, 1.0]$$

If fewer than 2 sources are available, the endpoint rejects the request with HTTP 422 (`INSUFFICIENT_HISTORICAL_DATA`). Fake or mock data is strictly forbidden.

#### Satellite Staleness Discounting
Real Sentinel-2 acquisitions are categorized by temporal freshness relative to analysis time:
- `CURRENT` ($\le 48$ hours): $1.0\times$ multiplier
- `RECENT` ($48 - 168$ hours): $0.75\times$ multiplier
- `HISTORICAL` ($> 168$ hours): $0.50\times$ multiplier

#### Mathematical Explainability & Prototype Warning
Every response includes:
- Exact mathematical decomposition: for each stream, $\text{contribution} = w'_{\text{effective}} \times S_{\text{normalized}}$
- Sum of contributions strictly equals the composite risk score
- Prototype warning candidate with derived urgency (`NONE`, `MONITOR`, `PREPARE`, `ACTION`), specific physical trigger reasons, and an explicit disclaimer distinguishing experimental prototype assessments from official IMD warnings.

**Request:**
```json
{
  "latitude": 19.0760,
  "longitude": 72.8777,
  "prediction_date": "2024-02-15",
  "nwp_horizon_hours": 24,
  "satellite_max_cloud": 25.0,
  "location_name": "Mumbai Operational Site"
}
```

**Response:**
```json
{
  "status": "success",
  "requested_location": { "latitude": 19.076, "longitude": 72.8777 },
  "location_name": "Mumbai Operational Site",
  "risk": {
    "score": 0.1773,
    "level": "LOW",
    "thresholds": { "low_max": 0.3, "moderate_max": 0.6, "high_max": 0.8 }
  },
  "fusion": {
    "policy_applied": "FULL_EVIDENCE",
    "original_weights": {
      "heavy_rainfall_model": 0.35,
      "nwp_forecast": 0.25,
      "radar_nowcast": 0.2,
      "satellite_inundation": 0.2
    },
    "effective_weights": {
      "heavy_rainfall_model": 0.35,
      "nwp_forecast": 0.25,
      "radar_nowcast": 0.2,
      "satellite_inundation": 0.2
    },
    "available_sources": ["heavy_rainfall_model", "nwp_forecast", "radar_nowcast", "satellite_inundation"],
    "unavailable_sources": []
  },
  "explanations": [
    {
      "source": "heavy_rainfall_model",
      "name": "Model 1 (Next-Day Heavy Rainfall XGBoost)",
      "description": "Predicted heavy rainfall probability: 0.0018 (decision threshold: 0.81).",
      "raw_value": 0.0018,
      "normalized_score": 0.0018,
      "effective_weight": 0.35,
      "contribution": 0.0006,
      "status": "available"
    },
    {
      "source": "nwp_forecast",
      "name": "NOAA GFS Numerical Weather Prediction",
      "description": "Peak forecast intensity: 0.3 mm/hr, 24h accumulated rain: 1.6 mm.",
      "raw_value": { "max_hourly_mm_hr": 0.3, "accumulated_mm": 1.6 },
      "normalized_score": 0.0108,
      "effective_weight": 0.25,
      "contribution": 0.0027,
      "status": "available"
    },
    {
      "source": "radar_nowcast",
      "name": "RainViewer Doppler Weather Radar Composite",
      "description": "Peak reflectivity: 48.8 dBZ, estimated rain rate: 40.9 mm/hr.",
      "raw_value": { "max_dbz": 48.8, "rain_rate_mm_hr": 40.9 },
      "normalized_score": 0.821,
      "effective_weight": 0.2,
      "contribution": 0.1642,
      "status": "available"
    },
    {
      "source": "satellite_inundation",
      "name": "Sentinel-2 L2A / Model 2 FloodUNet Inundation",
      "description": "Flooded area: 3.09 km² (3.0% of valid ground footprint), polygons: 154, status: HISTORICAL (age: 22640.3h).",
      "raw_value": { "flooded_area_sq_km": 3.09, "flooded_percentage": 3.0 },
      "normalized_score": 0.0492,
      "effective_weight": 0.2,
      "contribution": 0.0098,
      "status": "historical"
    }
  ],
  "prototype_warning_assessment": {
    "risk_level": "LOW",
    "urgency": "NONE",
    "trigger_reasons": [
      "Doppler radar reflectivity (48.8 dBZ) indicates intense convective precipitation core."
    ],
    "recommended_monitoring": "Routine meteorological and satellite monitoring.",
    "disclaimer": "EXPERIMENTAL PROTOTYPE DECISION ASSESSMENT DEVELOPED FOR SIH 2026 PS 26071. NOT AN OFFICIAL IMD GOVERNMENT WEATHER WARNING."
  }
}
```

---

### Deterministic Flood Warning Decision & Trigger Evaluation

`POST /api/v1/predict/warning`

Translates the multi-source risk assessment into machine-readable prototype warning states, operational urgencies, concrete physical trigger metrics, evidence freshness disclosures, forward temporal validity, and model provenance.

#### State Machine Mapping
- `LOW` $\to$ `NO_ALERT` (Urgency: `NONE`)
- `MODERATE` $\to$ `MONITOR` (Urgency: `MONITOR`)
- `HIGH` $\to$ `PREPARE` (Urgency: `PREPARE`)
- `EXTREME` $\to$ `ACTION` (Urgency: `ACTION`)
- $<2$ sources available $\to$ `INSUFFICIENT_DATA` (Urgency: `NONE`, HTTP 422 if directly requested)

#### Concrete Physical Triggers Evaluated
| Source | Metric | Configured Threshold | Physical Meaning |
|---|---|---|---|
| Model 1 | `heavy_rain_probability` | `0.81` | Model 1 heavy rainfall ML decision threshold |
| Model 1 | `observed_precipitation_mm` | `64.5 mm/day` | IMD heavy rainfall classification |
| NWP | `max_hourly_precipitation_mm_hr` | `20.0 mm/hr` | Intense convective rainfall intensity |
| NWP | `accumulated_precipitation_mm` | `70.0 mm` | Severe flash flood accumulation |
| Radar | `max_reflectivity_dbz` | `45.0 dBZ` | Intense convective precipitation core |
| Radar | `estimated_peak_rain_rate_mm_hr` | `30.0 mm/hr` | Marshall-Palmer instantaneous rain rate |
| Satellite | `flooded_percentage` | `10.0 %` | Significant surface water footprint |
| Satellite | `flooded_area_sq_km` | `5.0 km²` | WGS84 geodesic inundated extent |

#### Physical Burst Discrepancy Disclosure
If a real-time observation indicates a severe convective burst (e.g. radar $\ge 50.0\text{ dBZ}$ or NWP $\ge 35.0\text{ mm/hr}$) while the composite risk score remains at `NO_ALERT` or `MONITOR` due to dry historical lag records or multi-source weighting, the engine records an explicit `escalation_notes` disclosure rather than silently manipulating or fabricating the composite score.

#### Temporal Validity & Stale Data Disclosure
- Live Radar Active: Forward validity window governed by nowcast duration (3 hours from scan timestamp).
- NWP Active Fallback: Forward validity window governed by synoptic model cycle (12 hours).
- Only Historical Satellite: `valid_until = null`, with explicit reason explaining forward validity cannot be established from historical scenes.
- Mandatory disclaimer: **"EXPERIMENTAL PROTOTYPE ASSESSMENT FOR SIH 2026 PS 26071. NOT AN OFFICIAL IMD GOVERNMENT WARNING. NOT SANCTIONED FOR OFFICIAL EMERGENCY BROADCAST."**

**Request:**
```json
{
  "latitude": 19.0760,
  "longitude": 72.8777,
  "prediction_date": "2024-02-15",
  "nwp_horizon_hours": 24,
  "satellite_max_cloud": 25.0,
  "location_name": "Mumbai City"
}
```

**Response:**
```json
{
  "status": "success",
  "requested_location": { "latitude": 19.076, "longitude": 72.8777 },
  "location_name": "Mumbai City",
  "risk": {
    "score": 0.1773,
    "level": "LOW",
    "thresholds": { "low_max": 0.3, "moderate_max": 0.6, "high_max": 0.8 }
  },
  "warning": {
    "status": "NO_ALERT",
    "risk_level": "LOW",
    "urgency": "NONE",
    "triggered": true,
    "trigger_reasons": [
      "Doppler radar reflectivity reached 48.8 dBZ (severe convective threshold: 45.0 dBZ).",
      "Radar Marshall-Palmer nowcast indicates peak rain rate of 40.9 mm/hr."
    ],
    "triggers": [
      {
        "source": "heavy_rainfall_model",
        "metric": "heavy_rain_probability",
        "observed_value": 0.0018,
        "threshold": 0.81,
        "triggered": false,
        "unit": "probability",
        "timestamp": "2024-02-14",
        "description": "Model 1 heavy rainfall probability (0.0018) vs threshold (0.81)."
      },
      {
        "source": "radar_nowcast",
        "metric": "max_reflectivity_dbz",
        "observed_value": 48.8,
        "threshold": 45.0,
        "triggered": true,
        "unit": "dBZ",
        "timestamp": "2026-09-16T14:20:00+00:00",
        "description": "Peak Doppler radar reflectivity (48.8 dBZ) vs convective threshold (45.0 dBZ)."
      }
    ],
    "generated_at": "2026-09-16T14:23:45+00:00",
    "valid_until": "2026-09-16T17:20:00+00:00",
    "validity_reason": "Governed by Doppler radar nowcast window (3h validity from scan acquisition 2026-09-16T14:20:00+00:00).",
    "prototype_only": true,
    "official_warning_issued": false,
    "disclaimer": "EXPERIMENTAL PROTOTYPE ASSESSMENT FOR SIH 2026 PS 26071. NOT AN OFFICIAL IMD GOVERNMENT WARNING. NOT SANCTIONED FOR OFFICIAL EMERGENCY BROADCAST.",
    "escalation_notes": "DISCREPANCY DISCLOSURE: Physical observation indicates intense burst (Doppler radar reflectivity (>= 50 dBZ)), while composite risk score (0.1773) remains at NO_ALERT due to multi-source weight damping. Heightened situational vigilance recommended."
  },
  "evidence_freshness": {
    "current_sources": ["heavy_rainfall_model", "nwp_forecast", "radar_nowcast"],
    "stale_sources": [],
    "historical_sources": ["satellite_inundation"],
    "source_timestamps": {
      "heavy_rainfall_model": "2024-02-14",
      "nwp_forecast": "2026-09-16T14:00:00Z",
      "radar_nowcast": "2026-09-16T14:20:00+00:00",
      "satellite_inundation": "2024-02-16T05:50:31Z"
    },
    "satellite_is_historical": true
  },
  "source_provenance": {
    "risk_assessment_id": "risk_eval_d93c19be3cfbc2bc",
    "model_versions": {
      "heavy_rainfall_model": "heavy_rainfall_xgboost_v2",
      "flood_inundation_model": "flood_unet_sentinel2_6band"
    },
    "source_providers": {
      "heavy_rainfall_model": "NASA POWER Daily Meteorology API",
      "nwp_forecast": "NOAA GFS 0.25° via Open-Meteo GFS Seamless",
      "radar_nowcast": "RainViewer Global Doppler Radar Composite Network",
      "satellite_inundation": "Sentinel-2 L2A via Element 84 Earth Search STAC"
    },
    "rules_version": "v1.0_prototype_sih2026"
  }
}
```

---

## Unified End-to-End Prediction Pipeline (`POST /api/v1/predict`)

The unified prediction pipeline is the **primary frontend integration endpoint**. It coordinates the entire system in a single request:
1. **Concurrent Ingestion (Stage A):** Ingests real data across NASA POWER (weather), Open-Meteo GFS (NWP), RainViewer (Doppler radar), and Element 84 Earth Search (Sentinel-2 L2A).
2. **In-Process ML Inference:** Reuses existing singleton services for Model 1 (XGBoost) and Model 2 (FloodUNet); never makes internal HTTP calls.
3. **Multi-Source Risk Fusion (Stage B):** Deterministically fuses evidence with dynamic weight renormalization under missing-source policy ($\ge 2$ sources required).
4. **Deterministic Warning Decision (Stage C):** Evaluates 8 concrete physical triggers, operational states (`NO_ALERT`, `MONITOR`, `PREPARE`, `ACTION`, `INSUFFICIENT_DATA`), forward temporal validity, and physical burst discrepancy disclosures.
5. **Rich Frontend Assembly (Stage D):** Emits rainfall metrics, NWP forecasts, radar reflectivity, vector WGS84 GeoJSON polygons, composite risk, warning triggers, source availability/error health, timing breakdown, and provenance.

### Request Payload (`POST /api/v1/predict`)

```json
{
  "latitude": 19.0760,
  "longitude": 72.8777,
  "prediction_date": "2024-07-15",
  "nwp_horizon_hours": 24,
  "satellite_date": "2024-01-15",
  "satellite_max_cloud": 25.0,
  "min_polygon_area_sq_m": 1000.0,
  "location_name": "Mumbai Test Station"
}
```

### Response Payload Structure

```json
{
  "status": "success",
  "request": { "latitude": 19.076, "longitude": 72.8777, ... },
  "generated_at": "2026-09-16T14:52:32Z",
  "rainfall_prediction": {
    "probability": 0.9689,
    "predicted": true,
    "threshold": 0.81,
    "observation_date": "2024-07-14",
    "model_version": "heavy_rainfall_xgboost_v2",
    "historical_records_used": 30,
    "latest_precipitation_mm": 45.2
  },
  "nwp": {
    "source": "Open-Meteo GFS (NOAA 0.25° Seamless)",
    "model_name": "GFS_0.25",
    "forecast_summary": { "total_precipitation_mm": 1.6, ... },
    "forecast_horizon_hours": 24,
    "valid_times": ["2026-09-16T15:00:00Z", ...],
    "peak_hourly_precipitation_mm_hr": 0.3,
    "accumulated_precipitation_mm": 1.6,
    "max_cape_j_kg": 920.0
  },
  "radar": {
    "source": "RainViewer Global Doppler Radar Composite",
    "timestamp": "2026-09-16T14:50:00+00:00",
    "max_reflectivity_dbz": 50.1,
    "mean_reflectivity_dbz": 28.8,
    "estimated_rain_rate_mm_hr": 49.33,
    "coverage_percentage": 0.35,
    "tile_url": "https://tilecache.rainviewer.com/v2/radar/..."
  },
  "inundation": {
    "source": "Sentinel-2 L2A via Element 84 Earth Search",
    "scene": { "scene_id": "S2B_42QZG_...", ... },
    "flooded_area_sq_km": 3.202,
    "valid_area_sq_km": 26.2,
    "flooded_percentage": 12.22,
    "polygon_count": 196,
    "geojson": { "type": "FeatureCollection", "features": [...] }
  },
  "risk": {
    "score": 0.5341,
    "level": "MODERATE",
    "thresholds": { "LOW_MAX": 0.30, "MODERATE_MAX": 0.60, "HIGH_MAX": 0.80 },
    "fusion": {
      "policy_applied": "FULL_EVIDENCE",
      "effective_weights": { "heavy_rainfall_model": 0.35, "nwp_forecast": 0.25, "radar_nowcast": 0.20, "satellite_inundation": 0.20 }
    },
    "explanations": [...]
  },
  "warning": {
    "status": "MONITOR",
    "urgency": "MONITOR",
    "triggered": true,
    "triggers": [...],
    "valid_until": "2026-09-16T17:50:00+00:00",
    "validity_reason": "Governed by Doppler radar nowcast window (3h validity).",
    "prototype_only": true,
    "official_warning_issued": false,
    "disclaimer": "EXPERIMENTAL PROTOTYPE ASSESSMENT FOR SIH 2026 PS 26071. NOT AN OFFICIAL IMD GOVERNMENT WARNING."
  },
  "source_status": {
    "weather_model1": { "available": true, "status": "success", "latency_ms": 877.5, "error": null },
    "nwp": { "available": true, "status": "success", "latency_ms": 745.0, "error": null },
    "radar": { "available": true, "status": "success", "latency_ms": 1338.4, "error": null },
    "satellite_model2": { "available": true, "status": "success", "latency_ms": 8171.5, "error": null }
  },
  "timing": {
    "weather_model1_ms": 877.5,
    "nwp_ms": 745.0,
    "radar_ms": 1338.4,
    "satellite_model2_ms": 8171.5,
    "fusion_ms": 0.1,
    "warning_ms": 0.1,
    "total_ms": 8215.3
  },
  "provenance": { ... }
}
```

---

## Running Automated Tests

Run the complete test suite:

```bash
python3 -m pytest backend/tests -v
```

All 132 tests execute in ~8.3 seconds with 100% pass rate:
- Settings parsing, risk weight validation, and path resolution
- Direct `/health` and versioned `/api/v1/health`
- Real XGBoost model loading, feature ordering, and threshold logic (0.81)
- Real PyTorch FloodUNet checkpoint loading, 7.76M parameter count, 6-band tensor shapes, and threshold (0.5)
- NASA POWER API client retry, timeout, and response parser
- Model 1 feature engineering (exact 37 features, lags, rolling sums/stats, differences, calendar cyclicals, zero future leakage)
- Pipeline API endpoint: `POST /api/v1/predict/rainfall` with mocked transport and real XGBoost inference
- Open-Meteo NOAA GFS client, response parsing, unit conversions, pressure scaling, and summary statistics
- RainViewer Doppler radar client, Slippy tile math, bounding box calculation, PIL PNG tile decoding, active echo masks, and Marshall-Palmer rain rates
- Data API endpoints: `GET /api/v1/data/nwp` and `GET /api/v1/data/radar`
- Sentinel-2 STAC catalog client, 6-band verification, cloud filtering, and deterministic scene selection
- Sentinel-2 COG adaptive band range reading, 20m to 10m bilinear resampling, 512x512 windowing, and probability mosaic reconstruction
- OpenCV contour vectorization, interior hole handling, noise filtering, WGS84 geodesic coordinate transform, and area calculations
- Inundation pipeline endpoint: `POST /api/v1/predict/inundation` end-to-end with real Model 2 checkpoint inference
- Multi-source risk normalization math (Model 1 probability, NWP rainfall/CAPE, radar dBZ/rain rate, satellite inundation temporal discounting)
- Missing-source policy enforcement (4 sources full, 3 or 2 sources dynamic renormalization, <2 sources 422 error)
- Mathematical explainability decomposition and contribution sum integrity
- Prototype warning candidate generation and explicit IMD disclaimer
- Risk pipeline endpoint: `POST /api/v1/predict/risk` end-to-end with mocked transports and parameter validation
- Warning decision state machine (`NO_ALERT`, `MONITOR`, `PREPARE`, `ACTION`, `INSUFFICIENT_DATA`)
- Physical trigger evaluations across all 4 streams (rainfall, NWP, radar, inundation)
- Forward temporal validity windows and historical satellite disclosure (`valid_until = null`)
- Discrepancy disclosures for severe physical bursts under damped composite scores
- Warning pipeline endpoint: `POST /api/v1/predict/warning` end-to-end with mocked transports and parameter validation
- Unified pipeline endpoint: `POST /api/v1/predict` (and trailing slash alias) end-to-end with concurrent orchestration, GeoJSON polygons, latency profiling, and audit provenance
- API endpoints: `/api/v1/models/health`, `/api/v1/models/rainfall/predict`, `/api/v1/models/inundation/predict`
- Schema validation, coordinate boundaries, and error handlers

---

## Known Limitations

- Real-time in-situ IMD AWS hardware sensor telemetry and dedicated ground radar volume scan feeds are not connected directly on-premise; public composite APIs provide real live data.
- Warning decision evaluations are experimental decision aids for SIH 2026 PS 26071 and do not constitute official IMD government warnings. External dissemination (SMS/WhatsApp/email) is not implemented.
