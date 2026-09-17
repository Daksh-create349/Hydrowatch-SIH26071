'use client';

import React from 'react';
import { Shield, Droplets, Satellite, AlertCircle } from 'lucide-react';
import { RiskLevel, WarningStatus, WarningUrgency } from '@/lib/types';
import { RISK_LEVEL_CONFIG, WARNING_STATUS_CONFIG } from '@/lib/constants';
import { formatCoordinates, formatNumber, formatRelativeAge } from '@/lib/formatters';

interface MapHudProps {
  locationName: string;
  latitude: number;
  longitude: number;
  riskScore?: number | null;
  riskLevel?: RiskLevel | null;
  warningStatus?: WarningStatus | null;
  warningUrgency?: WarningUrgency | null;
  floodedAreaKm2?: number | null;
  floodedPercentage?: number | null;
  polygonCount?: number | null;
  satelliteAcquisitionTime?: string | null;
}

export const MapHud: React.FC<MapHudProps> = ({
  locationName,
  latitude,
  longitude,
  riskScore,
  riskLevel,
  warningStatus,
  floodedAreaKm2,
  floodedPercentage,
  polygonCount,
  satelliteAcquisitionTime,
}) => {
  const activeRisk = riskLevel ? RISK_LEVEL_CONFIG[riskLevel] : null;
  const activeWarning = warningStatus ? WARNING_STATUS_CONFIG[warningStatus] : null;

  return (
    <div className="bg-[#0b0e16]/90 backdrop-blur-md border border-[#1e2638] rounded-lg p-3 shadow-xl max-w-sm w-full space-y-3">
      {/* Target Coordinates */}
      <div className="border-b border-[#1e2638] pb-2">
        <div className="text-white font-bold text-sm tracking-wide uppercase">{locationName}</div>
        <div className="font-mono text-xs text-[#94a3b8]">{formatCoordinates(latitude, longitude)}</div>
      </div>

      {/* Primary Risk & Warning Indicators */}
      <div className="grid grid-cols-2 gap-2">
        {/* Risk Score */}
        <div className="bg-[#121622] border border-[#1e2638] p-2 rounded">
          <div className="text-[10px] font-mono uppercase text-[#64748b] flex items-center gap-1">
            <Shield className="w-3 h-3 text-[#00e5ff]" />
            Composite Risk
          </div>
          <div className="flex items-baseline gap-1.5 mt-1">
            <span className="text-lg font-bold font-mono text-white">
              {riskScore !== undefined && riskScore !== null ? formatNumber(riskScore, 2) : '—'}
            </span>
            {activeRisk && (
              <span
                className="text-[10px] font-bold px-1.5 py-0.5 rounded uppercase"
                style={{ color: activeRisk.color, backgroundColor: activeRisk.bgColor }}
              >
                {riskLevel}
              </span>
            )}
          </div>
        </div>

        {/* Warning State */}
        <div className="bg-[#121622] border border-[#1e2638] p-2 rounded">
          <div className="text-[10px] font-mono uppercase text-[#64748b] flex items-center gap-1">
            <AlertCircle className="w-3 h-3 text-[#f59e0b]" />
            Warning Status
          </div>
          <div className="mt-1">
            {activeWarning ? (
              <span
                className="text-xs font-bold px-2 py-0.5 rounded block text-center truncate uppercase"
                style={{
                  color: activeWarning.color,
                  backgroundColor: activeWarning.bgColor,
                  border: `1px solid ${activeWarning.borderColor}40`,
                }}
              >
                {activeWarning.label}
              </span>
            ) : (
              <span className="text-xs text-[#64748b] font-mono">—</span>
            )}
          </div>
        </div>
      </div>

      {/* Surface Inundation Telemetry */}
      <div className="bg-[#121622] border border-[#1e2638] p-2 rounded space-y-1 text-xs">
        <div className="flex items-center justify-between text-[10px] font-mono uppercase text-[#64748b]">
          <span className="flex items-center gap-1">
            <Droplets className="w-3 h-3 text-[#00e5ff]" />
            Detected Surface Water (Model 2)
          </span>
          {polygonCount !== undefined && polygonCount !== null && (
            <span className="text-[#94a3b8]">{polygonCount} Polygons</span>
          )}
        </div>
        <div className="flex items-baseline justify-between pt-0.5">
          <span className="text-base font-bold font-mono text-white">
            {floodedAreaKm2 !== undefined && floodedAreaKm2 !== null
              ? `${formatNumber(floodedAreaKm2, 2)} km²`
              : '—'}
          </span>
          {floodedPercentage !== undefined && floodedPercentage !== null && (
            <span className="font-mono text-xs text-[#00e5ff]">
              {formatNumber(floodedPercentage, 1)}% Coverage
            </span>
          )}
        </div>
      </div>

      {/* Satellite Acquisition Context */}
      <div className="flex items-center justify-between text-[11px] text-[#64748b] pt-1 border-t border-[#1e2638]/60">
        <span className="flex items-center gap-1">
          <Satellite className="w-3 h-3 text-[#64748b]" />
          Historical Satellite Baseline
        </span>
        <span className="font-mono text-[#cbd5e1]">
          {satelliteAcquisitionTime
            ? `${formatRelativeAge(satelliteAcquisitionTime)} (${satelliteAcquisitionTime.slice(0, 10)})`
            : 'Historical Archive'}
        </span>
      </div>
    </div>
  );
};
