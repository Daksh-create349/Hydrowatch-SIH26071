# HYDROWATCH FRONTEND — COMPLETE REBUILD FROM SCRATCH
# PREMIUM REAL PRODUCT + FULL GEOSPATIAL EXPERIENCE

THIS IS A FULL FRONTEND REBUILD.

The previous `frontend/` directory was deleted.

Do NOT attempt to patch non-existent files.

Create the entire frontend again from scratch.

The backend already exists and must NOT be modified unless a clearly verified frontend-blocking contract mismatch is discovered.

============================================================
1. FIRST: UNDERSTAND THE EXISTING BACKEND
============================================================

Before writing frontend code, inspect:

- `context.md`
- complete backend directory
- FastAPI routes
- Pydantic schemas
- OpenAPI schema
- `POST /api/v1/predict`
- all existing model/data/risk/warning response structures

The frontend MUST use the actual backend contracts.

Do NOT assume field names from this prompt if the backend defines them differently.

The backend is the source of truth.

Do NOT create frontend fake response objects to compensate for misunderstanding the backend.

============================================================
2. PRODUCT IDENTITY
============================================================

This is a real product.

Do NOT mention anywhere in user-facing UI:

- SIH
- Smart India Hackathon
- hackathon
- college
- student
- competition
- problem statement

The product should feel like a real commercial climate and geospatial intelligence platform.

Think:

- environmental intelligence
- flood intelligence
- atmospheric monitoring
- geospatial analysis
- operational decision support

NOT:

- student project
- admin dashboard
- generic SaaS template
- AI landing page

============================================================
3. CORE DESIGN DIRECTION
============================================================

Create a premium, restrained, highly intentional interface.

Design goals:

- sophisticated
- scientific
- editorial
- geospatial
- calm
- precise
- information-dense without being cluttered
- visually memorable
- production-quality

Avoid AI slop completely.

DO NOT use:

- purple AI gradients
- neon cyberpunk
- glowing neural-network graphics
- random blobs
- excessive glassmorphism
- excessive rounded cards
- fake charts
- decorative radar graphics
- giant circular gauges
- meaningless metric cards
- excessive badges
- emoji UI
- chatbot-style "AI explanation"
- fake live indicators
- stock disaster images

The actual map and actual data should be the visual content.

============================================================
4. TECHNOLOGY
============================================================

Use:

- Next.js 16+
- React 19+
- TypeScript
- CesiumJS
- Vanilla CSS/design tokens or existing project approach
- Lucide React for icons
- Vitest + React Testing Library

DO NOT use:

- MapLibre
- Mapbox
- Google Maps
- another mapping engine

CesiumJS is the PRIMARY geospatial engine.

Use Cesium client-side only.

SSR must be disabled for the Cesium viewer.

============================================================
5. MAP FOUNDATION
============================================================

The map is the heart of the entire application.

Use:

### Real satellite base imagery

Use real Esri World Imagery / ArcGIS World Imagery or another legitimate free-development-compatible imagery source.

The imagery must correspond to the selected geographic area.

Do NOT use static unrelated satellite screenshots.

### Real terrain

Use Cesium 3D World Terrain when available.

Use environment variable:

`NEXT_PUBLIC_CESIUM_ION_TOKEN`

Never hardcode tokens.

If terrain cannot load, show a clean terrain-unavailable state.

Do NOT silently replace a failed real terrain layer with fake terrain.

The map must still remain geographically usable.

============================================================
6. LOCATION-FIRST EXPERIENCE
============================================================

This is mandatory.

When user selects:

- Mumbai
- Pune
- Chennai
- Guwahati
- custom coordinates

the map MUST immediately:

1. update location state
2. move camera to exact coordinates
3. zoom to useful regional scale
4. tilt to useful 3D terrain perspective
5. show the location marker
6. show actual geographic surroundings

NEVER leave the camera at world view.

NEVER show an arbitrary location.

NEVER keep the previous location's map state.

============================================================
7. LOCATION DATA ISOLATION
============================================================

When location changes:

immediately clear:

- old risk
- old warning
- old inundation polygons
- old satellite metadata
- old analysis metrics
- old source timestamps

Old Mumbai data MUST NEVER remain while Pune is selected.

Before a new analysis completes, show a clean "analysis not run" state for the new location.

Then replace it with the new real backend result.

============================================================
8. CAMERA BEHAVIOR
============================================================

Implement:

### Initial location

Fly to selected coordinates.

### Analysis complete with polygons

Calculate bounds of REAL returned GeoJSON and frame them.

### Analysis complete with zero polygons

Remain focused on selected coordinate.

### Location changed

Fly to new location.

### User manually pans/zooms

Do NOT fight the user by repeatedly recentering.

### Reset

Return to selected location.

Use smooth camera transitions.

No dramatic cinematic camera animation.

============================================================
9. 3D TERRAIN
============================================================

Terrain must feel useful, not decorative.

Use:

- real 3D terrain
- sensible camera tilt
- realistic depth
- subtle lighting
- appropriate geographic scale

Do NOT use excessive vertical exaggeration that distorts geography.

If vertical exaggeration is used, keep it subtle and configurable.

For:

- Mumbai → coastline and urban geography
- Pune → surrounding terrain
- Chennai → coast/basin context
- Guwahati → river/terrain context

the map should visibly reflect the actual geography.

============================================================
10. INUNDATION — THIS MUST BE VISUALLY OBVIOUS
============================================================

The backend returns REAL Model 2 inundation GeoJSON.

Render that exact GeoJSON on Cesium.

Requirements:

- correct WGS84 coordinates
- correct geographic positioning
- terrain-aware rendering
- translucent fill
- clean outline
- strong contrast against imagery
- clickable polygons
- hover/click interaction where technically practical

When polygons are present:

the user must immediately understand:

"THIS is the predicted inundated area."

Do NOT merely display:

`3.2 km²`

without showing where it is.

============================================================
11. POLYGON POPUP
============================================================

Clicking a polygon should show ONLY actual backend properties.

Possible fields:

- flooded area
- perimeter
- scene ID
- source
- acquisition time
- model version

Only render fields actually present.

Do NOT invent:

- flood depth
- water height
- severity
- confidence
- velocity
- probability

unless the backend actually provides them.

============================================================
12. MAP LEGEND
============================================================

Create a clean map legend showing ONLY active real layers:

- Analysis location
- Predicted inundation
- Satellite imagery
- 3D terrain

If a layer is unavailable, do not pretend it is active.

============================================================
13. MAP HUD
============================================================

Create a compact floating map HUD.

It should show actual selected-location context:

- location name
- coordinates
- risk score
- risk level
- warning state
- inundated area when available
- polygon count when available
- satellite acquisition timestamp when available

Do NOT turn this into a giant dashboard.

============================================================
14. MAP DECORATION RULE
============================================================

Do NOT recreate old decorative:

- radar circles
- artificial rings
- vertical beams
- fake scan sweeps
- decorative SVG radar scopes

Every geospatial visual object must correspond to a real geographic/data concept.

============================================================
15. LIVE RADAR
============================================================

This is an important part of the product.

The radar visualization must use REAL RainViewer radar data.

Do NOT create a fake SVG radar.

Preferred implementation:

Create a dedicated Radar Intelligence panel/modal using the real RainViewer radar map centered dynamically on the selected location.

The radar view should support, where the provider allows:

- live radar
- timeline
- play/pause
- previous/next scan
- zoom
- pan

The radar must automatically center around:

`latitude`
`longitude`

of the selected location.

Do NOT leave the radar focused on some unrelated geography.

============================================================
16. RADAR TERMINOLOGY MUST BE ACCURATE
============================================================

Do NOT call RainViewer data:

- direct IMD radar hardware feed
- direct S-band IMD volume scan
- direct IMD volumetric interrogation

unless the backend actually supplies that exact feed.

Correct terminology:

- `RainViewer Radar Composite`
- `Live Doppler Radar Composite`
- `Radar Telemetry`

You may display nearest IMD radar station information ONLY as supporting metadata if the backend actually returns it.

Do not imply RainViewer is the same thing as direct IMD hardware.

============================================================
17. RADAR TELEMETRY
============================================================

Display actual radar telemetry from backend:

- timestamp
- max reflectivity
- estimated rainfall rate
- echo coverage
- source

Use real values only.

Severity colors may use:

- <20 dBZ → green
- 20–35 → blue
- 35–50 → amber
- >50 → red

BUT do not treat those colors as official IMD warning levels.

============================================================
18. RADAR CLEAR-SKY STATE
============================================================

If real radar has no active echoes:

DO NOT show a fake image.

Instead show:

`NO ACTIVE RADAR ECHOES`

plus:

- actual dBZ
- timestamp
- coverage

This is a valid real radar state.

============================================================
19. RADAR ATTRIBUTION
============================================================

Do not remove, obscure, or misleadingly hide provider attribution if the provider requires it.

The product should remain polished while preserving proper source attribution.

============================================================
20. RAINFALL MODEL SECTION
============================================================

Show REAL Model 1 information.

Display:

- heavy rainfall probability
- predicted / below threshold
- operational threshold = 0.81
- observation date
- latest observed precipitation
- available relevant meteorological fields

Use a refined linear probability indicator.

Do NOT use a speedometer.

Do NOT invent confidence.

============================================================
21. NWP FORECAST
============================================================

Use REAL GFS/Open-Meteo hourly data.

Create a polished meteorological forecast visualization.

Show actual:

- hours
- precipitation
- peak forecast
- forecast timing
- units

Use hover tooltips.

Each bar/point must correspond to an actual backend forecast value.

No:

- Gaussian curves
- synthetic smoothing
- fake trend lines
- interpolated values

============================================================
22. NWP DESIGN
============================================================

Make it feel like professional meteorological software.

Use:

- clean timeline
- actual time labels
- subtle grid
- peak callout
- forecast indicator

Do NOT overcrowd the chart.

============================================================
23. INUNDATION SUMMARY
============================================================

Display:

- flooded area
- flooded percentage
- polygon count
- Sentinel-2 scene ID
- acquisition time
- cloud coverage
- source

Clearly label:

`MODEL-PREDICTED INUNDATION`

and separately:

`SENTINEL-2 ACQUISITION`

Never present the satellite acquisition itself as a live flood observation.

============================================================
24. SENTINEL-2 IMAGERY
============================================================

The system uses Sentinel-2 imagery in the Model 2 pipeline.

When the backend exposes:

- scene thumbnail
- asset preview
- image URL
- scene information

render the actual selected scene.

The displayed image MUST correspond to the current analysis scene.

If no real scene image is available in the backend response:

do NOT substitute a random static satellite image.

Show scene metadata instead.

============================================================
25. WEATHER / RADAR / NWP / SATELLITE RELATIONSHIP
============================================================

Make the product explain the four evidence families:

### Weather / Rainfall Model
"what atmospheric conditions suggest"

### NWP
"what the forecast suggests"

### Radar
"what current radar observes"

### Sentinel-2 / Model 2
"what satellite imagery contains and what the segmentation model predicts"

Do NOT mix these concepts together.

============================================================
26. RISK
============================================================

Use the BACKEND risk score.

Do NOT calculate another score on the frontend.

Show:

- risk score
- risk level
- evidence availability
- dominant contribution

The score must exactly match backend output.

============================================================
27. WARNING
============================================================

Use the BACKEND warning result.

Show:

- NO_ALERT
- MONITOR
- PREPARE
- ACTION
- INSUFFICIENT_DATA

Also:

- triggered/not triggered
- trigger reasons
- validity
- escalation notes
- evidence freshness

Keep:

`PROTOTYPE ASSESSMENT · NOT AN OFFICIAL IMD WARNING`

clearly visible.

Do not make the warning look like a government-issued alert.

============================================================
28. EXPLAINABILITY
============================================================

Rebuild the complete explainability experience.

Create a polished:

`WHY THIS ASSESSMENT`

section.

Use the REAL backend contributions.

For every evidence stream display:

- source
- observed value
- normalized value
- effective weight
- contribution
- timestamp

Create a ranked contribution visualization.

Do not recompute backend math.

============================================================
29. SHAP
============================================================

If the backend returns real Tree SHAP attribution:

render it.

Show:

- top features
- positive/negative impact
- actual SHAP values or margins
- understandable feature descriptions

Label clearly:

`MODEL FEATURE ATTRIBUTION`

Include:

`SHAP describes the mathematical contribution of model features; it is not a physical causality proof.`

CRITICAL:

If backend does NOT return XAI/SHAP for a request:

DO NOT fabricate a baseline.

Show:

`MODEL FEATURE ATTRIBUTION UNAVAILABLE`

and explain that no attribution was returned.

============================================================
30. PHYSICAL EVIDENCE
============================================================

Create a visual evidence waterfall:

- rainfall model
- radar
- NWP
- inundation

Sort using ACTUAL backend contribution.

Do not invent percentages.

============================================================
31. CAUSALITY SECTION
============================================================

The UI may describe the meteorological process conceptually:

Moisture
→ Atmospheric setup
→ Rainfall
→ Surface response

BUT clearly distinguish this from mathematical model attribution.

Do not claim SHAP itself proves physical causality.

============================================================
32. OPERATIONAL DATA SECTION
============================================================

Create a refined real-data inspection area.

Possible sections:

### Sentinel-2
Actual scene metadata/image if supplied.

### Radar
Real RainViewer radar view.

### NWP
Real forecast visualization.

### Flood prediction
Actual Model 2 GeoJSON-derived result.

Never display unrelated stock imagery.

============================================================
33. SOURCE FRESHNESS
============================================================

Create a premium source timeline/status section.

Sources:

- NASA POWER
- Open-Meteo / NOAA GFS
- RainViewer
- Sentinel-2

For every source show:

- available/unavailable
- timestamp
- age where available
- CURRENT / RECENT / FORECAST / HISTORICAL
- latency where available

Do NOT invent timestamps.

============================================================
34. HISTORICAL SATELLITE MUST LOOK HISTORICAL
============================================================

This is critical.

If Sentinel-2 imagery is old:

display:

`HISTORICAL SATELLITE CONTEXT`

not:

`LIVE FLOODING`

Do not visually imply real-time observation.

============================================================
35. LOADING EXPERIENCE
============================================================

The unified endpoint can take several seconds.

Create a beautiful analysis progress interface.

Show stages such as:

- Weather observation
- Rainfall model
- NWP forecast
- Radar
- Satellite analysis
- Risk synthesis
- Warning assessment

Only mark stages complete when the frontend/backend state supports it.

Do NOT fake percentage completion.

============================================================
36. ERROR STATES
============================================================

No raw technical error messages.

Examples:

`Geospatial view unavailable`

`Radar data unavailable`

`Satellite analysis unavailable`

`Insufficient evidence`

`Analysis service unavailable`

Show remaining available evidence.

Never insert fake values when something fails.

============================================================
37. LOCATION COMMAND BAR
============================================================

Create a premium location control.

Default location:

Mumbai

Preset locations:

- Mumbai
- Pune
- Chennai
- Guwahati

Also support:

- custom latitude
- custom longitude
- location name
- analysis date/time where supported

Keep the advanced configuration collapsed by default.

Do not overwhelm the first screen with inputs.

============================================================
38. INITIAL SCREEN
============================================================

The initial screen should already feel complete before analysis.

Show:

- real Mumbai geography
- Cesium terrain
- real satellite imagery
- clean location marker
- elegant analysis controls
- empty-analysis state

Do NOT show fake risk numbers before analysis.

Do NOT show fake polygons.

============================================================
39. MAIN LAYOUT
============================================================

Use this hierarchy:

HEADER
↓
LOCATION / ANALYSIS COMMAND
↓
LARGE 3D GEOSPATIAL MAP
↓
RISK + WARNING
↓
EVIDENCE STRIP
↓
DETAILED WEATHER / RADAR / NWP / INUNDATION
↓
WHY THIS ASSESSMENT
↓
SOURCE FRESHNESS
↓
PROVENANCE / AUDIT

The map should dominate the first viewport.

============================================================
40. EVIDENCE STRIP
============================================================

Create four concise modules:

### RAIN
Probability / prediction

### RADAR
dBZ / rainfall rate

### NWP
forecast precipitation

### INUNDATION
flooded area / percentage

Each module:

- one main value
- useful secondary value
- source
- timestamp

Do not make 20 KPI cards.

============================================================
41. PROVENANCE
============================================================

Create an expandable technical audit panel.

Show:

### Models
- Model 1 checkpoint/version
- Model 2 checkpoint/version

### Data
- NASA POWER
- NOAA GFS / Open-Meteo
- RainViewer
- Sentinel-2

### Processing
- thresholds
- risk weights
- warning rules

### Timing
- provider latency
- total analysis duration

Never expose:

- secrets
- tokens
- local filesystem paths
- internal exception traces

============================================================
42. NO MOCK DATA
============================================================

The running application MUST contain zero:

- fake rainfall
- fake radar
- fake NWP
- fake inundation
- fake risk
- fake warnings
- fake satellite images
- fake SHAP

Test fixtures are allowed ONLY inside tests.

Never use fixture values in the normal application.

============================================================
43. NO CROSS-LOCATION CONTAMINATION
============================================================

If:

Mumbai analysis completes

then user selects Pune:

Immediately remove:

- Mumbai polygons
- Mumbai metrics
- Mumbai risk
- Mumbai warning
- Mumbai satellite metadata

Pune must start clean.

Then run the real API.

Never mix results.

============================================================
44. PERFORMANCE
============================================================

Cesium is expensive.

Implement:

- one Cesium viewer
- client-only initialization
- cleanup on unmount
- no duplicate imagery layers
- no duplicate terrain providers
- efficient GeoJSON handling
- minimal React rerenders
- memoized static config
- efficient chart rendering

Do not render thousands of DOM elements for map geometry.

Use Cesium primitives/entities appropriately.

============================================================
45. RESPONSIVE
============================================================

Desktop should be exceptional.

Mobile/tablet must remain usable.

On mobile:

- map remains large enough
- risk remains visible
- location controls collapse elegantly
- evidence modules stack/swipe
- charts remain readable
- polygon map remains usable

============================================================
46. ACCESSIBILITY
============================================================

Implement:

- keyboard navigation
- semantic buttons
- labels
- focus states
- proper contrast
- reduced motion support
- accessible chart descriptions
- accessible warning state

Do not rely only on color.

============================================================
47. VISUAL LANGUAGE
============================================================

Use:

- warm neutral / dark scientific palette
- charcoal
- deep green
- muted blue
- restrained warning colors
- clean typography
- subtle borders
- disciplined spacing

Do not use:

- neon
- purple AI gradients
- giant shadows
- excessive pills
- excessive rounded corners
- gradient-heavy backgrounds

============================================================
48. ICONS
============================================================

Use one consistent icon system such as Lucide.

No emoji icons.

No mixed icon libraries.

============================================================
49. FILE STRUCTURE
============================================================

Create a clean structure such as:

frontend/

  src/
    app/
      globals.css
      layout.tsx
      page.tsx

    components/
      app-shell/
        Header.tsx

      location/
        AnalysisCommand.tsx

      map/
        CesiumGlobe.tsx
        MapHud.tsx
        MapLegend.tsx

      risk/
        RiskOverview.tsx

      warning/
        WarningPanel.tsx

      weather/
        RainfallPanel.tsx
        NwpForecast.tsx

      radar/
        RadarPanel.tsx
        RadarTelemetry.tsx

      inundation/
        InundationPanel.tsx
        PolygonDetails.tsx

      explainability/
        WhyAssessment.tsx
        AttributionChart.tsx
        ShapPanel.tsx
        CausalityPanel.tsx

      source-status/
        FreshnessTimeline.tsx

      provenance/
        AuditPanel.tsx

      loading/
        AnalysisProgress.tsx

      common/
        ErrorState.tsx
        EmptyState.tsx

    lib/
      api.ts
      types.ts
      formatters.ts
      cesium.ts

    tests/
      dashboard.test.tsx
      map.test.tsx
      radar.test.tsx
      xai.test.tsx

  public/
    cesium/

Do NOT create static fake weather/radar/satellite assets as application fallbacks.

============================================================
50. ENVIRONMENT
============================================================

Create:

`.env.example`

with:

`NEXT_PUBLIC_API_BASE_URL=`

`NEXT_PUBLIC_CESIUM_ION_TOKEN=`

Do not hardcode environment-specific backend addresses.

============================================================
51. API CLIENT
============================================================

Use a typed API client.

Primary analysis:

`POST /api/v1/predict`

Do NOT have the dashboard reconstruct the analysis using multiple HTTP calls to the backend.

Use the unified response.

============================================================
52. RADAR API
============================================================

For radar visualization:

If using the real RainViewer map:

center it dynamically using the current coordinates.

If using backend radar telemetry:

use those values.

If rendering an actual radar raster layer:

ensure the geographic positioning is correct.

Do NOT stretch radar data arbitrarily over the map.

============================================================
53. FRONTEND DOES NOT REIMPLEMENT BACKEND LOGIC
============================================================

Do NOT recompute:

- risk score
- risk contributions
- warning level
- Model 1 probability
- Model 2 segmentation
- SHAP
- source normalization

Frontend = presentation.

Backend = scientific computation.

============================================================
54. TEST LOCATIONS
============================================================

Use real analysis verification for:

### Mumbai
19.0760, 72.8777

### Pune
18.5204, 73.8567

### Chennai
13.0827, 80.2707

### Guwahati
26.1445, 91.7362

Verify:

Select
→ correct camera
→ correct geographic context
→ run analysis
→ correct returned data
→ correct polygons
→ correct metrics
→ correct warning/risk

============================================================
55. IMPORTANT MAP TEST
============================================================

For every location:

The map must show the ACTUAL selected region.

Example:

Mumbai:
- Mumbai coastline/urban area

Pune:
- Pune surroundings

Chennai:
- Chennai coastline

Guwahati:
- Guwahati / Brahmaputra regional geography

The map must NOT remain at world scale.

============================================================
56. REAL FLOOD TEST
============================================================

When backend returns polygons:

The map must visibly show them.

If the backend returns:

Mumbai → 3.202 km² / 196 polygons

the frontend must render the real corresponding polygons at their actual coordinates.

Do NOT convert this into a generic circle.

============================================================
57. BUILD AND TEST
============================================================

Run:

`npm install`

Then:

`npm test -- --run`

Then:

`npm run build`

Also run:

`npm run lint`

and TypeScript checks if available.

Everything must pass.

============================================================
58. REAL BROWSER QA
============================================================

This is mandatory.

Open the actual frontend in a browser.

Start backend and frontend.

Perform real analysis.

Verify visually:

- map
- satellite imagery
- terrain
- location camera
- inundation polygons
- radar
- rainfall
- NWP
- risk
- warning
- XAI
- freshness
- provenance

Check browser console.

There must be no:

- Cesium runtime errors
- provider configuration error visible to user
- broken imagery
- blank map
- incorrect location
- cross-location pollution

============================================================
59. VISUAL QA
============================================================

Do not stop when it compiles.

Inspect the actual application visually.

Fix:

- awkward spacing
- excessive cards
- poor map framing
- weak typography
- tiny text
- excessive controls
- duplicate information
- ugly empty state
- generic dashboard appearance
- poor mobile layout

============================================================
60. PRODUCT QUALITY BAR
============================================================

The final application should feel like:

A real geospatial climate intelligence product.

Not:

"a frontend generated around an API."

The user should immediately understand:

WHERE
→ real selected location

WHAT
→ rainfall / radar / forecast / inundation

HOW MUCH
→ actual measurements/model outputs

WHY
→ real backend evidence + attribution

WHAT NOW
→ risk + warning assessment

============================================================
61. CONTEXT.MD
============================================================

After successful completion, update `context.md`.

Add:

`Frontend Rebuild — Complete Geospatial Product Restoration`

Document only what was actually implemented and verified.

Include:

- frontend stack
- Cesium
- imagery
- terrain
- radar
- inundation
- NWP
- rainfall
- XAI
- warning
- unified API
- testing
- build verification
- browser verification

Do NOT claim any feature that was not actually verified.

============================================================
62. FINAL SUCCESS CRITERION
============================================================

The rebuild is complete ONLY when this exact flow works:

1. Open app
2. Mumbai is shown on the real globe
3. Camera is already focused on Mumbai
4. Real satellite imagery is visible
5. Real 3D terrain is visible
6. Select Mumbai/Pune/Chennai/Guwahati
7. Camera automatically moves to selected location
8. Run analysis
9. Real `/api/v1/predict` request executes
10. Real rainfall result appears
11. Real NWP result appears
12. Real radar result appears
13. Real Sentinel-2/Model 2 result appears
14. Real