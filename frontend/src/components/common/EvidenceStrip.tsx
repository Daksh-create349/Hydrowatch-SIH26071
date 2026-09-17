'use client';

import React, { useState } from 'react';
import {
  CloudRain,
  Radio,
  TrendingUp,
  Droplets,
  ExternalLink,
  Satellite,
  Calendar,
} from 'lucide-react';
import {
  UnifiedRainfallSummary,
  UnifiedRadarSummary,
  UnifiedNwpSummary,
  UnifiedInundationSummary,
} from '@/lib/types';
import { formatNumber, formatTimestamp, formatRelativeAge } from '@/lib/formatters';

interface EvidenceStripProps {
  rainfall?: UnifiedRainfallSummary | null;
  radar?: UnifiedRadarSummary | null;
  nwp?: UnifiedNwpSummary | null;
  inundation?: UnifiedInundationSummary | null;
  onOpenRadarModal: () => void;
}

export const EvidenceStrip: React.FC<EvidenceStripProps> = ({
  rainfall,
  radar,
  nwp,
  inundation,
  onOpenRadarModal,
}) => {
  const [hoveredNwpIndex, setHoveredNwpIndex] = useState<number | null>(null);

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
      {/* 1. Rainfall Stream (XGBoost Model 1) */}
      <div className="bg-[#0b0e16] border border-[#1e2638] rounded-lg p-3.5 shadow-lg flex flex-col justify-between space-y-3">
        <div>
          <div className="flex items-center justify-between text-[11px] font-mono uppercase text-[#64748b]">
            <span className="flex items-center gap-1.5 text-white font-semibold">
              <CloudRain className="w-3.5 h-3.5 text-[#00e5ff]" />
              Heavy Rainfall Model
            </span>
            <span className="text-[#94a3b8]">XGBoost v2</span>
          </div>

          {rainfall ? (
            <div className="mt-2.5 space-y-2">
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-white">
                    {(rainfall.probability * 100).toFixed(1)}%
                  </div>
                  <div className="text-[10px] text-[#64748b] font-mono">
                    Heavy Rain Probability
                  </div>
                </div>
                <div
                  className={`px-2 py-0.5 rounded text-[11px] font-bold font-mono uppercase tracking-wider ${
                    rainfall.predicted
                      ? 'bg-[#ef4444]/20 text-[#ef4444] border border-[#ef4444]/40'
                      : 'bg-[#10b981]/20 text-[#10b981] border border-[#10b981]/40'
                  }`}
                >
                  {rainfall.predicted ? 'PREDICTED' : 'BELOW THRESHOLD'}
                </div>
              </div>

              {/* Linear Probability Visualizer with 0.81 Threshold Marker */}
              <div className="space-y-1">
                <div className="relative w-full h-2.5 bg-[#141824] rounded-full overflow-hidden border border-[#2a3449]">
                  <div
                    className={`h-full transition-all duration-500 ${
                      rainfall.probability >= rainfall.threshold
                        ? 'bg-gradient-to-r from-[#0284c7] to-[#ef4444]'
                        : 'bg-[#0284c7]'
                    }`}
                    style={{ width: `${Math.min(100, rainfall.probability * 100)}%` }}
                  />
                  {/* 81% Threshold Marker */}
                  <div
                    className="absolute top-0 bottom-0 w-0.5 bg-white shadow-sm"
                    style={{ left: '81%' }}
                    title="0.81 Operational Threshold"
                  />
                </div>
                <div className="flex justify-between text-[10px] font-mono text-[#64748b]">
                  <span>0%</span>
                  <span className="text-[#f59e0b] font-semibold">0.81 Decision Threshold</span>
                  <span>100%</span>
                </div>
              </div>

              <div className="pt-2 border-t border-[#1e2638] flex items-center justify-between text-[11px] text-[#94a3b8] font-mono">
                <span>D-1 Precipitation:</span>
                <span className="text-white font-semibold">
                  {formatNumber(rainfall.latest_precipitation_mm, 1)} mm/day
                </span>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-[#64748b] font-mono">
              Stream Pending Analysis
            </div>
          )}
        </div>

        {rainfall && (
          <div className="text-[10px] text-[#64748b] font-mono pt-2 border-t border-[#1e2638]/50 flex justify-between">
            <span>NASA POWER · 37 Features</span>
            <span>Obs: {rainfall.observation_date}</span>
          </div>
        )}
      </div>

      {/* 2. Radar Stream (RainViewer Doppler Radar) */}
      <div className="bg-[#0b0e16] border border-[#1e2638] rounded-lg p-3.5 shadow-lg flex flex-col justify-between space-y-3">
        <div>
          <div className="flex items-center justify-between text-[11px] font-mono uppercase text-[#64748b]">
            <span className="flex items-center gap-1.5 text-white font-semibold">
              <Radio className="w-3.5 h-3.5 text-[#00e5ff]" />
              Doppler Weather Radar
            </span>
            <span className="text-[#94a3b8]">Composite</span>
          </div>

          {radar ? (
            <div className="mt-2.5 space-y-2">
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-white">
                    {formatNumber(radar.max_reflectivity_dbz, 1)}{' '}
                    <span className="text-xs text-[#94a3b8]">dBZ</span>
                  </div>
                  <div className="text-[10px] text-[#64748b] font-mono">
                    Max Echo Reflectivity
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold font-mono text-[#00e5ff]">
                    {formatNumber(radar.estimated_rain_rate_mm_hr, 1)} mm/h
                  </div>
                  <div className="text-[10px] text-[#64748b] font-mono">
                    Est. Rain Rate (Z-R)
                  </div>
                </div>
              </div>

              {/* Reflectivity Scale Indicator */}
              <div className="bg-[#121622] p-2 rounded border border-[#1e2638] flex items-center justify-between text-xs">
                <span className="text-[11px] text-[#94a3b8]">Spatial Echo Coverage:</span>
                <span className="font-mono text-white font-semibold">
                  {formatNumber(radar.coverage_percentage, 1)}%
                </span>
              </div>

              <button
                type="button"
                onClick={onOpenRadarModal}
                className="w-full flex items-center justify-center gap-1.5 py-1.5 px-3 rounded bg-[#141824] hover:bg-[#1a2130] border border-[#2a3449] hover:border-[#00e5ff]/50 text-[#00e5ff] text-xs font-semibold transition-colors"
              >
                <Radio className="w-3.5 h-3.5" />
                <span>Inspect Live Doppler Viewer</span>
                <ExternalLink className="w-3 h-3 ml-1" />
              </button>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-[#64748b] font-mono">
              Radar Ingestion Standby
            </div>
          )}
        </div>

        {radar && (
          <div className="text-[10px] text-[#64748b] font-mono pt-2 border-t border-[#1e2638]/50 flex justify-between">
            <span>Doppler Radar Network</span>
            <span>{formatTimestamp(radar.timestamp)}</span>
          </div>
        )}
      </div>

      {/* 3. NWP Meteogram Stream (NOAA GFS via Open-Meteo) */}
      <div className="bg-[#0b0e16] border border-[#1e2638] rounded-lg p-3.5 shadow-lg flex flex-col justify-between space-y-3">
        <div>
          <div className="flex items-center justify-between text-[11px] font-mono uppercase text-[#64748b]">
            <span className="flex items-center gap-1.5 text-white font-semibold">
              <TrendingUp className="w-3.5 h-3.5 text-[#00e5ff]" />
              NWP 24h GFS Forecast
            </span>
            <span className="text-[#94a3b8]">0.25° Grid</span>
          </div>

          {nwp && nwp.hourly_precipitation && nwp.hourly_precipitation.length > 0 ? (
            <div className="mt-2.5 space-y-2">
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-white">
                    {formatNumber(nwp.peak_hourly_precipitation_mm_hr, 1)}{' '}
                    <span className="text-xs text-[#94a3b8]">mm/h</span>
                  </div>
                  <div className="text-[10px] text-[#64748b] font-mono">Peak Hourly Rate</div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold font-mono text-[#00e5ff]">
                    {formatNumber(nwp.accumulated_precipitation_mm, 1)} mm
                  </div>
                  <div className="text-[10px] text-[#64748b] font-mono">24h Accumulated</div>
                </div>
              </div>

              {/* Interactive SVG Meteogram Bar Chart */}
              <div className="relative pt-2">
                <div className="h-16 flex items-end gap-1 bg-[#121622] p-1.5 rounded border border-[#1e2638]">
                  {nwp.hourly_precipitation.slice(0, 24).map((val, idx) => {
                    const maxVal = Math.max(1, ...nwp.hourly_precipitation);
                    const heightPct = Math.max(4, (val / maxVal) * 100);
                    const isPeak = val === nwp.peak_hourly_precipitation_mm_hr && val > 0;
                    const isHovered = hoveredNwpIndex === idx;

                    return (
                      <div
                        key={idx}
                        onMouseEnter={() => setHoveredNwpIndex(idx)}
                        onMouseLeave={() => setHoveredNwpIndex(null)}
                        className="relative flex-1 h-full flex items-end cursor-pointer group"
                      >
                        <div
                          className={`w-full rounded-t-sm transition-all ${
                            isPeak
                              ? 'bg-[#f59e0b]'
                              : isHovered
                              ? 'bg-[#00e5ff]'
                              : val > 10
                              ? 'bg-[#0284c7]'
                              : 'bg-[#2a3449]'
                          }`}
                          style={{ height: `${heightPct}%` }}
                        />
                      </div>
                    );
                  })}
                </div>

                {/* Tooltip on Hover */}
                {hoveredNwpIndex !== null && (
                  <div className="absolute -top-6 left-1/2 -translate-x-1/2 bg-[#161b26] border border-[#00e5ff] px-2 py-0.5 rounded text-[10px] font-mono text-white whitespace-nowrap shadow-lg">
                    T+{hoveredNwpIndex + 1}h: {nwp.hourly_precipitation[hoveredNwpIndex]} mm/h
                  </div>
                )}

                <div className="flex justify-between text-[10px] font-mono text-[#64748b] mt-1">
                  <span>T+0h</span>
                  <span>T+12h</span>
                  <span>T+24h</span>
                </div>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-[#64748b] font-mono">
              NWP Forecast Standby
            </div>
          )}
        </div>

        {nwp && (
          <div className="text-[10px] text-[#64748b] font-mono pt-2 border-t border-[#1e2638]/50 flex justify-between">
            <span>NOAA GFS · Open-Meteo</span>
            <span>Horizon: {nwp.forecast_horizon_hours}h</span>
          </div>
        )}
      </div>

      {/* 4. Inundation Stream (Sentinel-2 + Model 2 FloodUNet) */}
      <div className="bg-[#0b0e16] border border-[#1e2638] rounded-lg p-3.5 shadow-lg flex flex-col justify-between space-y-3">
        <div>
          <div className="flex items-center justify-between text-[11px] font-mono uppercase text-[#64748b]">
            <span className="flex items-center gap-1.5 text-white font-semibold">
              <Droplets className="w-3.5 h-3.5 text-[#00e5ff]" />
              Detected Surface Water
            </span>
            <span className="text-[#94a3b8]">Model 2 Water Segmentation</span>
          </div>

          {inundation ? (
            <div className="mt-2.5 space-y-2">
              <div className="flex items-baseline justify-between">
                <div>
                  <div className="text-2xl font-bold font-mono text-white">
                    {formatNumber(inundation.flooded_area_sq_km, 2)}{' '}
                    <span className="text-xs text-[#94a3b8]">km²</span>
                  </div>
                  <div className="text-[10px] text-[#64748b] font-mono">
                    Model 2 Water Mask Extent
                  </div>
                </div>
                <div className="text-right">
                  <div className="text-sm font-bold font-mono text-[#00e5ff]">
                    {inundation.polygon_count}
                  </div>
                  <div className="text-[10px] text-[#64748b] font-mono">Vector Polygons</div>
                </div>
              </div>

              {/* Ground Coverage Percentage */}
              <div className="bg-[#121622] p-2 rounded border border-[#1e2638] flex items-center justify-between text-xs">
                <span className="text-[11px] text-[#94a3b8]">Detected Surface Water Extent:</span>
                <span className="font-mono text-white font-semibold">
                  {formatNumber(inundation.flooded_percentage, 1)}% of Scene
                </span>
              </div>

              {/* Historical Baseline Reference (Strict Separation) */}
              <div className="p-2 rounded bg-[#0e121a] border border-[#1e2638] text-[11px] space-y-1">
                <div className="flex items-center justify-between text-[10px] font-mono uppercase text-[#64748b]">
                  <span className="flex items-center gap-1">
                    <Satellite className="w-3 h-3 text-[#00e5ff]" />
                    Historical Satellite Baseline
                  </span>
                  <span className="text-[#94a3b8]">
                    {formatRelativeAge(inundation.scene?.acquisition_datetime)}
                  </span>
                </div>
                <div className="flex justify-between text-white font-mono text-[10px]">
                  <span className="truncate max-w-[120px]" title={inundation.scene?.scene_id}>
                    {inundation.scene?.scene_id || 'Granule Active'}
                  </span>
                  <span className="text-[#94a3b8]">
                    Cloud: {formatNumber(inundation.scene?.cloud_coverage_percentage, 1)}%
                  </span>
                </div>
                <div className="text-[9px] text-[#64748b] font-mono pt-1 border-t border-[#1e2638]/40">
                  Historical archive capture · Baseline water reference (not live flood)
                </div>
              </div>
            </div>
          ) : (
            <div className="py-6 text-center text-xs text-[#64748b] font-mono">
              Detected Surface Water Standby
            </div>
          )}
        </div>

        {inundation && (
          <div className="text-[10px] text-[#64748b] font-mono pt-2 border-t border-[#1e2638]/50 flex justify-between">
            <span>Element 84 Earth Search</span>
            <span>6-Band Multispectral</span>
          </div>
        )}
      </div>
    </div>
  );
};
