'use client';

import React, { useState } from 'react';
import { Terminal, ChevronDown, ChevronUp, Copy, Check, FileJson, ShieldCheck } from 'lucide-react';
import { UnifiedPredictionResponse } from '@/lib/types';

interface AuditPanelProps {
  data?: UnifiedPredictionResponse | null;
}

export const AuditPanel: React.FC<AuditPanelProps> = ({ data }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [copied, setCopied] = useState(false);

  if (!data) return null;

  const handleCopyJson = () => {
    navigator.clipboard.writeText(JSON.stringify(data, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="bg-[#0b0e16] border border-[#1e2638] rounded-lg shadow-xl overflow-hidden text-xs">
      {/* Accordion Toggle Bar */}
      <button
        type="button"
        id="audit-panel-toggle"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-4 py-3 bg-[#101420] hover:bg-[#141928] border-b border-[#1e2638] transition-colors text-left"
      >
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-[#00e5ff]" />
          <span className="font-bold text-white uppercase tracking-wider">
            Technical Provenance & Diagnostic Audit
          </span>
          <span className="text-[10px] font-mono px-1.5 py-0.5 rounded bg-[#1e2638] text-[#94a3b8]">
            Rules {data.provenance?.rules_version || 'v1.0'}
          </span>
        </div>
        <div className="flex items-center gap-2 text-[#94a3b8]">
          <span className="text-[11px] font-mono hidden sm:inline">
            {isOpen ? 'Collapse Diagnostics' : 'Inspect Models, Config & Raw JSON'}
          </span>
          {isOpen ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
        </div>
      </button>

      {/* Expanded Content */}
      {isOpen && (
        <div className="p-4 space-y-4">
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            {/* ML Model Provenance */}
            <div className="bg-[#121622] border border-[#1e2638] p-3 rounded space-y-1.5">
              <div className="text-[10px] font-mono uppercase text-[#64748b] flex items-center gap-1 font-semibold">
                <ShieldCheck className="w-3.5 h-3.5 text-[#00e5ff]" />
                Active Model Versions
              </div>
              <div className="font-mono text-[11px] space-y-1">
                {Object.entries(data.provenance?.model_versions || {}).map(([model, ver]) => (
                  <div key={model} className="flex justify-between border-b border-[#1e2638]/50 pb-0.5">
                    <span className="text-[#94a3b8]">{model}:</span>
                    <span className="text-white truncate max-w-[140px]" title={ver}>
                      {ver}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Configured Thresholds */}
            <div className="bg-[#121622] border border-[#1e2638] p-3 rounded space-y-1.5">
              <div className="text-[10px] font-mono uppercase text-[#64748b] font-semibold">
                Trigger Thresholds
              </div>
              <div className="font-mono text-[11px] space-y-1 max-h-32 overflow-y-auto">
                {Object.entries(data.provenance?.configured_thresholds || {}).map(([key, val]) => (
                  <div key={key} className="flex justify-between border-b border-[#1e2638]/50 pb-0.5">
                    <span className="text-[#94a3b8] truncate max-w-[140px]">{key}:</span>
                    <span className="text-[#00e5ff]">{val}</span>
                  </div>
                ))}
              </div>
            </div>

            {/* Ingestion Timing Breakdown */}
            <div className="bg-[#121622] border border-[#1e2638] p-3 rounded space-y-1.5">
              <div className="text-[10px] font-mono uppercase text-[#64748b] font-semibold">
                Execution Latencies (ms)
              </div>
              <div className="font-mono text-[11px] space-y-1">
                {Object.entries(data.timing || {}).map(([stage, ms]) => (
                  <div key={stage} className="flex justify-between border-b border-[#1e2638]/50 pb-0.5">
                    <span className="text-[#94a3b8]">{stage.replace('_ms', '')}:</span>
                    <span className="text-white">{Math.round(ms)} ms</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Raw JSON Inspection */}
          <div className="space-y-1.5 pt-2">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-1.5 text-[10px] font-mono uppercase text-[#64748b]">
                <FileJson className="w-3.5 h-3.5 text-[#00e5ff]" />
                Raw Backend Payload Response (POST /api/v1/predict)
              </div>
              <button
                type="button"
                onClick={handleCopyJson}
                className="flex items-center gap-1 text-[11px] font-mono text-[#00e5ff] hover:underline"
              >
                {copied ? (
                  <>
                    <Check className="w-3.5 h-3.5 text-[#10b981]" /> Copied to Clipboard
                  </>
                ) : (
                  <>
                    <Copy className="w-3.5 h-3.5" /> Copy JSON Payload
                  </>
                )}
              </button>
            </div>
            <pre className="bg-[#080a10] border border-[#1e2638] rounded p-3 font-mono text-[11px] text-[#cbd5e1] max-h-64 overflow-y-auto leading-relaxed">
              {JSON.stringify(data, null, 2)}
            </pre>
          </div>
        </div>
      )}
    </div>
  );
};
