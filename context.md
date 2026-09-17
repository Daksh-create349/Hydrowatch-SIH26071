# Project Context — SIH 2026 Problem Statement 26071

## Project Metadata

- **SIH Problem Statement ID:** 26071
- **Title:** AI/ML-Based Integrated Heavy Rainfall Early Warning and Inundation Prediction System using Satellite, Radar, Observational Weather and Numerical Weather Prediction Model Data.
- **Organization:** Ministry of Earth Sciences (MoES)
- **Department:** India Meteorological Department (IMD)
- **Category:** Software
- **Theme:** Disaster Management

---

## Current Status

- **Model 1 (Heavy Rainfall Prediction):** Trained and verified (`best_heavy_rain_xgboost_v2.json`, 37 features, threshold 0.81). Operational via `POST /api/v1/predict/rainfall`.
- **Model 2 (Inundation / Flood Segmentation):** Trained and verified (`best_model.pth`, FloodUNet 7.76M params, 6 Sentinel-2 bands, threshold 0.5). Operational via `POST /api/v1/predict/inundation`.
- **Weather / Radar / NWP Data Pipelines:** Operational via NASA POWER Daily API, Open-Meteo NOAA GFS 0.25°, and RainViewer Doppler radar composites.
- **Risk Fusion Engine (Prompt 6):** Operational via `POST /api/v1/predict/risk`. Multi-source deterministic fusion combining Model 1, NOAA GFS, RainViewer radar, and Sentinel-2 / Model 2 inundation with dynamic weight renormalization, missing-source policy, temporal freshness discounting, mathematical explainability, and prototype warning candidates.
- **Warning Decision Layer (Prompt 7):** Operational via `POST /api/v1/predict/warning`. Deterministic state machine (`NO_ALERT`, `MONITOR`, `PREPARE`, `ACTION`, `INSUFFICIENT_DATA`), concrete physical triggers (rainfall, NWP, radar, inundation), evidence freshness disclosures, forward validity windows, discrepancy disclosures for severe bursts under damped composite scores, and model provenance. Strictly labeled `prototype_only=True` and `official_warning_issued=False`.
- **Unified Prediction Pipeline (Prompt 8):** Operational via `POST /api/v1/predict` (and `/api/v1/predict/`). Primary frontend integration endpoint orchestrating all 4 real evidence streams (Weather/Model 1, NWP, Radar, Sentinel-2/Model 2), executing risk fusion and deterministic warning decision in-process with zero duplicate provider calls, and returning complete vector GeoJSON polygons, source statuses, latency breakdowns, and provenance.
- **Frontend Dashboard (HydroWatch Rebuild):** Complete from-scratch commercial-grade geospatial intelligence rebuild (`frontend/`) using Next.js 16.3.5 (App Router, Turbopack), React 19.2.8, CesiumJS 1.145.0 (Esri World Imagery, 3D World Terrain with water mask and realistic sun lighting, WGS84 GeoJSON inundation polygon clamping, camera flyTo/auto-fit, strict location state isolation), live RainViewer interactive Doppler radar composite modal, NWP 24h meteogram chart, multi-source risk attribution table, Tree SHAP feature attribution (XAI), and technical provenance audit panel. 15/15 automated unit tests passing (100% pass rate), Next.js production build verified (`next build` exit 0).
- **Backend Automated Tests:** 133/133 passing with 100% pass rate.
- **Frontend Automated Tests:** 15/15 passing with 100% pass rate.

---

## Model Information

### Model 1 — Heavy Rainfall Prediction
- **Type:** XGBoost Binary Classifier
- **Purpose:** Predict next-day heavy rainfall probability for target geographic regions.
- **Pipeline:** Leakage-safe historical meteorological feature pipeline using 37 input features (atmospheric variables: precipitation, temperature, dew point, humidity, surface pressure, wind speeds at 2m and 10m, downward shortwave radiation; 1d/2d/3d/7d/14d/30d lags; rolling sums, means, and maximums; 1-day temporal changes; cyclical month/day-of-year encodings; and geospatial coordinates).
- **Model Artifacts:**
  - `best_heavy_rain_xgboost_v2.json` (Primary XGBoost model file)
  - `best_heavy_rain_xgboost_v2.pkl` (Joblib serialized version)
- **Untouched Final Test Metrics:**
  - Accuracy: **92.27%**
  - Precision: **41.19%**
  - Recall: **61.13%**
  - F1-Score: **0.4921**
  - ROC-AUC: **0.9228**
  - PR-AUC: **0.5138**
- **Metric Integrity Note:** Never claim 95%+ accuracy for Model 1. Test metrics reflect genuine imbalanced weather evaluation.

### Model 2 — Inundation / Flood Segmentation
- **Type:** U-Net Architecture (`FloodUNet`, 7,763,905 parameters)
- **Input Modality:** Sentinel-2 multispectral imagery with 6 calibrated bands:
  - `B2` (Blue)
  - `B3` (Green)
  - `B4` (Red)
  - `B8` (Near-Infrared)
  - `B11` (Shortwave Infrared 1)
  - `B12` (Shortwave Infrared 2)
- **Purpose:** High-resolution pixel-level flood and water inundation segmentation.
- **Dataset Basis:** Sen1Floods11 v1.1 (512x512 chips, reflectance scale 10000.0, AdamW optimizer, BCE + Dice loss with water class weight 9.5201).
- **Model Artifacts:**
  - `best_model.pth` (PyTorch model checkpoint)
  - `best_model_metadata.json` (Architectural and training metadata)
  - `dataset_config.json` (Dataset split and raster index specifications)
  - `unet_model_config.json` (Loss weights and model configuration)
- **Validation vs. Test Metric Distinctions:**
  - **Best Validation Checkpoint:** Achieved at epoch 28 with Validation IoU = **83.16%** (`0.83161358`).
  - **Final Untouched Test Metrics:**
    - Pixel Accuracy: **97.79%**
    - Mean IoU: **83.84%**
    - Dice / F1: **91.21%**
    - Precision: **90.95%**
    - Recall: **91.47%**

---

## Architecture & Pipeline

```text
REAL DATA SOURCES
    |
    +-- Satellite precipitation (GPM / INSAT-3D/3DR) [NOT CONNECTED]
    |
    +-- Radar (Doppler Weather Radar) [NOT CONNECTED]
    |
    +-- Weather observations (IMD AWS / Surface stations) [NOT CONNECTED]
    |
    +-- Numerical Weather Prediction (NWP - GFS / NCUM / WRF) [NOT CONNECTED]
    |
    +-- Satellite imagery (Sentinel-2 multispectral) [NOT CONNECTED]
    |
    +-- Terrain / geospatial data (DEM / Slope / Land Use) [NOT CONNECTED]
    |
    v
DATA INGESTION (Adapters & Providers)
    |
    v
DATA NORMALIZATION / VALIDATION (Pydantic schemas)
    |
    v
FEATURE ENGINEERING / FUSION (Leakage-safe pipelines)
    |
    +----------------------+
    |                      |
    v                      v
MODEL 1                MODEL 2
Heavy rainfall        Inundation
prediction (XGBoost)   segmentation (U-Net)
    |                      |
    +----------+-----------+
               |
               v
        RISK FUSION ENGINE
               |
               v
       SPATIAL RISK RESULT
               |
        +------+------+
        |             |
        v             v
     WARNING       EXPLANATION
               |
               v
          FASTAPI REST
               |
               v
           FRONTEND
```

### Service Responsibilities
1. `WeatherObservationService`: Ingest and validate observational station/AWS data.
2. `NWPService`: Ingest numerical weather prediction grids and point forecasts.
3. `RadarService`: Process Doppler Weather Radar reflectivity and precipitation rate scans.
4. `SatellitePrecipitationService`: Ingest gridded satellite precipitation products.
5. `SatelliteImageryService`: Ingest and preprocess multispectral Sentinel-2 imagery (6 bands).
6. `TerrainService`: Provide digital elevation models, flow direction, and slope layers.
7. `Model1Service`: Load XGBoost rainfall model and execute inference on feature vectors.
8. `Model2Service`: Load U-Net flood segmentation model and generate water probability masks.
9. `RiskFusionService`: Fuse rainfall predictions, flood masks, and terrain vulnerability.
10. `WarningService`: Generate actionable IMD-standard early warnings and advisories.

---

## Data Sources & Connection Status

| Source Name | Modality | Intended Provider | Current Status |
|:---|:---|:---|:---|
| Surface Meteorological Data | Daily observations & reanalysis | NASA POWER Daily Point API | **CONNECTED** |
| Numerical Weather Prediction (NWP) | Global atmospheric forecasts (0.25°) | Open-Meteo NOAA GFS Seamless API | **CONNECTED** |
| Doppler Weather Radar | Live reflectivity composite (dBZ) | RainViewer Global DWR Composite | **CONNECTED** |
| Surface Weather Observations | In-situ real-time weather stations | IMD AWS Network | **NOT CONNECTED** |
| Satellite Precipitation | Gridded precipitation estimates | GPM IMERG / INSAT-3DR | **NOT CONNECTED** |
| Multispectral Satellite Imagery | Optical satellite bands | Copernicus Sentinel-2 | **NOT CONNECTED** |
| Terrain & Elevation | DEM raster data | Copernicus DEM / SRTM | **NOT CONNECTED** |

---

## Demonstration Region

- **Primary Demo Region:** Mumbai Metropolitan Region (MMR), Maharashtra, India.
- **Architectural Design:** Completely generic coordinates and bounding box system (`Location`, `GeoBoundingBox`). Mumbai is strictly a demo configuration, not hardcoded into logic.

---

## Engineering Rules

1. **Zero Fabrication:** Real data only for claimed live features. No fake weather numbers, random mock probabilities, or dummy masks.
2. **Explicit Connection State:** Any interface not yet wired to a live source must report `is_connected = False` and raise `NotImplementedError` if invoked.
3. **Leakage Prevention:** Temporal train/test splits and lag-based feature engineering must guarantee no future data leaks into predictions.
4. **Model Preservation:** Checkpoint weights and trained model parameters must remain unaltered unless explicit, documented retraining is requested.
5. **Configuration Decoupling:** All filesystem paths, environments, log levels, and endpoints are configured via environment variables, never hardcoded personal paths.
6. **No Secret Leaks:** Credentials, API tokens, and private paths must never be checked into version control or hardcoded.

---

## Backend Progress — Prompt 2 (Real ML Model Inference Services)

### 1. Model 1 (Heavy Rainfall Prediction)
- **Implementation Status:** Fully implemented and operational via `Model1Service`.
- **Model Checkpoint:** `best_heavy_rain_xgboost_v2.json` (Native JSON format loaded via `xgboost.Booster`).
- **Feature Ordering:** Exactly 37 features ordered per training pipeline:
  1. `PRECTOTCORR`, 2. `T2M`, 3. `T2MDEW`, 4. `RH2M`, 5. `PS`, 6. `WS2M`, 7. `WS10M`, 8. `ALLSKY_SFC_SW_DWN`,
  9. `rain_lag_1d`, 10. `rain_lag_2d`, 11. `rain_lag_3d`, 12. `rain_lag_7d`, 13. `rain_lag_14d`,
  14. `rain_sum_prev_3d`, 15. `rain_sum_prev_7d`, 16. `rain_sum_prev_14d`, 17. `rain_sum_prev_30d`,
  18. `rain_mean_prev_7d`, 19. `rain_max_prev_7d`,
  20. `T2M_lag_1d`, 21. `T2MDEW_lag_1d`, 22. `RH2M_lag_1d`, 23. `PS_lag_1d`, 24. `WS2M_lag_1d`, 25. `WS10M_lag_1d`, 26. `ALLSKY_SFC_SW_DWN_lag_1d`,
  27. `temperature_change_1d`, 28. `humidity_change_1d`, 29. `pressure_change_1d`, 30. `wind_change_1d`,
  31. `month`, 32. `month_sin`, 33. `month_cos`, 34. `doy_sin`, 35. `doy_cos`, 36. `latitude`, 37. `longitude`.
- **Decision Threshold:** Frozen validation-selected threshold `0.81`.
- **Loading Strategy:** Thread-safe lazy singleton preloaded during FastAPI application lifespan startup. Cached in-memory; zero reloads per request.

### 2. Model 2 (Flood Inundation Segmentation)
- **Implementation Status:** Fully implemented and operational via `Model2Service`.
- **Model Checkpoint:** `best_model.pth` (PyTorch U-Net checkpoint).
- **Architecture:** `FloodUNet` (7,763,905 parameters; double-conv blocks with `bias=False`, batch normalization, 2x2 maxpool downsampling, 2x2 transposed conv upsampling, 1x1 conv output layer).
- **Six-Band Ordering:** Strictly enforced: `[B2, B3, B4, B8, B11, B12]`.
- **Preprocessing Pipeline:**
  1. Cast to `float32`.
  2. Divide by `10000.0` (reflectance scale).
  3. Replace non-finite values (NaN / ±Inf) with `0.0`.
  4. Clip values to `[0.0, 1.0]`.
- **Inference Mode & Device:** `eval()` mode with `torch.no_grad()`. Device selection: CUDA when available, otherwise CPU (`MODEL2_DEVICE` setting).
- **Output Format:** Width/height dimensions, valid pixel count, water pixel count, flooded area percentage, sigmoid probability matrix, and thresholded binary inundation mask (threshold `0.5`).

### 3. API Endpoints Implemented
- `GET /api/v1/models/health`: Real-time report on model load state, configured paths, types, thresholds, and devices.
- `POST /api/v1/models/rainfall/predict`: Real Model 1 inference from JSON meteorological feature vectors.
- `POST /api/v1/models/inundation/predict`: Real Model 2 segmentation from JSON multi-channel array `[6, H, W]`.
- `POST /api/v1/models/inundation/predict-raster`: Real Model 2 segmentation from uploaded `.npy` or `.tif` raster files.

### 4. Application Startup & Error Handling
- FastAPI lifespan attempts non-fatal preloading of Model 1 and Model 2 on startup.
- If checkpoints are absent, startup logs clear warnings, health endpoints report `loaded: false`, and prediction endpoints return structured `503 Service Unavailable` with `MODEL_NOT_LOADED` code.
- Input validation failures return `422 Unprocessable Entity` with details on missing features or invalid dimensions.

### 5. Tests Added & Results
- Total test count: 34 tests (15 new tests added covering real XGBoost inference, FloodUNet checkpoint loading, preprocessing, determinism, parameter count, API validation, and health checks).
- Full suite passes in 0.20s: `python3 -m pytest backend/tests -v`.

### 6. Limitations & Boundaries
- External real data streams (live weather stations, Doppler radar, satellite precipitation, Sentinel-2 tile catalogs) remain unconnected.
- Inundation masks are returned as 2D arrays / pixel counts; geospatial GeoJSON vectorization and risk fusion are deferred to subsequent prompts.

### 7. Files Changed in Prompt 2
- Created: `backend/app/models/flood_unet.py`, `backend/app/api/v1/endpoints/models.py`, `backend/tests/test_model_inference.py`.
- Modified: `backend/app/core/config.py`, `backend/app/models/__init__.py`, `backend/app/schemas/prediction.py`, `backend/app/schemas/__init__.py`, `backend/app/services/model1_service.py`, `backend/app/services/model2_service.py`, `backend/app/api/v1/router.py`, `backend/app/api/v1/endpoints/health.py`, `backend/app/main.py`, `backend/tests/test_services.py`, `backend/tests/conftest.py`, `backend/README.md`, `context.md`.

---

## Backend Progress — Prompt 3 (Real NASA POWER Weather Ingestion & Model 1 Feature Pipeline)

### 1. Real Weather Data Ingestion (NASA POWER API)
- **Data Source:** NASA POWER Daily Point API (`https://power.larc.nasa.gov/api/temporal/daily/point`).
- **Core Atmospheric Variables Fetched (8 parameters):**
  1. `PRECTOTCORR`: Precipitation corrected (mm/day)
  2. `T2M`: Air temperature at 2m (°C)
  3. `T2MDEW`: Dew point temperature at 2m (°C)
  4. `RH2M`: Relative humidity at 2m (%)
  5. `PS`: Surface atmospheric pressure (kPa)
  6. `WS2M`: Wind speed at 2m (m/s)
  7. `WS10M`: Wind speed at 10m (m/s)
  8. `ALLSKY_SFC_SW_DWN`: All sky surface downward solar irradiance (MJ/m²/day)
- **Client Features:**
  - Implemented via `NasaPowerClient` with asynchronous HTTP (`httpx.AsyncClient`).
  - Exponential backoff retry handling (3 attempts) on transient network/5xx failures.
  - Strict validation: rejects `-999.0` sentinel missing values, non-finite values (`NaN`, `±Inf`), missing dates, and unparseable types.
  - Coordinate proximity verification ensuring response maps to requested coordinates within 1.0 degree tolerance.

### 2. Exact 37-Feature Engineering (`Model1FeatureBuilder`)
- **Temporal Relationship & Leakage Prevention:**
  - Model 1 predicts next-day heavy rainfall for calendar date $D$.
  - Latest observation date used is strictly $D_{obs} = D - 1$.
  - Zero future data leakage: Any record with $\text{date} \ge D$ is strictly filtered out.
  - Minimum lookback requirement: Requires $\ge 30$ continuous daily records ending at $D - 1$ ($D-30$ to $D-1$). Discontinuities or gaps raise `WeatherObservationValidationError`.
- **Exact 37 Features in Training Order:**
  1–8. Base variables at $D-1$: `PRECTOTCORR`, `T2M`, `T2MDEW`, `RH2M`, `PS`, `WS2M`, `WS10M`, `ALLSKY_SFC_SW_DWN`
  9–13. Precipitation lags: `rain_lag_1d` ($D-2$), `rain_lag_2d` ($D-3$), `rain_lag_3d` ($D-4$), `rain_lag_7d` ($D-8$), `rain_lag_14d` ($D-15$)
  14–17. Rolling precipitation sums ending on $D-1$: `rain_sum_prev_3d` (3 days), `rain_sum_prev_7d` (7 days), `rain_sum_prev_14d` (14 days), `rain_sum_prev_30d` (30 days)
  18–19. Rolling precipitation statistics ending on $D-1$: `rain_mean_prev_7d`, `rain_max_prev_7d`
  20–26. Atmospheric 1-day lags at $D-2$: `T2M_lag_1d`, `T2MDEW_lag_1d`, `RH2M_lag_1d`, `PS_lag_1d`, `WS2M_lag_1d`, `WS10M_lag_1d`, `ALLSKY_SFC_SW_DWN_lag_1d`
  27–30. 1-day temporal differences: `temperature_change_1d` ($T2M_{D-1} - T2M_{D-2}$), `humidity_change_1d`, `pressure_change_1d`, `wind_change_1d`
  31–35. Calendar cyclical encodings for $D-1$: `month`, `month_sin`, `month_cos`, `doy_sin`, `doy_cos`
  36–37. Geospatial coordinates: `latitude`, `longitude`

### 3. API Endpoints Implemented
- `POST /api/v1/predict/rainfall`:
  - Request: `latitude`, `longitude`, `prediction_date` (YYYY-MM-DD), optional `location_name`.
  - Process: Fetches NASA POWER history, constructs 37 features, runs real Model 1 XGBoost inference.
  - Response: `prediction_date`, `observation_date` ($D-1$), `heavy_rain_predicted` (bool), `heavy_rain_probability` (float), `threshold` (0.81), `model_version`, `historical_records_used`, `latest_weather` summary.

### 4. Verified Live Pipeline Results
- **Mumbai Peak Monsoon Test (`2024-07-15`):**
  - Observation Date Used ($D-1$): `2024-07-14` (`PRECTOTCORR = 53.06 mm`, `RH2M = 93.61%`)
  - Inference Result: `heavy_rain_predicted = True`, `probability = 0.9689` (threshold `0.81`).
- **Mumbai Dry Season Test (`2024-01-15`):**
  - Observation Date Used ($D-1$): `2024-01-14` (`PRECTOTCORR = 0.0 mm`, `RH2M = 51.18%`)
  - Inference Result: `heavy_rain_predicted = False`, `probability = 0.0014`.

### 5. Automated Tests Added
- Total test count: 48 automated tests (14 new tests added in Prompt 3).
- 100% pass rate in 0.76s: `python3 -m pytest backend/tests -v`.

### 6. Limitations & Deferred Scope
- Radar volume scans, NWP gridded forecasts, Sentinel-2 tile catalogs, and inundation risk fusion remain deferred to future prompts.
- NASA POWER data availability has an operational delay of 1 to 2 days; predictions for today/future without released NASA POWER history raise structured 422 errors rather than fabricating synthetic observations.

---

## Backend Progress — Prompt 4 (Real NWP + Radar Data Ingestion)

### 1. Real NWP Forecast Integration (Open-Meteo NOAA GFS)
- **Data Source:** Open-Meteo GFS API (`https://api.open-meteo.com/v1/forecast` with `models=gfs_seamless`).
- **Underlying Model:** NOAA Global Forecast System (GFS) 0.25° grid (~25 km resolution).
- **Licensing:** Open Database License (ODbL) / CC-BY 4.0; open public machine-readable JSON.
- **Horizon & Frequency:** Hourly forecasts for 1 to 16 days, updated 4 times daily (00, 06, 12, 18 UTC cycles).
- **Variables Ingested & Normalized:**
  1. `precipitation`: Hourly rainfall rate in mm/hr
  2. `temperature_2m`: Air temperature in °C
  3. `relative_humidity_2m`: Relative humidity in %
  4. `dew_point_2m`: Dew point temperature in °C
  5. `surface_pressure`: Converted to kPa (`hPa / 10.0`)
  6. `wind_speed_10m`: Wind speed at 10m in m/s
  7. `cape`: Convective Available Potential Energy in J/kg
- **Implementation:** `OpenMeteoNwpClient` & `NWPService` with in-memory TTL caching (10 min).
- **API Endpoint:** `GET /api/v1/data/nwp` (query: `latitude`, `longitude`, `forecast_days`).

### 2. Real Doppler Weather Radar Integration (RainViewer Global DWR Composite)
- **Data Source:** RainViewer Radar Network (`https://api.rainviewer.com/public/weather-maps.json`).
- **Product:** Doppler Weather Radar Maximum Reflectivity Composite (DWR MAX-Z, dBZ scale).
- **Licensing:** Free open public radar API.
- **Resolution & Frequency:** 10-minute scan intervals; Web Mercator Slippy tiles ($z=0$ to $z=14$, ~2.4 km/px at $z=6$).
- **Processing Pipeline:**
  1. Converts coordinates $(lat, lon)$ to Web Mercator tile $(z, x, y)$ and derives exact geographic `GeoBoundingBox`.
  2. Downloads real-time 256x256 RGBA PNG raster tile from RainViewer tilecache CDN.
  3. Decodes array using PIL: alpha channel defines active precipitation echo mask (clear air = alpha 0).
  4. Computes peak reflectivity (dBZ), mean echo reflectivity, active echo pixel count, and echo spatial coverage percentage.
  5. Derives estimated peak rainfall rate (mm/hr) using standard Marshall-Palmer radar relation: $Z = 200 \times R^{1.6} \implies R = (10^{\text{dBZ}/10} / 200)^{0.625}$.
- **Implementation:** `RainViewerRadarClient` & `RadarService` with in-memory TTL caching (5 min).
- **API Endpoint:** `GET /api/v1/data/radar` (query: `latitude`, `longitude`, `zoom`).

### 3. Verified Live Integration Results (Mumbai `19.0760, 72.8777`)
- **NWP Live Query:**
  - Status: HTTP 200
  - Forecast Count: 48 hours
  - Peak Rainfall Rate: 0.9 mm/hr, Max CAPE: 1210.0 J/kg, Surface Pressure: 101.0 kPa
- **Radar Live Query:**
  - Status: HTTP 200
  - Latest Frame: `2026-09-16T13:20:00Z`
  - Tile: `z=6, x=44, y=28`, Bounding Box: `[16.63619°N, 21.94305°N, 67.5°E, 73.125°E]`
  - Active Echo Pixels: 220 / 65,536 (0.336% coverage)
  - Max Reflectivity: 48.8 dBZ
  - Estimated Max Rain Rate: 40.91 mm/hr

### 4. Automated Tests Added
- Total test count: 64 automated tests (16 new tests added in Prompt 4).
- 100% pass rate in ~4.3s: `python3 -m pytest backend/tests -v`.

### 5. Scope Boundaries Maintained
- Risk fusion, warning decision rules, GeoJSON polygon vectorization, and frontend remain deferred to later prompts.
- Dedicated on-premise IMD hardware antenna direct connections remain unconnected; public composite APIs provide real live data.

---

## Backend Progress — Prompt 5 (Real Sentinel-2 → Model 2 Geospatial Inundation Pipeline)

### 1. Real Sentinel-2 STAC Catalog Client & Asset Discovery
- **Provider & Endpoint:** Element 84 Earth Search STAC API (`https://earth-search.aws.element84.com/v1/search`) indexing AWS Open Data Sentinel-2 Level-2A Cloud-Optimized GeoTIFFs.
- **Collection:** `sentinel-2-l2a` (Bottom-Of-Atmosphere surface reflectance).
- **Licensing:** Open Access Government Data / Copernicus Open Access / CC-BY 4.0.
- **Bands Required & Mappings:**
  - `B2`: Blue (10 m, asset key `blue` / `B02.tif`)
  - `B3`: Green (10 m, asset key `green` / `B03.tif`)
  - `B4`: Red (10 m, asset key `red` / `B04.tif`)
  - `B8`: Near-Infrared (10 m, asset key `nir` / `B08.tif`)
  - `B11`: SWIR-1 (20 m, asset key `swir16` / `B11.tif`)
  - `B12`: SWIR-2 (20 m, asset key `swir22` / `B12.tif`)
- **Deterministic Scene Selection:**
  - Evaluates geographic point containment in scene bounding box.
  - Rejects any candidate missing any of the 6 required bands.
  - Filters scenes exceeding `max_cloud_percentage` (default 25.0%).
  - Sorts candidate scenes deterministically by `(abs(days_delta), cloud_coverage)`.
  - Returns structured `selection_reason` string.

### 2. Adaptive COG Range Reader & 10m Common Grid Alignment
- **Band Tile Streaming:** Implemented `fetch_cog_band_aligned` using HTTP Range requests against S3 COGs (`bytes=...`), downloading only the 64KB header and the specific ~1.2MB tile covering target coordinates rather than entire 180MB/band files.
- **Adaptive Dimension Handling:** Dynamically inspects `ModelPixelScaleTag` and `TileWidth`/`TileLength` per band:
  - 10m bands (1024x1024 tiles, 10,240m extent): 1-to-1 tile index mapping.
  - 20m bands with 512x512 tiles (10,240m extent, e.g. B12): 1-to-1 tile index mapping, bilinear resampled 2x to 1024x1024.
  - 20m bands with 1024x1024 tiles (20,480m extent, e.g. B11): 2x2 quadrant indexing, slices 512x512 subwindow and bilinear resamples 2x to 1024x1024.
- **Common Model Grid:** Stacks aligned bands in exact order `[B2, B3, B4, B8, B11, B12]` into `(6, 1024, 1024)` float32 array.

### 3. Window Tiling & Model 2 Inference
- **Tiling:** Divides `(6, 1024, 1024)` grid into 512x512 sliding windows with 64px overlap (stride 448) and boundary clamping.
- **Preprocessing:** Preserves exact Sen1Floods11 training preprocessing: float32, division by 10000.0, non-finite values replaced with 0.0, clipped to `[0.0, 1.0]`.
- **Inference:** Evaluates real `FloodUNet` PyTorch checkpoint (`best_model.pth`, 7,763,905 parameters) without model reloading.
- **Mosaic Reconstruction:** Blends overlapping probabilities using 2D sinusoidal pyramid weighting, normalizes accumulator, and thresholds at 0.5 to produce final binary mask.

### 4. Geospatial Polygonization & Area Calculation
- **Contour Vectorization:** Uses OpenCV `cv2.findContours(..., cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)` to extract exterior polygons and interior hole rings.
- **Noise Filtering:** Discards polygons smaller than `min_polygon_area_sq_m` (default 500 m² / 5 pixels).
- **Geodesic Projection:** Maps pixel coordinates to UTM Easting/Northing, then projects to WGS84 (`EPSG:4326`) longitude/latitude using Snyder/Karney ellipsoid equations (<0.1 mm precision).
- **Area Computation:** Computes geodesic area via $100\,\text{m}^2/\text{pixel}$ grid geometry ($10^{-4}\,\text{km}^2$), returning `valid_area_sq_km`, `flooded_area_sq_km`, `flooded_percentage`, and `polygon_count`.

### 5. API Endpoint Implemented
- `POST /api/v1/predict/inundation`:
  - Request: `latitude`, `longitude`, optional `date` (YYYY-MM-DD), `max_cloud_percentage`, `min_polygon_area_sq_m`, `location_name`.
  - Response: `requested_location`, `selected_scene`, `model_version`, `threshold` (0.5), `grid_resolution_m` (10.0), `raster_dimensions` [1024, 1024], `valid_area_sq_km`, `flooded_area_sq_km`, `flooded_percentage`, `polygon_count`, and GeoJSON `FeatureCollection`.

### 6. Verified Live Pipeline Results
- **Mumbai Coastal Test (`18.97, 72.82` — `2024-02-01`):**
  - Scene ID: `S2B_43QBB_20240201_0_L2A` (Acquisition: `2024-02-01T05:53:37Z`)
  - Cloud Cover: `6.02%`, CRS: `EPSG:32643` (UTM 43N)
  - Dimensions: `[1024, 1024]`, Resolution: `10.0 m`
  - Valid Area: `104.858 km²`
  - Flooded Area: `87.165 km²` (`83.13%` — correctly detects Arabian Sea & coastal waters)
  - Polygon Count: `86`
  - Sample Polygon: 7 points, vertex `[72.809843, 18.958834]`
- **Pune Inland Test (`18.52, 73.85` — `2024-02-01`):**
  - Scene ID: `S2A_43QCA_20240203_0_L2A` (Acquisition: `2024-02-03T05:49:51Z`)
  - Cloud Cover: `0.00%`, CRS: `EPSG:32643`
  - Valid Area: `104.858 km²`
  - Flooded Area: `0.305 km²` (`0.29%` — dry inland ground correctly classified with tiny reservoir polygons)
  - Polygon Count: `39`

### 7. Automated Tests Added
- Total test count: 86 automated tests (22 new tests added in Prompt 5 across `test_sentinel_catalog.py`, `test_raster_tiling.py`, `test_polygonization.py`, `test_inundation_pipeline.py`).
- 100% pass rate in ~8.3s: `python3 -m pytest backend/tests -v`.

---

## Changelog

### 2026-09-16 — Prompt 8: Unified End-to-End Prediction API
- Created dedicated unified request/response schemas in `backend/app/schemas/unified.py`: `UnifiedPredictionRequest`, `SourceStatusDetail`, `UnifiedRainfallSummary`, `UnifiedNwpSummary`, `UnifiedRadarSummary`, `UnifiedInundationSummary`, `UnifiedRiskSummary`, `UnifiedTimingDetail`, `UnifiedPredictionResponse`.
- Re-exported all new unified schemas in `backend/app/schemas/__init__.py`.
- Implemented `UnifiedPredictionService` (`backend/app/services/unified_prediction_service.py`):
  - Stage A: Concurrently coordinates real evidence ingestion across NASA POWER (`weather_service.predict_rainfall`), NOAA GFS (`nwp_service.fetch_point_forecast`), RainViewer radar (`radar_service.fetch_radar_composite`), and Sentinel-2 / Model 2 UNet (`satellite_service.predict_inundation`) via `asyncio.gather(..., return_exceptions=True)`.
  - Captures high-resolution per-source latency measurements with `time.perf_counter()`.
  - Isolates provider failures cleanly into `source_status` without leaking raw stack traces.
  - Stage B: Passes normalized evidence into `RiskFusionService.fuse_evidence` respecting existing missing-source policy ($\ge 2$ sources required, $< 2$ sources raises 422 `InsufficientHistoricalDataError`).
  - Stage C: Passes composite risk response into `WarningService.evaluate_warning` to compute physical triggers, deterministic operational state, and temporal validity windows.
  - Stage D: Assembles frontend-ready payload with rich metrics, vector GeoJSON polygons, composite risk, warning triggers, timing breakdown, and complete audit provenance.
  - In-process execution: never makes internal HTTP requests, avoids duplicate serialization overhead, reuses singleton model services (`Model1Service.get_instance()`, `Model2Service.get_instance()`).
- Exposed `POST /api/v1/predict` (and trailing slash alias `POST /api/v1/predict/`) in `backend/app/api/v1/endpoints/prediction.py`.
- Preserved 100% backward compatibility with all prior endpoints (`/rainfall`, `/inundation`, `/risk`, `/warning`, `/models/*`, `/data/*`).
- Added 10 automated unit and integration tests in `backend/tests/test_unified_prediction.py` covering full evidence success, trailing slash alias, partial radar missing, partial satellite missing, partial weather missing, insufficient evidence (422), coordinate/date validation, determinism & idempotency, zero duplicate provider calls, and model singleton reuse.
- Total test suite expanded to **132/132 tests passing** (100% pass rate in ~8.3s).
- Conducted live real end-to-end verification against Mumbai (`19.0760, 72.8777`):
  - All 4 real feeds active simultaneously (`weather_model1`: 877ms, prob 0.9689; `nwp`: 745ms, rain 1.6mm; `radar`: 1338ms, 50.1 dBZ; `satellite_model2`: 8171ms, 3.202 km² flooded, 196 vector polygons).
  - Risk score: 0.5341 (MODERATE), Warning Status: MONITOR, governed by radar nowcast validity.

### 2026-09-16 — Prompt 7: Explainable Warning Decision Layer
- Extended configuration with centralized trigger thresholds (`TRIGGER_RAINFALL_PROBABILITY=0.81`, `TRIGGER_RAINFALL_OBSERVED_MM=64.5`, `TRIGGER_NWP_HOURLY_PRECIP_MM_HR=20.0`, `TRIGGER_NWP_ACCUMULATED_PRECIP_MM=70.0`, `TRIGGER_RADAR_MAX_DBZ=45.0`, `TRIGGER_RADAR_RAIN_RATE_MM_HR=30.0`, `TRIGGER_INUNDATION_FLOODED_PCT=10.0`, `TRIGGER_INUNDATION_AREA_SQ_KM=5.0`) and validity windows (`WARNING_VALIDITY_RADAR_HOURS=3.0`, `WARNING_VALIDITY_NWP_HOURS=12.0`).
- Created warning schemas in `backend/app/schemas/warning.py`: `WarningStatus` (`NO_ALERT`, `MONITOR`, `PREPARE`, `ACTION`, `INSUFFICIENT_DATA`), `WarningUrgency`, `PhysicalTrigger`, `EvidenceFreshness`, `WarningProvenance`, `WarningDecision`, `WarningAssessmentRequest`, `WarningDecisionResponse`.
- Implemented `WarningService.evaluate_warning` mapping composite risk level to operational state and evaluating concrete physical triggers with observed vs threshold values.
- Built temporal validity evaluator: 3h forward validity for active radar nowcasts, 12h for NWP cycles, and `valid_until = null` for historical satellite scenes.
- Built discrepancy disclosure: detects if real-time physical bursts (e.g. radar $\ge 50$ dBZ or NWP $\ge 35$ mm/hr) occur while composite score is low/moderate due to weights, and records an explicit `escalation_notes` warning without tampering with composite scores.
- Exposed `POST /api/v1/predict/warning` consuming existing `RiskAssessmentService` without redundant external queries.
- Strictly maintained `prototype_only=True` and `official_warning_issued=False` with explicit non-official IMD disclaimer.
- Added 21 automated tests across `test_warning_decision.py` and `test_warning_pipeline.py`. All 122 backend tests passing (100%).
- Verified live end-to-end on real Mumbai data (`19.0760, 72.8777`) and controlled severe multi-source threat scenario (`0.9125` EXTREME $\to$ ACTION, 8/8 triggers fired).

### 2026-09-16 — Prompt 6: Real Multi-Source Flood-Risk Engine & Explainability Pipeline
- Configured dynamic risk fusion weights (`RISK_WEIGHT_RAINFALL=0.35`, `RISK_WEIGHT_NWP=0.25`, `RISK_WEIGHT_RADAR=0.20`, `RISK_WEIGHT_INUNDATION=0.20`, sum = 1.0) and prototype thresholds (`0.30, 0.60, 0.80`) with Pydantic model validator enforcement.
- Created normalized evidence schemas (`RainfallEvidence`, `NwpEvidence`, `RadarEvidence`, `SatelliteInundationEvidence`), `SourceExplanation`, `PrototypeWarningCandidate`, `FusionMetadata`, `RiskAssessmentRequest`, and `RiskAssessmentResponse`.
- Implemented `RiskFusionService` with physical normalization functions (Model 1 probability, NWP rain rate/accum/CAPE, radar dBZ/rain rate, satellite inundation with `<48h` (1.0), `48-168h` (0.75), `>168h` (0.50) temporal discounting).
- Implemented missing-source policy: full evidence across 4 sources, dynamic weight renormalization across 3 or 2 sources, strict HTTP 422 (`INSUFFICIENT_HISTORICAL_DATA`) rejection for <2 sources. Zero fake data tolerated.
- Built mathematical explainability decomposition where each stream's contribution equals `effective_weight * normalized_score`, and sum of contributions strictly equals the composite risk score.
- Added prototype warning candidate derivation with urgency levels (`NONE`, `MONITOR`, `PREPARE`, `ACTION`), physical triggers, and explicit non-official IMD disclaimer.
- Built `RiskAssessmentService` orchestrator concurrently querying NASA POWER, Open-Meteo GFS, RainViewer radar, and Sentinel-2 STAC/COG with graceful partial failure handling.
- Exposed `POST /api/v1/predict/risk` pipeline endpoint.
- Verified live end-to-end on Mumbai (`19.0760, 72.8777`): all 4 live streams succeeded, composite risk `0.1773` (LOW), Radar `0.1642` contribution, Sentinel-2 `0.0098`, NWP `0.0027`, Model 1 `0.0006`, exact sum match.
- Added 15 new automated tests across `test_risk_fusion.py` and `test_risk_pipeline.py`. All 101 backend tests passing (100%).

### 2026-09-16 — Prompt 5: Real Sentinel-2 → Model 2 Geospatial Inundation Pipeline
- Implemented `Sentinel2CatalogClient` querying Element 84 Earth Search STAC API for Sentinel-2 Level-2A surface reflectance scenes with deterministic ranking and 6-band verification (`B2, B3, B4, B8, B11, B12`).
- Implemented `SentinelRasterProcessor` with adaptive COG HTTP Range requests, 20m to 10m bilinear resampling, 512x512 sliding window tiling with overlap blending, and probability mosaic reconstruction.
- Implemented OpenCV contour vectorization (`cv2.findContours`), hole ring nesting, minimum polygon area filtering, and WGS84 geodesic transformation.
- Connected `SatelliteImageryService` and exposed `POST /api/v1/predict/inundation`.
- Verified live end-to-end on real Sentinel-2 Level-2A imagery for Mumbai (83.13% water) and Pune (0.29% water).
- Added 22 new automated tests, bringing total test count to 86 tests (100% passing).

### 2026-09-16 — Prompt 4: Real NWP + Radar Data Ingestion
- Implemented `OpenMeteoNwpClient` and wired `NWPService` to ingest real NOAA GFS 0.25° numerical weather forecasts with hourly atmospheric parameters (precipitation, temperature, pressure, wind, CAPE).
- Implemented `RainViewerRadarClient` and wired `RadarService` to ingest live Doppler Weather Radar composite scans, decode raster tiles via PIL, and calculate dBZ reflectivity and Marshall-Palmer rainfall rates.
- Created `DataCache` in-memory TTL caching abstraction.
- Added API endpoints: `GET /api/v1/data/nwp` and `GET /api/v1/data/radar`.
- Verified live end-to-end against real NOAA GFS and RainViewer DWR composite feeds.
- Expanded test suite to 64 automated tests with 100% pass rate.

### 2026-09-16 — Prompt 3: Real NASA POWER Weather Ingestion + Model 1 Feature Pipeline
- Added NASA POWER API client (`NasaPowerClient`) with async HTTPX, retry backoff, and strict validation.
- Implemented `DailyWeatherRecord` schema and `Model1FeatureBuilder` for exact 37-feature calculation with zero future leakage.
- Wired real `POST /api/v1/predict/rainfall` pipeline endpoint connecting live meteorological ingestion directly to Model 1 XGBoost.
- Verified live end-to-end inference against NASA POWER API for Mumbai monsoon (0.9689 prob) and dry season (0.0014 prob).
- Added 14 new automated tests; all 48 tests pass.

### 2026-09-16 — Real ML Model Inference Services (Prompt 2)
- Implemented real inference for Model 1 (`best_heavy_rain_xgboost_v2.json`, 37 features, frozen threshold 0.81).
- Recreated exact PyTorch `FloodUNet` architecture (7,763,905 params) and implemented real Model 2 inference (`best_model.pth`, 6-band Sentinel-2 order `[B2, B3, B4, B8, B11, B12]`, threshold 0.5).
- Added `POST /api/v1/models/rainfall/predict`, `POST /api/v1/models/inundation/predict`, `POST /api/v1/models/inundation/predict-raster`, and `GET /api/v1/models/health`.
- Integrated thread-safe model caching and startup preloading into FastAPI lifecycle.
- Resolved macOS OpenMP duplicate runtime linkage via `install_name_tool`.
- Expanded automated test suite to 34 tests with 100% pass rate.

### 2026-09-17 — Frontend Rebuild — HydroWatch Complete Geospatial Intelligence Interface
- **Complete Rebuild from Scratch**: Rebuilt the deleted `frontend/` directory as a commercial-grade, production-quality geospatial intelligence product adhering strictly to all 78 master criteria.
- **Technology Stack**:
  - Next.js 16.3.5 (App Router, Turbopack static compilation)
  - React 19.2.8 & React DOM 19.2.8
  - CesiumJS 1.145.0 (Client-side dynamic import, SSR disabled, static assets in `/cesium`)
  - Tailwind CSS v4 + Vanilla CSS design system tokens (`#08090c`, `#10141e`, `#161b26`)
  - Vitest 3.2.7 + React Testing Library 16.3.3 + jsdom 30.0.1
  - Lucide React icon library
- **3D Geospatial Engine (CesiumJS)**:
  - Base Imagery: High-resolution real-world satellite imagery via open Esri World Imagery XYZ tile service (`https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}`).
  - 3D Terrain: Cesium World Terrain with water mask, vertex normals, and realistic sun lighting, with clean non-technical fallback to WGS84 ellipsoid.
  - GeoJSON Inundation Clamping: Model 2 FloodUNet vector polygons rendered with translucent cyan fill (`rgba(0, 180, 216, 0.42)`) and `#00E5FF` outline, clamped to terrain.
  - Camera Controller: Immediate `flyTo` on location selection with 3D perspective tilt (~38° pitch, altitude 18,000m). Automatic bounding box framing when inundation polygons exist.
  - Interactive Popover: Renders only authentic backend properties (`flooded_area_sq_m`, `perimeter_m`, `scene_id`, `source`).
  - Active 4-Layer Legend: Selected Point, Predicted Inundation, 3D Terrain, Esri Satellite Imagery.
- **Strict Location State Isolation**:
  - Synchronously clears all previous GeoJSON polygons, inundation values, risk score, warning state, and satellite scene metadata on preset or custom coordinate change to ensure zero cross-location contamination (verified in tests and live).
- **Real Multi-Source Telemetry Streams**:
  - Single unified endpoint: `POST /api/v1/predict`
  - Heavy Rainfall (Model 1): Linear probability scale with 0.81 operational decision threshold line, binary prediction flag, and D-1 precipitation (mm).
  - Doppler Radar: Real RainViewer composite telemetry (max dBZ, mean dBZ, rain rate mm/h via Marshall-Palmer $Z = 200 \times R^{1.6}$, echo coverage %, timestamp) and dedicated interactive modal centered on target coordinates with dBZ severity color scale (`<20`, `20-35`, `35-50`, `>50 dBZ`).
  - NWP 24h Forecast: Interactive SVG meteogram bar chart with hover tooltips, peak intensity callout, and accumulated precipitation (mm).
  - Inundation Segmentation (Model 2): Flooded area (km²), flooded %, polygon count, strictly separated from Sentinel-2 optical acquisition baseline.
- **Explainability & Warning Decision**:
  - Why This Assessment: Multi-source risk attribution table displaying source, observed value, normalized score, effective weight, contribution %, and timestamp. Proportional visual waterfall.
  - Model Feature Attribution (Tree SHAP): Top positive and negative meteorological drivers, log-odds margins, narrative synthesis, and mandatory scientific non-causality attribution disclaimer.
  - Early Warning Instrument: Evaluates physical trigger limits, validity window, urgency, and displays mandatory notice: `PROTOTYPE ASSESSMENT · NOT AN OFFICIAL IMD WARNING`.
- **Quality & Verification**:
  - 15/15 unit tests passing (`npm test -- --run`).
  - Next.js production build passing with 0 errors (`npm run build`).
  - Zero synthetic fallbacks, zero fake radar scopes, zero fake charts, zero emojis, zero student/hackathon references.


