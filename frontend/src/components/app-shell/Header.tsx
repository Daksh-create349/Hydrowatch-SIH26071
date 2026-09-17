'use client';

import React from 'react';
import { Activity, Globe, ShieldAlert, Radio } from 'lucide-react';
import { formatCoordinates, formatTimestamp } from '@/lib/formatters';

interface HeaderProps {
  locationName: string;
  latitude: number;
  longitude: number;
  generatedAt?: string | null;
  isBackendHealthy: boolean;
  streamsOnlineCount?: number;
}

export const Header: React.FC<HeaderProps> = ({
  locationName,
  latitude,
  longitude,
  generatedAt,
  isBackendHealthy,
  streamsOnlineCount = 4,
}) => {
  return (
    <header className="sticky top-0 z-40 w-full bg-[#0a0c12]/90 backdrop-blur-md border-b border-[#1e2638] px-4 py-2.5 flex flex-wrap items-center justify-between gap-3 text-sm">
      {/* Brand & Product Identity */}
      <div className="flex items-center gap-3">
        <div className="flex items-center justify-center w-8 h-8 rounded-md bg-[#0284c7]/20 border border-[#00e5ff]/40 text-[#00e5ff]">
          <Activity className="w-4 h-4 text-[#00e5ff]" />
        </div>
        <div>
          <div className="flex items-center gap-2">
            <span className="font-bold tracking-wider text-base text-white">HydroWatch</span>
            <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#1e2638] text-[#94a3b8] uppercase tracking-widest">
              v2.0 PRO
            </span>
          </div>
          <p className="text-[11px] text-[#64748b] tracking-wide uppercase font-medium">
            Geospatial Environmental & Flood Intelligence
          </p>
        </div>
      </div>

      {/* Target Location & Coordinates */}
      <div className="hidden sm:flex items-center gap-2 px-3 py-1.5 rounded-md bg-[#10141e] border border-[#1e2638] text-xs">
        <Globe className="w-3.5 h-3.5 text-[#00e5ff]" />
        <span className="text-white font-medium">{locationName}</span>
        <span className="text-[#64748b]">·</span>
        <span className="font-mono text-[#94a3b8]">{formatCoordinates(latitude, longitude)}</span>
      </div>

      {/* System Telemetry & Streams Status */}
      <div className="flex items-center gap-4 text-xs">
        {generatedAt && (
          <div className="hidden md:flex flex-col text-right">
            <span className="text-[10px] text-[#64748b] uppercase tracking-wider">Analysis Cycle</span>
            <span className="font-mono text-[#cbd5e1] text-[11px]">{formatTimestamp(generatedAt)}</span>
          </div>
        )}

        <div className="flex items-center gap-2 px-2.5 py-1 rounded bg-[#10141e] border border-[#1e2638]">
          <Radio className={`w-3.5 h-3.5 ${isBackendHealthy ? 'text-[#10b981]' : 'text-[#ef4444]'}`} />
          <span className="text-[#cbd5e1] font-mono text-[11px]">
            {isBackendHealthy ? `${streamsOnlineCount}/4 STREAMS ACTIVE` : 'GATEWAY OFFLINE'}
          </span>
          <span
            className={`w-2 h-2 rounded-full ${
              isBackendHealthy ? 'bg-[#10b981] animate-pulse-subtle' : 'bg-[#ef4444]'
            }`}
          />
        </div>
      </div>
    </header>
  );
};
