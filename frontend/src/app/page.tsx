'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react';
import dynamic from 'next/dynamic';
import { Header } from '@/components/app-shell/Header';
import { AnalysisCommand } from '@/components/location/AnalysisCommand';
import { MapHud } from '@/components/map/MapHud';
import { WarningPanel } from '@/components/warning/WarningPanel';
import { EvidenceStrip } from '@/components/common/EvidenceStrip';
import { RadarModal } from '@/components/radar/RadarModal';
import { WhyAssessment } from '@/components/explainability/WhyAssessment';
import { FreshnessTimeline } from '@/components/source-status/FreshnessTimeline';
import { AuditPanel } from '@/components/provenance/AuditPanel';
import { AnalysisProgress } from '@/components/loading/AnalysisProgress';
import { ErrorState } from '@/components/common/ErrorState';
import { PRESET_LOCATIONS } from '@/lib/constants';
import { PresetLocation, UnifiedPredictionResponse } from '@/lib/types';
import { runUnifiedPrediction, checkBackendHealth } from '@/lib/api';

// Dynamically import Cesium with SSR disabled to prevent Node canvas errors
const DynamicCesiumGlobe = dynamic(
  () => import('@/components/map/CesiumGlobe').then((mod) => mod.CesiumGlobe),
  {
    ssr: false,
    loading: () => (
      <div className="w-full h-[540px] md:h-[620px] bg-[#08090c] rounded-lg flex flex-col items-center justify-center border border-[#1e2638] text-xs font-mono text-[#64748b]">
        <div className="w-8 h-8 border-2 border-[#00e5ff] border-t-transparent rounded-full animate-spin mb-3" />
        <span>INITIALIZING GEOSPATIAL 3D ENGINE...</span>
      </div>
    ),
  }
);

export default function HydroWatchDashboard() {
  // Location State (Default: Mumbai, Maharashtra)
  const [selectedLocation, setSelectedLocation] = useState<PresetLocation>(PRESET_LOCATIONS[0]);
  const [latitude, setLatitude] = useState<number>(PRESET_LOCATIONS[0].latitude);
  const [longitude, setLongitude] = useState<number>(PRESET_LOCATIONS[0].longitude);
  const [locationName, setLocationName] = useState<string>(PRESET_LOCATIONS[0].name);

  // Analysis Parameters (Default: 2024-07-15 peak monsoon validation benchmark)
  const [predictionDate, setPredictionDate] = useState<string>('2024-07-15');
  const [nwpHorizonHours, setNwpHorizonHours] = useState<number>(24);
  const [satelliteMaxCloud, setSatelliteMaxCloud] = useState<number>(60);

  // Execution & Telemetry State
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [data, setData] = useState<UnifiedPredictionResponse | null>(null);
  const [error, setError] = useState<{ message: string; details?: string } | null>(null);
  const [isBackendHealthy, setIsBackendHealthy] = useState<boolean>(true);
  const [isRadarModalOpen, setIsRadarModalOpen] = useState<boolean>(false);

  const abortControllerRef = useRef<AbortController | null>(null);

  // Check backend health on initial mount
  useEffect(() => {
    checkBackendHealth()
      .then(() => setIsBackendHealthy(true))
      .catch((err) => {
        console.warn('[HydroWatch] Backend connection warning:', err);
        setIsBackendHealthy(false);
      });
  }, []);

  // Location Preset Switch: STRICT STATE ISOLATION (immediately clear old data)
  const handleSelectPreset = useCallback((preset: PresetLocation) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    // Immediately clear all previous prediction geometry and metrics
    setData(null);
    setError(null);
    setSelectedLocation(preset);
    setLatitude(preset.latitude);
    setLongitude(preset.longitude);
    setLocationName(preset.name);
  }, []);

  // Custom Coordinates Selection: STRICT STATE ISOLATION
  const handleSelectCustom = useCallback((lat: number, lon: number, name: string) => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
      abortControllerRef.current = null;
    }
    setData(null);
    setError(null);
    setSelectedLocation({
      id: 'custom',
      name: name || 'Custom Point',
      state: 'User Defined',
      latitude: lat,
      longitude: lon,
      defaultZoomAltitude: 18000,
    });
    setLatitude(lat);
    setLongitude(lon);
    setLocationName(name || 'Custom Point');
  }, []);

  // Execute Unified Prediction Pipeline
  const handleRunAnalysis = useCallback(async () => {
    if (isLoading) return;

    if (abortControllerRef.current) {
      abortControllerRef.current.abort();
    }
    const controller = new AbortController();
    abortControllerRef.current = controller;

    setIsLoading(true);
    setError(null);

    try {
      const response = await runUnifiedPrediction(
        {
          latitude,
          longitude,
          prediction_date: predictionDate,
          nwp_horizon_hours: nwpHorizonHours,
          satellite_max_cloud: satelliteMaxCloud,
          location_name: locationName,
        },
        controller.signal
      );

      setData(response);
      setIsBackendHealthy(true);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') {
        return; // Request was cleanly cancelled by user switching location
      }
      console.error('[HydroWatch] Analysis failed:', err);
      const errMsg = err instanceof Error ? err.message : 'Environmental synthesis failed.';
      setError({
        message: 'Could not complete multi-source environmental assessment for target location.',
        details: errMsg,
      });
    } finally {
      setIsLoading(false);
      abortControllerRef.current = null;
    }
  }, [latitude, longitude, predictionDate, nwpHorizonHours, satelliteMaxCloud, locationName, isLoading]);

  return (
    <div className="min-h-screen bg-[#08090c] flex flex-col selection:bg-[#0284c7]/30 selection:text-[#00e5ff]">
      {/* 1. Authoritative Header */}
      <Header
        locationName={locationName}
        latitude={latitude}
        longitude={longitude}
        generatedAt={data?.generated_at}
        isBackendHealthy={isBackendHealthy}
        streamsOnlineCount={
          data?.source_status
            ? Object.values(data.source_status).filter((s) => s.available).length
            : isBackendHealthy
            ? 4
            : 0
        }
      />

      {/* Main Dashboard Layout */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-3 sm:p-5 space-y-5">
        {/* 2. Floating Command Bar */}
        <AnalysisCommand
          selectedLocation={selectedLocation}
          onSelectPreset={handleSelectPreset}
          onSelectCustom={handleSelectCustom}
          onRunAnalysis={handleRunAnalysis}
          isLoading={isLoading}
          predictionDate={predictionDate}
          onChangeDate={setPredictionDate}
          nwpHorizonHours={nwpHorizonHours}
          onChangeNwpHorizon={setNwpHorizonHours}
          satelliteMaxCloud={satelliteMaxCloud}
          onChangeSatelliteMaxCloud={setSatelliteMaxCloud}
        />

        {/* 3. Hero Geospatial Section: Real 3D Terrain Globe & Map HUD */}
        <section className="relative">
          <DynamicCesiumGlobe
            latitude={latitude}
            longitude={longitude}
            locationName={locationName}
            geojson={data?.inundation?.geojson}
            polygonCount={data?.inundation?.polygon_count}
          />

          {/* Floating Map HUD (Overlay on desktop) */}
          <div className="mt-3 lg:mt-0 lg:absolute lg:top-3 lg:left-3 z-20">
            <MapHud
              locationName={locationName}
              latitude={latitude}
              longitude={longitude}
              riskScore={data?.risk?.score}
              riskLevel={data?.risk?.level}
              warningStatus={data?.warning?.status}
              warningUrgency={data?.warning?.urgency}
              floodedAreaKm2={data?.inundation?.flooded_area_sq_km}
              floodedPercentage={data?.inundation?.flooded_percentage}
              polygonCount={data?.inundation?.polygon_count}
              satelliteAcquisitionTime={
                (data?.inundation?.scene?.acquisition_datetime as string) || null
              }
            />
          </div>
        </section>

        {/* Loading Progress State */}
        {isLoading && (
          <section className="py-4">
            <AnalysisProgress locationName={locationName} stagesCompleted={2} />
          </section>
        )}

        {/* Error Notification State */}
        {error && !isLoading && (
          <section className="py-2">
            <ErrorState
              message={error.message}
              details={error.details}
              onRetry={handleRunAnalysis}
            />
          </section>
        )}

        {/* 4. Prototype Early Warning Instrument */}
        <section>
          <WarningPanel warning={data?.warning} />
        </section>

        {/* 5. Physical Telemetry Evidence Matrix (Rainfall, Radar, NWP 24h, Inundation) */}
        <section>
          <EvidenceStrip
            rainfall={data?.rainfall_prediction}
            radar={data?.radar}
            nwp={data?.nwp}
            inundation={data?.inundation}
            onOpenRadarModal={() => setIsRadarModalOpen(true)}
          />
        </section>

        {/* 6. Explainability: Mathematical Multi-Source Attribution & Tree SHAP */}
        <section>
          <WhyAssessment
            risk={data?.risk}
            xai={data?.rainfall_prediction?.xai}
            inundation={data?.inundation}
            radar={data?.radar}
            nwp={data?.nwp}
            lat={latitude}
            lon={longitude}
            onOpenRadarModal={() => setIsRadarModalOpen(true)}
          />
        </section>

        {/* 7. Source Freshness & Latency Breakdown */}
        <section>
          <FreshnessTimeline
            sourceStatus={data?.source_status}
            timing={data?.timing}
          />
        </section>

        {/* 8. Technical Diagnostic Provenance Drawer */}
        <section>
          <AuditPanel data={data} />
        </section>
      </main>

      {/* Dedicated RainViewer Doppler Radar Modal */}
      <RadarModal
        isOpen={isRadarModalOpen}
        onClose={() => setIsRadarModalOpen(false)}
        radar={data?.radar}
        latitude={latitude}
        longitude={longitude}
        locationName={locationName}
      />
    </div>
  );
}
