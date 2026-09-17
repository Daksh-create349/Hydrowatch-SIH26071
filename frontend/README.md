# HydroWatch Frontend — Complete Geospatial Intelligence Interface

HydroWatch is a commercial-grade, multi-source flood risk assessment and early warning platform synthesizing observational weather, NOAA GFS NWP, RainViewer Doppler radar, and Sentinel-2 multispectral flood inundation analytics.

---

## 1. Technical Stack

| Layer | Technology | Operational Notes |
| :--- | :--- | :--- |
| **Framework** | **Next.js 16.3.5** (App Router, Turbopack) | Fast Refresh and static production builds with zero TypeScript errors. |
| **UI Library** | **React 19.2.8** | Client-side reactive interface with zero cross-location data contamination. |
| **Geospatial Engine** | **CesiumJS 1.145.0** | Loaded client-side via dynamic import with SSR disabled. |
| **Satellite Base Imagery** | **Esri World Imagery** (`ArcGIS World_Imagery`) | Global real-world satellite imagery up to zoom 19 with legal provider attribution preserved. |
| **3D Elevation & Water** | **Cesium 3D World Terrain** | Real 3D terrain mesh with water mask, vertex normals, and realistic sun lighting. Seamless ellipsoid fallback. |
| **Doppler Radar** | **RainViewer Global Composite** | Live composite centered on coordinates, timeline playback, and dBZ severity scale. |
| **Styling** | **Tailwind CSS v4 + Vanilla CSS Tokens** | Curated dark scientific palette (`#08090c`, `#10141e`, `#161b26`). |
| **Testing Suite** | **Vitest 3.2.7 + React Testing Library** | 15 unit tests covering dashboard lifecycle, location isolation, XAI suite, radar telemetry, and warning rules. |
| **API Client** | Native `fetch` with typed TypeScript contracts | Environment-driven `POST /api/v1/predict` unified pipeline orchestrator. |

---

## 2. Directory Structure

```text
frontend/
├── public/
│   └── cesium/                     # CesiumJS static assets (Workers, Assets, Widgets, ThirdParty)
├── src/
│   ├── app/
│   │   ├── globals.css             # Scientific dark design tokens & Cesium UI overrides
│   │   ├── layout.tsx              # Root HTML layout with viewport and metadata definitions
│   │   └── page.tsx                # Master dashboard coordinator (zero cross-location contamination)
│   ├── components/
│   │   ├── app-shell/
│   │   │   └── Header.tsx          # Branding, operational stream health, coordinates indicator
│   │   ├── location/
│   │   │   └── AnalysisCommand.tsx # Preset dropdown (Mumbai, Pune, Chennai, Guwahati) & custom coordinates
│   │   ├── map/
│   │   │   ├── CesiumGlobe.tsx     # 3D Cesium viewer, terrain mesh, Esri imagery, GeoJSON clamping, 4-layer legend
│   │   │   └── MapHud.tsx          # Floating HUD with composite risk index, warning pill, and inundation telemetry
│   │   ├── warning/
│   │   │   └── WarningPanel.tsx    # Authoritative early warning instrument (PROTOTYPE ASSESSMENT / NOT OFFICIAL IMD)
│   │   ├── common/
│   │   │   ├── EvidenceStrip.tsx   # 4-column physical matrix (Rainfall, Radar, NWP 24h meteogram, Inundation)
│   │   │   └── ErrorState.tsx      # Resilient error display with diagnostic toggle and retry action
│   │   ├── radar/
│   │   │   └── RadarModal.tsx      # Interactive RainViewer composite map modal with playback and dBZ scale
│   │   ├── explainability/
│   │   │   └── WhyAssessment.tsx   # Multi-source risk attribution table, Tree SHAP waterfall, causality chain
│   │   ├── source-status/
│   │   │   └── FreshnessTimeline.tsx # Real timestamps, latency, and status badges (LIVE, FORECAST, HISTORICAL)
│   │   ├── provenance/
│   │   │   └── AuditPanel.tsx      # Technical expandable drawer with model versions and raw JSON inspection
│   │   └── loading/
│   │       └── AnalysisProgress.tsx # Stepwise 7-stage pipeline execution monitor
│   ├── lib/
│   │   ├── api.ts                  # Typed fetch wrapper for POST /api/v1/predict and GET /health
│   │   ├── constants.ts            # Centralized preset locations, IMD radar network stations, color scales
│   │   ├── formatters.ts           # Coordinate, metric, and date/time formatters
│   │   └── types.ts                # TypeScript data contracts mirroring backend FastAPI schemas
│   └── tests/
│       ├── setup.ts                # Vitest DOM matchers setup
│       ├── fixtures/mockData.ts    # Isolated test fixtures
│       ├── dashboard.test.tsx      # 7 unit tests (initial render, preset switches, custom coords, state isolation)
│       ├── xai.test.tsx            # 3 unit tests (multi-source attribution, SHAP drivers, disclaimer)
│       ├── radar.test.tsx          # 2 unit tests (radar telemetry, clear troposphere handling)
│       └── warning.test.tsx        # 3 unit tests (warning states, physical triggers, disclaimer)
├── next.config.ts                  # Next.js Turbopack config with fallback externals
├── vitest.config.ts                # Vitest configuration with JSDOM and React plugin
├── tsconfig.json                   # Strict TypeScript configuration
├── package.json                    # Dependencies and scripts
└── .env.example                    # NEXT_PUBLIC_API_BASE_URL and NEXT_PUBLIC_CESIUM_ION_TOKEN
```

---

## 3. Environment Variables

Create `.env.local` in `frontend/`:

```bash
NEXT_PUBLIC_API_BASE_URL=http://127.0.0.1:8001
NEXT_PUBLIC_CESIUM_ION_TOKEN=
```

---

## 4. Development & Testing Commands

```bash
# Install dependencies
npm install

# Run automated tests (15 unit tests)
npm test -- --run

# Run production build (Turbopack + TypeScript)
npm run build

# Run local development server (port 3000)
npm run dev
```

---

## 5. Key Operational Behaviors

1. **State Isolation**: When selecting a new preset or custom coordinate, all previous GeoJSON polygons, risk scores, and telemetry metrics immediately clear from state before the new API response arrives.
2. **Camera Management**: Selection of a preset immediately commands the Cesium camera to fly to the target coordinates with a 3D perspective tilt (~38° pitch, altitude 18,000m). When inundation polygons are returned, the camera auto-fits to their spatial bounding box with clean padding.
3. **Strict Authenticity**: Zero synthetic bell curves, zero decorative circular SVG radar scopes, zero fake depth metrics, zero glowing neon effects, and zero mention of hackathons, students, or competitions.
