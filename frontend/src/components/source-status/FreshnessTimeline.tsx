'use client';

import React from 'react';
import { Clock, CheckCircle2, XCircle, AlertCircle } from 'lucide-react';
import { SourceStatusDetail, UnifiedTimingDetail } from '@/lib/types';
import { formatRelativeAge, formatTimestamp } from '@/lib/formatters';

interface FreshnessTimelineProps {
  sourceStatus?: Record<string, SourceStatusDetail> | null;
  timing?: UnifiedTimingDetail | null;
}

export const FreshnessTimeline: React.FC<FreshnessTimelineProps> = ({
  sourceStatus,
  timing,
}) => {
  if (!sourceStatus) return null;

  const sources = [
    {
      key: 'radar',
      name: 'Doppler Weather Radar',
      role: 'LIVE OBSERVATION',
      provider: 'Doppler Radar Network',
    },
    {
      key: 'nwp',
      name: 'Numerical Weather Prediction',
      role: 'FORECAST (GFS)',
      provider: 'NOAA 0.25° Seamless',
    },
    {
      key: 'weather_model1',
      name: 'Surface Weather Observation',
      role: 'OBSERVATION (D-1)',
      provider: 'NASA POWER Daily API',
    },
    {
      key: 'satellite_model2',
      name: 'Sentinel-2 L2A Multispectral',
      role: 'HISTORICAL BASELINE',
      provider: 'Element 84 Earth Search',
    },
  ];

  return (
    <div className="bg-[#0b0e16] border border-[#1e2638] rounded-lg p-4 shadow-xl space-y-3">
      <div className="flex items-center justify-between border-b border-[#1e2638] pb-2.5">
        <div className="flex items-center gap-2">
          <Clock className="w-4 h-4 text-[#00e5ff]" />
          <h3 className="text-xs font-bold text-white uppercase tracking-wider">
            Telemetry Currency & Pipeline Health
          </h3>
        </div>
        {timing && (
          <span className="font-mono text-[11px] text-[#94a3b8]">
            Total Ingestion Latency: <span className="text-[#00e5ff] font-bold">{Math.round(timing.total_ms)}ms</span>
          </span>
        )}
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2.5">
        {sources.map((src) => {
          const detail = sourceStatus[src.key];
          const isSuccess = detail?.status === 'success';
          const isFailed = detail?.status === 'failed';

          return (
            <div
              key={src.key}
              className={`p-3 rounded-lg border text-xs space-y-1.5 ${
                isSuccess
                  ? 'bg-[#121624] border-[#1e2638]'
                  : isFailed
                  ? 'bg-[#ef4444]/10 border-[#ef4444]/40'
                  : 'bg-[#121624]/60 border-[#1e2638]'
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#1e2638] text-[#00e5ff] font-semibold uppercase">
                  {src.role}
                </span>
                {isSuccess ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#10b981]" />
                ) : isFailed ? (
                  <XCircle className="w-3.5 h-3.5 text-[#ef4444]" />
                ) : (
                  <AlertCircle className="w-3.5 h-3.5 text-[#94a3b8]" />
                )}
              </div>

              <div>
                <div className="font-semibold text-white truncate">{src.name}</div>
                <div className="text-[10px] text-[#64748b]">{detail?.source || src.provider}</div>
              </div>

              <div className="pt-1 border-t border-[#1e2638]/60 flex items-center justify-between text-[10px] font-mono">
                <span className="text-[#94a3b8]">
                  {detail?.timestamp ? formatRelativeAge(detail.timestamp) : 'No Timestamp'}
                </span>
                <span className="text-[#64748b]">
                  {detail?.latency_ms !== undefined ? `${Math.round(detail.latency_ms)}ms` : '—'}
                </span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
