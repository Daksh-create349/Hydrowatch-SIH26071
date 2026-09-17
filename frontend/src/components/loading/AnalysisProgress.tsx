'use client';

import React from 'react';
import { Loader2, CheckCircle2, Clock, Globe } from 'lucide-react';

interface AnalysisProgressProps {
  locationName: string;
  stagesCompleted?: number; // 0 to 7
}

export const AnalysisProgress: React.FC<AnalysisProgressProps> = ({
  locationName,
  stagesCompleted = 1,
}) => {
  const stages = [
    { id: 'weather', label: 'Weather observation', source: 'NASA POWER Daily Point API' },
    { id: 'rainfall', label: 'Rainfall model', source: 'Model 1 XGBoost inference' },
    { id: 'nwp', label: 'NWP forecast', source: 'Open-Meteo NOAA GFS 0.25°' },
    { id: 'radar', label: 'Radar observation', source: 'Doppler Radar Composite' },
    { id: 'satellite', label: 'Satellite analysis', source: 'Sentinel-2 L2A & Model 2 FloodUNet' },
    { id: 'fusion', label: 'Risk synthesis', source: 'Deterministic multi-source fusion' },
    { id: 'warning', label: 'Warning assessment', source: 'Operational state machine evaluation' },
  ];

  return (
    <div className="bg-[#0b0e16]/95 border border-[#00e5ff]/30 rounded-lg p-5 shadow-2xl backdrop-blur-md max-w-lg mx-auto space-y-4">
      <div className="flex items-center justify-between border-b border-[#1e2638] pb-3">
        <div className="flex items-center gap-2">
          <Globe className="w-4 h-4 text-[#00e5ff]" />
          <h3 className="font-bold text-white text-xs uppercase tracking-widest">
            ANALYSING LOCATION: {locationName}
          </h3>
        </div>
        <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#0284c7]/20 text-[#00e5ff] font-semibold">
          PIPELINE ACTIVE
        </span>
      </div>

      <div className="space-y-2 font-mono text-xs">
        {stages.map((stage, idx) => {
          const isDone = idx < stagesCompleted;
          const isCurrent = idx === stagesCompleted;

          return (
            <div
              key={stage.id}
              className={`flex items-center justify-between p-2 rounded transition-colors ${
                isCurrent
                  ? 'bg-[#141824] border border-[#00e5ff]/30 text-white'
                  : isDone
                  ? 'text-[#cbd5e1]'
                  : 'text-[#64748b]'
              }`}
            >
              <div className="flex items-center gap-2">
                {isDone ? (
                  <CheckCircle2 className="w-3.5 h-3.5 text-[#10b981] shrink-0" />
                ) : isCurrent ? (
                  <Loader2 className="w-3.5 h-3.5 text-[#00e5ff] animate-spin shrink-0" />
                ) : (
                  <Clock className="w-3.5 h-3.5 text-[#64748b] shrink-0" />
                )}
                <span className={isCurrent ? 'font-semibold text-[#00e5ff]' : ''}>
                  {stage.label}
                </span>
              </div>
              <span className="text-[10px] text-[#64748b] truncate max-w-[170px]">
                {stage.source}
              </span>
            </div>
          );
        })}
      </div>

      <div className="pt-2 border-t border-[#1e2638] text-[10px] text-[#94a3b8] font-mono text-center">
        Multispectral Sentinel-2 COG alignment & windowed FloodUNet inference in progress.
      </div>
    </div>
  );
};
