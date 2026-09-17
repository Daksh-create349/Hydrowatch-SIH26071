'use client';

import React from 'react';
import { X, Radio, ExternalLink, Info, Activity } from 'lucide-react';
import { UnifiedRadarSummary } from '@/lib/types';
import { RADAR_DBZ_THRESHOLDS } from '@/lib/constants';
import { formatCoordinates, formatNumber, formatTimestamp } from '@/lib/formatters';

interface RadarModalProps {
  isOpen: boolean;
  onClose: () => void;
  radar?: UnifiedRadarSummary | null;
  latitude: number;
  longitude: number;
  locationName: string;
}

export const RadarModal: React.FC<RadarModalProps> = ({
  isOpen,
  onClose,
  radar,
  latitude,
  longitude,
  locationName,
}) => {
  if (!isOpen) return null;

  // Real RainViewer interactive web embed centered on target coordinates
  const rainViewerEmbedUrl = `https://www.rainviewer.com/map.html?loc=${latitude},${longitude},8&oFa=0&oC=1&oU=0&oRev=0&oR=1&oC=1&oT=1&oStatic=0&layer=radar&sm=1&sn=1`;

  const hasEchoes = radar && radar.max_reflectivity_dbz > 10;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3 sm:p-6 bg-black/80 backdrop-blur-sm animate-in fade-in duration-200">
      <div className="bg-[#0c0f17] border border-[#1e2638] rounded-xl w-full max-w-5xl max-h-[92vh] flex flex-col shadow-2xl overflow-hidden">
        {/* Modal Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-[#1e2638] bg-[#101420]">
          <div className="flex items-center gap-2.5">
            <Radio className="w-5 h-5 text-[#00e5ff]" />
            <div>
              <h3 className="font-bold text-white text-sm tracking-wide uppercase">
                Doppler Radar Reflectivity Composite
              </h3>
              <p className="text-[11px] font-mono text-[#94a3b8]">
                {locationName} · {formatCoordinates(latitude, longitude)}
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="p-1 rounded-md hover:bg-[#1e2638] text-[#94a3b8] hover:text-white transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Modal Body */}
        <div className="flex-1 overflow-y-auto p-4 space-y-4">
          {/* Telemetry Metrics Bar */}
          {radar ? (
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2.5">
              <div className="bg-[#121624] border border-[#1e2638] p-3 rounded-lg">
                <div className="text-[10px] font-mono uppercase text-[#64748b]">Max Reflectivity</div>
                <div className="text-xl font-bold font-mono text-white mt-0.5">
                  {formatNumber(radar.max_reflectivity_dbz, 1)} dBZ
                </div>
                <div className="text-[10px] text-[#00e5ff] font-mono mt-0.5">
                  Mean: {formatNumber(radar.mean_reflectivity_dbz, 1)} dBZ
                </div>
              </div>

              <div className="bg-[#121624] border border-[#1e2638] p-3 rounded-lg">
                <div className="text-[10px] font-mono uppercase text-[#64748b]">Est. Rain Rate</div>
                <div className="text-xl font-bold font-mono text-white mt-0.5">
                  {formatNumber(radar.estimated_rain_rate_mm_hr, 1)} mm/h
                </div>
                <div className="text-[10px] text-[#94a3b8] font-mono mt-0.5">
                  Z = 200 · R^1.6
                </div>
              </div>

              <div className="bg-[#121624] border border-[#1e2638] p-3 rounded-lg">
                <div className="text-[10px] font-mono uppercase text-[#64748b]">Spatial Echo Coverage</div>
                <div className="text-xl font-bold font-mono text-white mt-0.5">
                  {formatNumber(radar.coverage_percentage, 1)}%
                </div>
                <div className="text-[10px] text-[#94a3b8] font-mono mt-0.5">
                  Radius ~120 km
                </div>
              </div>

              <div className="bg-[#121624] border border-[#1e2638] p-3 rounded-lg">
                <div className="text-[10px] font-mono uppercase text-[#64748b]">Observation Timestamp</div>
                <div className="text-xs font-bold font-mono text-white mt-1 truncate">
                  {formatTimestamp(radar.timestamp)}
                </div>
                <div className="text-[10px] text-[#10b981] font-mono mt-0.5">
                  Active Composite
                </div>
              </div>
            </div>
          ) : (
            <div className="p-3 bg-[#121624] border border-[#1e2638] rounded-lg text-xs text-[#94a3b8] font-mono">
              Radar telemetry stream offline or pending initial analysis.
            </div>
          )}

          {/* Active Echo Status Banner */}
          {!hasEchoes && radar && (
            <div className="flex items-center gap-2 bg-[#10b981]/10 border border-[#10b981]/30 px-3 py-2 rounded-md text-xs text-[#10b981]">
              <Activity className="w-4 h-4 shrink-0" />
              <span>
                No active convective radar echoes detected over {locationName} at {formatTimestamp(radar.timestamp)}. Reflectivity is below 15 dBZ.
              </span>
            </div>
          )}

          {/* Real Embedded Interactive Radar Map */}
          <div className="relative w-full h-[360px] sm:h-[420px] rounded-lg overflow-hidden border border-[#1e2638] bg-black">
            <iframe
              src={rainViewerEmbedUrl}
              title={`Doppler Radar Composite - ${locationName}`}
              className="w-full h-full border-0"
              allowFullScreen
              loading="lazy"
            />
            {/* Top-left overlap badge covering the rainviewer.com pill button */}
            <div className="absolute top-2 left-3 sm:left-4 bg-[#080b14] border border-[#1e2638] h-[40px] px-4 rounded-full shadow-2xl flex items-center gap-2.5 z-20 pointer-events-auto min-w-[178px]">
              <span className="w-2 h-2 rounded-full bg-[#00e5ff] animate-pulse shrink-0" />
              <span className="text-xs font-mono font-bold text-white tracking-wide uppercase">
                LIVE DOPPLER RADAR
              </span>
            </div>

            {/* Bottom-right watermark overlap badge */}
            <div className="absolute bottom-1.5 right-1.5 bg-[#080b14] border border-[#1e2638] px-3 py-1.5 rounded-md shadow-2xl flex items-center gap-2 z-20 pointer-events-auto">
              <span className="w-2 h-2 rounded-full bg-[#10b981] animate-pulse" />
              <span className="text-[11px] font-mono font-bold text-[#00e5ff] tracking-wider uppercase">
                Doppler Radar Telemetry
              </span>
            </div>
            {/* Bottom-left metadata badge */}
            <div className="absolute bottom-1.5 left-1.5 bg-[#080b14]/95 border border-[#1e2638] px-2.5 py-1 rounded-md shadow-2xl flex items-center gap-1.5 z-20 pointer-events-auto">
              <span className="text-[10px] font-mono text-[#94a3b8]">
                Real-time Reflectivity Sweep · {locationName}
              </span>
            </div>
          </div>

          {/* Reflectivity Severity Color Scale & Provenance */}
          <div className="bg-[#121624] border border-[#1e2638] p-3 rounded-lg space-y-2">
            <div className="text-[11px] font-mono uppercase text-[#64748b] tracking-wider">
              Doppler Reflectivity Severity Scale (dBZ)
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
              {RADAR_DBZ_THRESHOLDS.map((tier, idx) => (
                <div key={idx} className="flex items-center gap-2 text-xs">
                  <span
                    className="w-3 h-3 rounded-sm shrink-0"
                    style={{ backgroundColor: tier.color }}
                  />
                  <div>
                    <div className="font-mono font-semibold text-white">{tier.label}</div>
                    <div className="text-[10px] text-[#94a3b8]">{tier.description}</div>
                  </div>
                </div>
              ))}
            </div>
            <div className="pt-2 border-t border-[#1e2638]/50 flex items-center justify-between text-[11px] text-[#64748b]">
              <span className="flex items-center gap-1">
                <Info className="w-3.5 h-3.5" />
                Operational Doppler Radar Network · Real-time Composite Feed
              </span>
              <a
                href={`https://www.rainviewer.com/weather-radar-map-live.html?loc=${latitude},${longitude},8`}
                target="_blank"
                rel="noopener noreferrer"
                className="text-[#00e5ff] hover:underline flex items-center gap-1 font-mono text-[10px]"
              >
                External Radar Feed <ExternalLink className="w-3 h-3" />
              </a>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
