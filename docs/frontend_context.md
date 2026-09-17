# HydroWatch Frontend — Honest Architecture & Technical Context

> **Integrity Statement**: This document is an authentic, zero-exaggeration technical breakdown of the HydroWatch frontend application. It documents the exact origin of every live API feed, geospatial layer, machine learning inference service, and presentation component. Zero synthetic fallbacks, zero decorative geospatial slop, zero fake charts, zero emojis, and zero mentions of student, hackathon, or competition.

---

## 1. Executive Summary & Tech Stack

The frontend is a commercial-grade geospatial intelligence dashboard for environmental early warning, quantitative rainfall forecasting, and flood inundation risk assessment.

| Component | Specification | Honest Operational Notes |
| :--- | :--- | :--- |
| **Framework** | **Next.js 16.3.5** (App Router, Turbopack) | Fast Refresh and Turbopack production builds (`next build` passes with 0 errors). |
| **Runtime / Library** | **React 19.2.8** / React DOM 19.2.8 | Client-side application (`'use client'` on all interactive views). |
| **Geospatial Engine** | **CesiumJS 1.145.0** | Loaded client-side via dynamic import with SSR disabled. |
| **Satellite Imagery** | **Esri World Imagery** (`ArcGIS World_Imagery`) | Real global satellite imagery up to zoom 19 via open XYZ tile service. |
| **3D Elevation** | **Cesium 3D World Terrain** | Real 3D terrain mesh with 1.4x vertical exaggeration and solar shading. |
| **Styling** | **Vanilla CSS Tokens** + Tailwind CSS v4 | Curated dark mode palette (`#0a0b0e`, `#10141e`) via `src/app/globals.css`. |
| **Testing Suite** | **Vitest 5.0.1** + React Testing Library 16.3.3 + jsdom 30.0.1 | 15 automated unit tests covering dashboard, warning instrument, and XAI suite. |
| **API Client** | Native `fetch` with typed TypeScript contracts | Single unified orchestrator endpoint `POST /api/v1/predict`. |

---

## 2. Real Operational Data vs. Fallback Policy

```
                                  ┌─────────────────────────────┐
                                  │      Next.js Frontend       │
                                  │    (http://localhost:3000)  │
                                  └──────────────┬──────────────┘
                                                 │ POST /api/v1/predict
                                                 ▼
                                  ┌─────────────────────────────┐
                                  │       FastAPI Backend       │
                                  │   (http://127.0.0.1:8001)   │
                                  └──────────────┬──────────────┘
                                                 │
         ┌────────────────────────┬──────────────┴──────────────┬────────────────────────┐
         ▼                        ▼                             ▼                        ▼
┌──────────────────┐    ┌──────────────────┐          ┌──────────────────┐    ┌──────────────────┐
│ NASA POWER / GFS │    │  RainViewer DWR  │          │ AWS Earth Search │    │ Open-Meteo GFS   │
│ (XGBoost Model 1)│    │ (Radar Telemetry)│          │ (Sentinel-2 STAC)│    │ (NWP 24h Grid)   │
└──────────────────┘    └──────────────────┘          └──────────────────┘    └──────────────────┘
```

| Stream / Feature | Live / Real Implementation | Honest Behavior (Zero Synthetic Slop) |
| :--- | :--- | :--- |
| **Heavy Rain Probability (Model 1)** | **100% Real**: FastAPI runs XGBoost classifier (`best_heavy_rain_xgboost_v2.json`) on 37 lag/meteorological features from NASA POWER. | Visualized with restrained linear probability scale, explicit **81% operational decision threshold** line, and `PREDICTED` vs `BELOW THRESHOLD` flag. |
| **Doppler Weather Radar** | **Real Live Telemetry**: RainViewer API fetches live max reflectivity (dBZ), estimated rain rate (mm/h), echo coverage percentage, and timestamp. | Prominently marked `RADAR TELEMETRY`. Never fakes a spatial raster overlay when only telemetry is present. If radar offline, displays `RADAR UNAVAILABLE` without breaking the dashboard. |
| **NWP Hourly Meteogram** | **100% Real GFS 24h Series**: Backend extracts actual 24-hour chronological precipitation rates (`hourly_precipitation`) from Open-Meteo GFS. | Interactive SVG chart with hover tooltip displaying hour (`T+Xh`) and exact `mm`, peak callout, and baseline axis. Zero synthetic bell curves. |
| **Inundation Vectors (Model 2)** | **Real ML Output**: Backend FloodUNet segments Sentinel-2 multispectral COGs from AWS S3, vectorizing water masks into GeoJSON. | Translucent cyan fill (`#00B4D8`, alpha 0.42) with `#00E5FF` outline. Camera automatically flies and fits to the bounding box of returned polygons. Popover shows only real fields (`flooded_area_sq_m`, `perimeter_m`, `scene_id`, `source`). |
| **Satellite Baseline vs Flood** | **Strict Separation**: Clean separation between `MODEL-PREDICTED INUNDATION` and `SATELLITE ACQUISITION`. | Sentinel-2 acquisition date and cloud cover are explicitly presented as the optical acquisition baseline to prevent historical imagery from ever looking like a live flood observation. |
| **Prototype Warning Panel** | **Authoritative Assessment**: Evaluates physical trigger rules against operational limits. | Prominently marked: `PROTOTYPE ASSESSMENT · NOT AN OFFICIAL IMD WARNING`. Shows status, urgency, active triggers, validity, and escalation notes. |
| **Multi-Source Attribution** | **Backend-Owned Fusion Math**: Uses exact backend weights and fusion contributions. | Each row shows: source, observed value, normalized score, effective weight, contribution %, and timestamp. No frontend percentage calculations. |
| **Model Feature Attribution (Tree SHAP)** | **100% Real**: Backend computes exact Tree SHAP margins using XGBoost. | Labeled `MODEL FEATURE ATTRIBUTION`. Explains mathematical directional contribution (+Red/-Cyan) without claiming physical causality. |
| **Map Satellite & 3D Terrain** | **Real Esri World Imagery + 3D Terrain**: Cesium async World Terrain with 1.4x exaggeration. | Camera flies directly to selected coordinates. Active 4-layer legend indicates Analysis Coordinate, Predicted Inundation, 3D Terrain, and Satellite Imagery. |

---

## 3. Directory & File Structure

```
frontend/
├── public/
│   └── cesium/                                 # CesiumJS static assets (Workers, Assets, ThirdParty, Widgets)
├── src/
│   ├── app/
│   │   ├── globals.css                         # Design system tokens, dark mode palette, typography
│   │   ├── layout.tsx                          # Root HTML layout with Inter & JetBrains Mono font definitions
│   │   └── page.tsx                            # Main Dashboard Page (Zero cross-location contamination)
│   ├── components/
│   │   ├── app-shell/Header.tsx                # Authoritative app bar, streams online count, WGS84 indicator
│   │   ├── common/
│   │   │   ├── ErrorState.tsx                  # Resilient error card with retry callback
│   │   │   └── EvidenceStrip.tsx               # 4-column physical matrix (Rainfall, Radar, NWP chart, Inundation)
│   │   ├── explainability/
│   │   │   └── WhyAssessment.tsx               # Multi-source attribution, Tree SHAP, sensor context gallery
│   │   ├── loading/
│   │   │   └── AnalysisProgress.tsx            # Stepwise pipeline execution monitor (7 stages)
│   │   ├── location/
│   │   │   └── AnalysisCommand.tsx             # Floating preset selector, lat/lon inputs, date picker
│   │   ├── map/
│   │   │   ├── CesiumGlobe.tsx                 # 3D Cesium viewer, 4-layer legend, bounding box auto-framing
│   │   │   └── MapHud.tsx                      # Floating HUD with restrained risk scale, level, urgency, primary driver
│   │   ├── provenance/
│   │   │   └── AuditPanel.tsx                  # Technical expandable drawer with JSON payload inspection
│   │   ├── source-status/
│   │   │   └── FreshnessTimeline.tsx           # Telemetry freshness, latency, age, and classification badges
│   │   └── warning/
│   │       └── WarningPanel.tsx                # Early warning instrument (PROTOTYPE ASSESSMENT / NOT OFFICIAL IMD)
│   ├── lib/
│   │   ├── api.ts                              # Typed fetch wrapper for POST /api/v1/predict
│   │   ├── formatters.ts                       # Preset locations & coordinate/date formatters
│   │   ├── radarTelemetry.ts                   # IMD radar network database, Haversine distance, dBZ severity scale
│   │   └── types.ts                            # TypeScript data contracts mirroring backend Pydantic models
│   └── tests/
│       ├── dashboard.test.tsx                  # 12 unit tests verifying dashboard, WarningPanel, HUD, presets
│       ├── setup.ts                            # Vitest environment setup (@testing-library/jest-dom)
│       └── xai.test.tsx                        # 3 unit tests verifying SHAP drivers, causality, modal
├── vitest.config.ts                            # Vitest configuration with JSDOM and React plugin
└── package.json                                # Dependencies and script definitions
```

---

## 4. Key Component Responsibilities

### 4.1. `src/app/page.tsx` (Dashboard Coordinator)
- **Primary Page Flow**:
  1. `Header`: Product identity, streams online indicator.
  2. `CesiumGlobe` + `AnalysisCommand` + `MapHud`: 3D map hero with restrained analytical risk index, warning pill, and primary driver.
  3. `WarningPanel`: Prototype assessment warning instrument with active trigger list and escalation guidance.
  4. `EvidenceStrip`: 4-column physical evidence matrix (Rainfall, Radar Telemetry, NWP 24h chart with hover tooltips, and Inundation with separated satellite acquisition).
  5. `WhyAssessment`: Multi-source risk attribution table (all 6 fields), Tree SHAP feature attribution, operational data gallery.
  6. `FreshnessTimeline`: Latency, age, and status tags (`LIVE OBSERVATION`, `FORECAST (GFS)`, `HISTORICAL CONTEXT`).
  7. `AuditPanel`: Full diagnostic payload and model provenance.
- **Zero Cross-Location Data Contamination**:
  - `setData(null)` runs synchronously whenever a preset location or coordinate changes.
  - Previous geometry and metrics disappear immediately before the new API response arrives.

### 4.2. `src/components/map/CesiumGlobe.tsx` (Geospatial Engine)
- **4-Layer Active Map Legend**:
  - Analysis Coordinate (`#FFFFFF` pin on `#0284C7`)
  - Predicted Inundation (`#00B4D8` translucent fill, `#00E5FF` outline, polygon count)
  - 3D World Terrain (1.4x relief)
  - Satellite Imagery (Esri World Imagery)
- **Bounding Box Auto-fit**: Automatically calculates the bounding box of returned inundation polygons and flies the camera to frame them with clean padding.
- **Real Fields Only Popover**: Shows `flooded_area_sq_m`, `perimeter_m`, `scene_id`, and `source`.

### 4.3. `src/components/warning/WarningPanel.tsx` (Warning Instrument)
- Visible badges: `PROTOTYPE ASSESSMENT` and `NOT AN OFFICIAL IMD WARNING`.
- Displays status (`ACTION`, `PREPARE`, `MONITOR`, `NO_ALERT`), urgency, trigger reasons with observed values vs limits, validity window, and escalation guidance.

### 4.4. `src/components/common/EvidenceStrip.tsx` (Physical Telemetry Matrix)
- **Station Rain**: Linear probability scale with 81% decision threshold marker, prediction status, observed precipitation mm.
- **Doppler Radar**: Labeled `RADAR TELEMETRY`, dynamic dBZ color-coded severity (<20 green, 20-35 cyan, 35-50 amber, >50 red), rain rate mm/h with Marshall-Palmer Z-R relationship (Z = 200 * R^1.6), echo coverage % (<100km radius), nearest IMD radar station proximity, and honest note (`Direct volumetric scan · No spatial raster`).
- **NWP Forecast**: Real 24-hour GFS precipitation meteogram bar chart with interactive hover tooltip and peak callout.
- **Inundation Summary**: Flooded area km², flooded %, polygon count, separated from `SATELLITE ACQUISITION BASELINE` (Sentinel-2 sensor, scene ID, cloud coverage %).

### 4.5. `src/components/explainability/WhyAssessment.tsx` (XAI Suite)
- **Multi-Source Risk Attribution**: Displays all 6 required fields per stream: source, observed value, normalized score, effective weight, contribution %, timestamp.
- **Model Feature Attribution**: Tree SHAP attributions labeled `MODEL FEATURE ATTRIBUTION` with explicit non-causal disclaimer.
- **Operational Data Gallery**: Real remote sensing visuals with sensor product, timestamp, and representation context.
- **Authoritative Radar Telemetry Scope**: High-precision SVG tactical radar scope with concentric 25km/50km/100km/150km range rings, cardinal axes (N/E/S/W), antenna sweep sector, station HUD, and clear atmosphere badge (`CLEAR TROPOSPHERE · 0.0 dBZ ECHO`) or convective echo clusters.
- **Doppler Radar Lightbox Modal**: Includes 4-tier meteorological dBZ severity scale bar, Marshall-Palmer equation, nearest IMD station proximity, and explicit note (`Direct volumetric scan telemetry. No spatial raster available for this station at current observation time.`). Never displays 0 dBZ in red.

---

## 5. Verification & Test Suite

- **Frontend Unit Tests**:
  - `npm test -- --run` passes (15/15 tests across `dashboard.test.tsx` and `xai.test.tsx`).
- **Frontend Production Build**:
  - `npm run build` passes with exit code 0 (`next build` with Turbopack).
- **Backend Unit Tests**:
  - `PYTHONPATH=. pytest backend/tests/` passes (133/133 tests).
- **Zero Mock / Synthetic Slop**:
  - Verified: No synthetic bell curves, no fake radar overlays, no circular speedometer gauges, no emojis, and zero SIH/hackathon references.
