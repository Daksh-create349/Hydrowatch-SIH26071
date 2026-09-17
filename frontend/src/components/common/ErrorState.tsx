'use client';

import React from 'react';
import { AlertCircle, RotateCcw, ChevronDown, ChevronUp } from 'lucide-react';

interface ErrorStateProps {
  title?: string;
  message: string;
  details?: string;
  onRetry?: () => void;
}

export const ErrorState: React.FC<ErrorStateProps> = ({
  title = 'Analysis Ingestion Failure',
  message,
  details,
  onRetry,
}) => {
  const [showDetails, setShowDetails] = React.useState(false);

  return (
    <div className="bg-[#120f14] border border-[#ef4444]/40 rounded-lg p-5 shadow-2xl max-w-lg mx-auto text-center space-y-3">
      <div className="flex justify-center">
        <div className="p-3 bg-[#ef4444]/10 rounded-full border border-[#ef4444]/30">
          <AlertCircle className="w-8 h-8 text-[#ef4444]" />
        </div>
      </div>
      <div>
        <h3 className="font-bold text-white text-sm uppercase tracking-wide">{title}</h3>
        <p className="text-xs text-[#cbd5e1] mt-1 max-w-md mx-auto">{message}</p>
      </div>

      {details && (
        <div className="text-left">
          <button
            type="button"
            onClick={() => setShowDetails(!showDetails)}
            className="text-[10px] font-mono text-[#94a3b8] hover:text-white flex items-center gap-1 mx-auto"
          >
            <span>{showDetails ? 'Hide Diagnostics' : 'Show Diagnostics'}</span>
            {showDetails ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
          </button>
          {showDetails && (
            <pre className="mt-2 bg-[#0a0a0f] border border-[#2a1a1f] p-2 rounded text-[10px] font-mono text-[#ef4444] overflow-x-auto">
              {details}
            </pre>
          )}
        </div>
      )}

      {onRetry && (
        <div className="pt-2">
          <button
            type="button"
            onClick={onRetry}
            className="inline-flex items-center gap-1.5 px-4 py-2 rounded bg-[#0284c7] hover:bg-[#0369a1] text-white text-xs font-semibold tracking-wider transition-colors shadow-lg"
          >
            <RotateCcw className="w-3.5 h-3.5" />
            <span>RETRY ANALYSIS</span>
          </button>
        </div>
      )}
    </div>
  );
};
