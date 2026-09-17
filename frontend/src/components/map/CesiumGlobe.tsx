'use client';

import React, { useEffect, useRef, useState } from 'react';
import type * as CesiumType from 'cesium';
import {
  Compass,
  Maximize2,
  Minimize2,
  Layers,
  ZoomIn,
  ZoomOut,
  Crosshair,
  MapPin,
  AlertTriangle,
} from 'lucide-react';
import { GeoJSONFeatureCollection } from '@/lib/types';
import { formatCoordinates } from '@/lib/formatters';

interface CesiumGlobeProps {
  latitude: number;
  longitude: number;
  locationName: string;
  geojson?: GeoJSONFeatureCollection | null;
  polygonCount?: number;
}

export const CesiumGlobe: React.FC<CesiumGlobeProps> = ({
  latitude,
  longitude,
  locationName,
  geojson,
  polygonCount = 0,
}) => {
  const wrapperRef = useRef<HTMLDivElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const viewerRef = useRef<CesiumType.Viewer | null>(null);
  const geojsonDataSourceRef = useRef<CesiumType.GeoJsonDataSource | null>(null);
  const locationPinEntityRef = useRef<CesiumType.Entity | null>(null);
  const isCesiumLoadedRef = useRef(false);

  const [isInitializing, setIsInitializing] = useState(true);
  const [terrainLoaded, setTerrainLoaded] = useState(false);
  const [satelliteLoaded, setSatelliteLoaded] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [selectedPolygonMeta, setSelectedPolygonMeta] = useState<Record<string, unknown> | null>(null);

  useEffect(() => {
    const handleFullscreenChange = () => {
      setIsFullscreen(Boolean(document.fullscreenElement));
    };
    document.addEventListener('fullscreenchange', handleFullscreenChange);
    return () => {
      document.removeEventListener('fullscreenchange', handleFullscreenChange);
    };
  }, []);

  // Initialize Cesium viewer once
  useEffect(() => {
    let isCancelled = false;

    async function initCesium() {
      if (!containerRef.current || viewerRef.current) return;

      try {
        // Set Cesium base URL for static assets (Workers, Assets, Widgets)
        (window as unknown as { CESIUM_BASE_URL: string }).CESIUM_BASE_URL = '/cesium';

        const Cesium: typeof CesiumType = await import('cesium');
        if (isCancelled || !containerRef.current) return;

        // Configure optional Cesium Ion Token
        const ionToken = process.env.NEXT_PUBLIC_CESIUM_ION_TOKEN;
        if (ionToken) {
          Cesium.Ion.defaultAccessToken = ionToken;
        }

        // Initialize Cesium Viewer with clean minimalist interface
        const viewer = new Cesium.Viewer(containerRef.current, {
          animation: false,
          baseLayerPicker: false,
          fullscreenButton: false,
          geocoder: false,
          homeButton: false,
          infoBox: false, // We use custom precision popover
          sceneModePicker: false,
          selectionIndicator: false,
          timeline: false,
          navigationHelpButton: false,
          navigationInstructionsInitiallyVisible: false,
          scene3DOnly: true,
          shouldAnimate: false,
          contextOptions: {
            webgl: {
              preserveDrawingBuffer: true,
            },
          },
        });

        viewerRef.current = viewer;

        // Hide raw Cesium Ion bottom container, watermarks, and credit popups
        if (viewer.bottomContainer) {
          (viewer.bottomContainer as HTMLElement).style.display = 'none';
        }

        // Suppress raw Cesium Ion error popup panel on UI
        if (viewer.cesiumWidget) {
          (viewer.cesiumWidget as unknown as { showErrorPanel: () => void }).showErrorPanel = () => {};
        }

        // High-fidelity scene optimization: crisp Retina scaling, low SSE, HDR
        viewer.resolutionScale = Math.min(window.devicePixelRatio || 1.0, 2.0);
        viewer.scene.globe.maximumScreenSpaceError = 1.25; // Sharp tile resolution without blurring
        viewer.scene.globe.tileCacheSize = 300;
        viewer.scene.globe.depthTestAgainstTerrain = true;
        viewer.scene.globe.enableLighting = false; // Vivid satellite imagery day and night
        viewer.scene.globe.showWaterEffect = true;
        if (viewer.scene.postProcessStages?.fxaa) {
          viewer.scene.postProcessStages.fxaa.enabled = true;
        }
        viewer.scene.highDynamicRange = true;

        // 1. Configure Base Satellite Imagery
        // Priority 1: Cesium Ion World Imagery (Aerial with labels) using user token
        // Priority 2: ArcGIS MapServer Imagery Provider (reads level limits, avoids grey "data not available" tiles)
        try {
          viewer.imageryLayers.removeAll();
          let baseProvider: CesiumType.ImageryProvider | null = null;

          if (ionToken && typeof Cesium.createWorldImageryAsync === 'function') {
            try {
              baseProvider = await Cesium.createWorldImageryAsync({
                style: Cesium.IonWorldImageryStyle.AERIAL_WITH_LABELS,
              });
            } catch (ionErr) {
              console.warn('[HydroWatch Cesium] Ion World Imagery initialization fallback:', ionErr);
            }
          }

          if (!baseProvider) {
            if (typeof Cesium.ArcGisMapServerImageryProvider?.fromUrl === 'function') {
              baseProvider = await Cesium.ArcGisMapServerImageryProvider.fromUrl(
                'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer',
                { enablePickFeatures: false }
              );
            } else {
              baseProvider = new Cesium.UrlTemplateImageryProvider({
                url: 'https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
                maximumLevel: 18,
              });
            }
          }

          if (baseProvider && !isCancelled && viewerRef.current) {
            viewer.imageryLayers.addImageryProvider(baseProvider);
            setSatelliteLoaded(true);
          }
        } catch (imageryErr) {
          console.warn('[HydroWatch Cesium] Base satellite imagery error:', imageryErr);
        }

        // 2. Configure 3D World Terrain with realistic relief & water mask
        try {
          if (typeof Cesium.createWorldTerrainAsync === 'function') {
            const terrain = await Cesium.createWorldTerrainAsync({
              requestWaterMask: true,
              requestVertexNormals: true,
            });
            if (!isCancelled && viewerRef.current) {
              (terrain as unknown as { errorEvent?: { addEventListener: (cb: () => void) => void } }).errorEvent?.addEventListener(() => {
                setTerrainLoaded(false);
              });
              viewer.terrainProvider = terrain;
              setTerrainLoaded(true);
            }
          } else if (typeof Cesium.Terrain?.fromWorldTerrain === 'function') {
            const terrain = Cesium.Terrain.fromWorldTerrain({
              requestWaterMask: true,
              requestVertexNormals: true,
            });
            if (!isCancelled && viewerRef.current) {
              (terrain as unknown as { errorEvent?: { addEventListener: (cb: () => void) => void } }).errorEvent?.addEventListener(() => {
                setTerrainLoaded(false);
              });
              viewer.scene.setTerrain(terrain);
              setTerrainLoaded(true);
            }
          }
        } catch (terrainErr) {
          console.warn('[HydroWatch Cesium] 3D World Terrain fallback to ellipsoid:', terrainErr);
          setTerrainLoaded(false);
        }

        // 3. Configure Click / Hover Handler for Inundation Polygons
        const handler = new Cesium.ScreenSpaceEventHandler(viewer.scene.canvas);
        handler.setInputAction((movement: { position: CesiumType.Cartesian2 }) => {
          const pickedObject = viewer.scene.pick(movement.position);
          if (Cesium.defined(pickedObject) && pickedObject.id && pickedObject.id.properties) {
            const props: Record<string, unknown> = {};
            const propertyNames = pickedObject.id.properties.propertyNames;
            for (const name of propertyNames) {
              props[name] = pickedObject.id.properties[name]?.getValue();
            }
            setSelectedPolygonMeta(props);
          } else {
            setSelectedPolygonMeta(null);
          }
        }, Cesium.ScreenSpaceEventType.LEFT_CLICK);

        isCesiumLoadedRef.current = true;
        setIsInitializing(false);

        // Fly initial camera to target coordinates
        flyCameraToCoordinates(viewer, latitude, longitude, 18000, -38);
        updateLocationPin(viewer, latitude, longitude, locationName);
      } catch (err) {
        console.error('[HydroWatch Cesium] Viewer initialization failure:', err);
        setErrorMessage('Geospatial view initialization failed. WebGL2 or 3D canvas unavailable.');
        setIsInitializing(false);
      }
    }

    initCesium();

    return () => {
      isCancelled = true;
      if (viewerRef.current && !viewerRef.current.isDestroyed()) {
        viewerRef.current.destroy();
        viewerRef.current = null;
      }
    };
  }, []);

  // Handle Location changes: fly camera and reposition marker immediately
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !isCesiumLoadedRef.current || viewer.isDestroyed()) return;

    flyCameraToCoordinates(viewer, latitude, longitude, 18000, -38);
    updateLocationPin(viewer, latitude, longitude, locationName);
  }, [latitude, longitude, locationName]);

  // Handle GeoJSON inundation polygon updates (or clearing on location change)
  useEffect(() => {
    const viewer = viewerRef.current;
    if (!viewer || !isCesiumLoadedRef.current || viewer.isDestroyed()) return;

    // Immediately remove old GeoJSON data source (strictly prevent cross-location contamination)
    if (geojsonDataSourceRef.current) {
      viewer.dataSources.remove(geojsonDataSourceRef.current, true);
      geojsonDataSourceRef.current = null;
    }
    setSelectedPolygonMeta(null);

    if (!geojson || !geojson.features || geojson.features.length === 0) {
      return;
    }

    const currentGeoJson = geojson;

    // Load new GeoJSON
    async function loadGeoJson() {
      if (!viewer || viewer.isDestroyed() || !currentGeoJson) return;
      try {
        const Cesium: typeof CesiumType = await import('cesium');

        // Defensively filter out permanent coastal ocean water features
        const validFeatures = (currentGeoJson.features || []).filter((feat) => {
          const props = feat.properties || {};
          if (props.is_permanent_water === true || props.water_type === 'coastal_ocean') {
            return false;
          }
          return true;
        });

        if (validFeatures.length === 0) {
          // If all detected water was coastal ocean (or 0 features), keep camera centered on city coordinates
          flyCameraToCoordinates(viewer, latitude, longitude, 18000, -38);
          return;
        }

        const sanitizedGeoJson = {
          ...currentGeoJson,
          features: validFeatures,
        };

        const dataSource = await Cesium.GeoJsonDataSource.load(sanitizedGeoJson as unknown as Record<string, unknown>, {
          stroke: Cesium.Color.fromCssColorString('#00E5FF'),
          fill: Cesium.Color.fromCssColorString('rgba(0, 180, 216, 0.42)'),
          strokeWidth: 2.5,
          clampToGround: true,
        });

        if (viewer.isDestroyed()) return;
        geojsonDataSourceRef.current = dataSource;
        await viewer.dataSources.add(dataSource);

        // Fly camera to intelligently fit inundation bounding box
        viewer.flyTo(dataSource, {
          duration: 2.0,
          offset: new Cesium.HeadingPitchRange(0, Cesium.Math.toRadians(-38), 0),
        });
      } catch (geoErr) {
        console.warn('[HydroWatch Cesium] GeoJSON polygon rendering error:', geoErr);
      }
    }

    loadGeoJson();
  }, [geojson, latitude, longitude]);

  // Camera Helper Functions
  const flyCameraToCoordinates = async (
    viewer: CesiumType.Viewer,
    lat: number,
    lon: number,
    height: number,
    pitchDeg: number
  ) => {
    const Cesium: typeof CesiumType = await import('cesium');
    viewer.camera.flyTo({
      destination: Cesium.Cartesian3.fromDegrees(lon, lat, height),
      orientation: {
        heading: Cesium.Math.toRadians(0.0),
        pitch: Cesium.Math.toRadians(pitchDeg),
        roll: 0.0,
      },
      duration: 1.8,
    });
  };

  const updateLocationPin = async (
    viewer: CesiumType.Viewer,
    lat: number,
    lon: number,
    name: string
  ) => {
    const Cesium: typeof CesiumType = await import('cesium');
    if (locationPinEntityRef.current) {
      viewer.entities.remove(locationPinEntityRef.current);
      locationPinEntityRef.current = null;
    }

    const pinEntity = viewer.entities.add({
      name: `Analysis Point: ${name}`,
      position: Cesium.Cartesian3.fromDegrees(lon, lat),
      point: {
        pixelSize: 10,
        color: Cesium.Color.fromCssColorString('#00E5FF'),
        outlineColor: Cesium.Color.WHITE,
        outlineWidth: 2,
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
      label: {
        text: name.toUpperCase(),
        font: 'bold 11px monospace',
        fillColor: Cesium.Color.WHITE,
        outlineColor: Cesium.Color.fromCssColorString('#08090C'),
        outlineWidth: 3,
        style: Cesium.LabelStyle.FILL_AND_OUTLINE,
        verticalOrigin: Cesium.VerticalOrigin.BOTTOM,
        pixelOffset: new Cesium.Cartesian2(0, -12),
        heightReference: Cesium.HeightReference.CLAMP_TO_GROUND,
        disableDepthTestDistance: Number.POSITIVE_INFINITY,
      },
    });

    locationPinEntityRef.current = pinEntity;
  };

  // Map Controls Callbacks
  const handleFocusLocation = () => {
    if (!viewerRef.current) return;
    flyCameraToCoordinates(viewerRef.current, latitude, longitude, 16000, -38);
  };

  const handleFocusInundation = () => {
    if (!viewerRef.current || !geojsonDataSourceRef.current) return;
    viewerRef.current.flyTo(geojsonDataSourceRef.current, { duration: 1.5 });
  };

  const handleResetNorth = async () => {
    if (!viewerRef.current) return;
    const Cesium: typeof CesiumType = await import('cesium');
    const camera = viewerRef.current.camera;
    camera.flyTo({
      destination: camera.position,
      orientation: {
        heading: 0,
        pitch: camera.pitch,
        roll: 0,
      },
      duration: 1.0,
    });
  };

  const handleZoom = (inward: boolean) => {
    if (!viewerRef.current) return;
    const camera = viewerRef.current.camera;
    const moveAmount = camera.positionCartographic.height * 0.35;
    if (inward) {
      camera.zoomIn(moveAmount);
    } else {
      camera.zoomOut(moveAmount);
    }
  };

  const toggleFullscreen = () => {
    if (!wrapperRef.current) return;
    if (!document.fullscreenElement) {
      wrapperRef.current.requestFullscreen().then(() => setIsFullscreen(true)).catch(() => {});
    } else {
      document.exitFullscreen().then(() => setIsFullscreen(false)).catch(() => {});
    }
  };

  return (
    <div
      ref={wrapperRef}
      className={`relative w-full ${
        isFullscreen ? 'h-screen w-screen rounded-none' : 'h-[540px] md:h-[620px] rounded-lg'
      } bg-[#08090c] overflow-hidden border border-[#1e2638] shadow-2xl transition-all`}
    >
      {/* Cesium Canvas Container */}
      <div ref={containerRef} className="w-full h-full" id="cesium-container" />

      {/* Loading Indicator */}
      {isInitializing && (
        <div className="absolute inset-0 bg-[#08090c]/90 flex flex-col items-center justify-center gap-3 z-30">
          <div className="w-8 h-8 border-2 border-[#00e5ff] border-t-transparent rounded-full animate-spin" />
          <p className="text-xs font-mono uppercase tracking-widest text-[#94a3b8]">
            Initializing 3D World Globe & Terrain Mesh...
          </p>
        </div>
      )}

      {/* Error Fallback */}
      {errorMessage && (
        <div className="absolute inset-0 bg-[#08090c]/95 flex flex-col items-center justify-center p-6 text-center z-30">
          <AlertTriangle className="w-10 h-10 text-[#f59e0b] mb-2" />
          <h3 className="text-sm font-semibold text-white mb-1">Geospatial View Unavailable</h3>
          <p className="text-xs text-[#94a3b8] max-w-md mb-4">{errorMessage}</p>
        </div>
      )}

      {/* Minimal Floating Map Controls (Top-Right) */}
      <div className="absolute top-3 right-3 z-20 flex flex-col gap-1.5 bg-[#0e121a]/85 backdrop-blur-md border border-[#1e2638] p-1 rounded-md shadow-lg">
        <button
          type="button"
          onClick={handleFocusLocation}
          title="Center on Selected Location"
          className="p-1.5 rounded hover:bg-[#1b2234] text-[#94a3b8] hover:text-[#00e5ff] transition-colors"
        >
          <Crosshair className="w-4 h-4" />
        </button>
        {polygonCount > 0 && (
          <button
            type="button"
            onClick={handleFocusInundation}
            title="Fit to Detected Water Extent"
            className="p-1.5 rounded hover:bg-[#1b2234] text-[#00e5ff] hover:text-white transition-colors"
          >
            <Layers className="w-4 h-4" />
          </button>
        )}
        <button
          type="button"
          onClick={handleResetNorth}
          title="Reset North Heading"
          className="p-1.5 rounded hover:bg-[#1b2234] text-[#94a3b8] hover:text-white transition-colors"
        >
          <Compass className="w-4 h-4" />
        </button>
        <div className="border-t border-[#1e2638] my-0.5" />
        <button
          type="button"
          onClick={() => handleZoom(true)}
          title="Zoom In"
          className="p-1.5 rounded hover:bg-[#1b2234] text-[#94a3b8] hover:text-white transition-colors"
        >
          <ZoomIn className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={() => handleZoom(false)}
          title="Zoom Out"
          className="p-1.5 rounded hover:bg-[#1b2234] text-[#94a3b8] hover:text-white transition-colors"
        >
          <ZoomOut className="w-4 h-4" />
        </button>
        <button
          type="button"
          onClick={toggleFullscreen}
          title="Toggle Fullscreen"
          className="p-1.5 rounded hover:bg-[#1b2234] text-[#94a3b8] hover:text-white transition-colors"
        >
          {isFullscreen ? <Minimize2 className="w-4 h-4" /> : <Maximize2 className="w-4 h-4" />}
        </button>
      </div>

      {/* 4-Layer Geospatial Active Legend (Bottom-Left) */}
      <div className="absolute bottom-3 left-3 z-20 bg-[#0e121a]/90 backdrop-blur-md border border-[#1e2638] px-3 py-2 rounded-md shadow-lg text-[11px] font-mono space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-2.5 rounded-full bg-[#00e5ff] border border-white" />
          <span className="text-white">Selected Point: {locationName}</span>
        </div>
        <div className="flex items-center gap-2">
          <span className="w-3.5 h-2.5 rounded-sm bg-[#00b4d8]/40 border border-[#00e5ff]" />
          <span className="text-[#cbd5e1]">
            Detected Surface Water / Model 2 Water Segmentation {polygonCount > 0 ? `(${polygonCount} vectors)` : '(0 vectors)'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${terrainLoaded ? 'bg-[#10b981]' : 'bg-[#94a3b8]'}`} />
          <span className="text-[#94a3b8]">
            {terrainLoaded ? '3D World Terrain Active' : '3D Terrain Unavailable'}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <span className={`w-2 h-2 rounded-full ${satelliteLoaded ? 'bg-[#10b981]' : 'bg-[#94a3b8]'}`} />
          <span className="text-[#94a3b8]">Esri World Satellite Imagery</span>
        </div>
      </div>

      {/* Polygon Inspection Popover (when user clicks an inundation vector) */}
      {selectedPolygonMeta && (
        <div className="absolute top-3 left-3 z-20 bg-[#0f131d]/95 backdrop-blur-md border border-[#00e5ff]/40 p-3 rounded-md shadow-2xl max-w-xs text-xs">
          <div className="flex items-center justify-between border-b border-[#1e2638] pb-1.5 mb-2">
            <span className="font-bold text-[#00e5ff] uppercase tracking-wider text-[11px]">
              Detected Surface Water Polygon (Model 2)
            </span>
            <button
              type="button"
              onClick={() => setSelectedPolygonMeta(null)}
              className="text-[#64748b] hover:text-white text-xs px-1"
            >
              ✕
            </button>
          </div>
          <div className="space-y-1 font-mono text-[11px]">
            {selectedPolygonMeta.flooded_area_sq_m !== undefined && (
              <div className="flex justify-between">
                <span className="text-[#94a3b8]">Surface Area:</span>
                <span className="text-white font-semibold">
                  {(Number(selectedPolygonMeta.flooded_area_sq_m) / 1000000).toFixed(4)} km²
                </span>
              </div>
            )}
            {selectedPolygonMeta.perimeter_m !== undefined && (
              <div className="flex justify-between">
                <span className="text-[#94a3b8]">Perimeter:</span>
                <span className="text-white font-semibold">
                  {Math.round(Number(selectedPolygonMeta.perimeter_m))} m
                </span>
              </div>
            )}
            {selectedPolygonMeta.water_type !== undefined && (
              <div className="flex justify-between">
                <span className="text-[#94a3b8]">Classification:</span>
                <span className="text-[#00e5ff] capitalize font-medium">
                  {String(selectedPolygonMeta.water_type).replace('_', ' ')}
                </span>
              </div>
            )}
            {selectedPolygonMeta.scene_id !== undefined && (
              <div className="flex justify-between gap-2">
                <span className="text-[#94a3b8]">Scene ID:</span>
                <span className="text-white truncate max-w-[140px]" title={String(selectedPolygonMeta.scene_id)}>
                  {String(selectedPolygonMeta.scene_id)}
                </span>
              </div>
            )}
            {selectedPolygonMeta.source !== undefined && (
              <div className="flex justify-between gap-2">
                <span className="text-[#94a3b8]">Source:</span>
                <span className="text-white truncate max-w-[140px]">
                  {String(selectedPolygonMeta.source)}
                </span>
              </div>
            )}
          </div>
          <div className="text-[10px] text-[#64748b] border-t border-[#1e2638] pt-1.5 mt-2">
            Historical Satellite Baseline · Model 2 Water Segmentation (includes permanent water)
          </div>
        </div>
      )}
    </div>
  );
};
