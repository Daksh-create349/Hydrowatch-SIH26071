'use client';

import React from 'react';
import { AlertTriangle, Clock, ShieldCheck, ChevronRight, Info } from 'lucide-react';
import { WarningDecision } from '@/lib/types';
import { WARNING_STATUS_CONFIG } from '@/lib/constants';
import { formatNumber, formatTimestamp } from '@/lib/formatters';

interface WarningPanelProps {
  warning?: WarningDecision | null;
}

export const WarningPanel: React.FC<WarningPanelProps> = ({ warning }) => {
  if (!warning) {
    return (
      <div className="bg-[#0b0e16] border border-[#1e2638] rounded-lg p-4 text-center">
        <p className="text-xs text-[#64748b] font-mono uppercase tracking-wider">
          Awaiting analysis execution for prototype early warning assessment.
        </p>
      </div>
    );
  }

  const statusConfig = WARNING_STATUS_CONFIG[warning.status] || WARNING_STATUS_CONFIG.NO_ALERT;

  return (
    <div className="bg-[#0b0e16] border border-[#1e2638] rounded-lg p-4 shadow-xl space-y-4">
      {/* Header & Mandatory Prototype Notice */}
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#1e2638] pb-3">
        <div className="flex items-center gap-2.5">
          <div
            className="w-3.5 h-3.5 rounded-full"
            style={{ backgroundColor: statusConfig.color }}
          />
          <div>
            <h2 className="text-sm font-bold text-white tracking-wider flex items-center gap-2 uppercase">
              Prototype Warning Assessment
              <span
                className="text-[10px] px-2 py-0.5 rounded font-mono font-semibold"
                style={{
                  color: statusConfig.color,
                  backgroundColor: statusConfig.bgColor,
                  border: `1px solid ${statusConfig.borderColor}60`,
                }}
              >
                {statusConfig.label}
              </span>
            </h2>
            <p className="text-[11px] font-mono text-[#f59e0b] tracking-wider mt-0.5">
              PROTOTYPE ASSESSMENT · NOT AN OFFICIAL IMD WARNING
            </p>
          </div>
        </div>

        {/* Validity Window */}
        {warning.valid_until && (
          <div className="flex items-center gap-1.5 text-xs text-[#94a3b8] font-mono bg-[#141824] px-2.5 py-1 rounded border border-[#1e2638]">
            <Clock className="w-3.5 h-3.5 text-[#00e5ff]" />
            <span>Valid Until: {formatTimestamp(warning.valid_until)}</span>
          </div>
        )}
      </div>

      {/* Primary Trigger Reasons */}
      {warning.trigger_reasons && warning.trigger_reasons.length > 0 && (
        <div className="space-y-1.5">
          <div className="text-[11px] font-mono uppercase tracking-wider text-[#64748b]">
            Trigger Criteria & Synoptic Drivers
          </div>
          <ul className="space-y-1">
            {warning.trigger_reasons.map((reason, idx) => (
              <li key={idx} className="text-xs text-[#cbd5e1] flex items-start gap-2 bg-[#121622] p-2 rounded border border-[#1e2638]">
                <ChevronRight className="w-3.5 h-3.5 text-[#00e5ff] shrink-0 mt-0.5" />
                <span>{reason}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Concrete Physical Triggers Matrix */}
      {warning.triggers && warning.triggers.length > 0 && (
        <div className="space-y-2">
          <div className="text-[11px] font-mono uppercase tracking-wider text-[#64748b]">
            Multi-Source Physical Trigger Evaluation
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-2">
            {warning.triggers.map((trigger, idx) => {
              return (
                <div
                  key={idx}
                  className={`p-2.5 rounded border text-xs space-y-1 ${
                    trigger.triggered
                      ? 'bg-[#ef4444]/10 border-[#ef4444]/40'
                      : 'bg-[#121622] border-[#1e2638]'
                  }`}
                >
                  <div className="flex items-center justify-between text-[10px] font-mono uppercase">
                    <span className="text-[#94a3b8] truncate">{trigger.source.replace('_', ' ')}</span>
                    <span
                      className={`font-bold px-1 rounded ${
                        trigger.triggered ? 'text-[#ef4444] bg-[#ef4444]/20' : 'text-[#10b981]'
                      }`}
                    >
                      {trigger.triggered ? 'TRIGGERED' : 'NORMAL'}
                    </span>
                  </div>
                  <div className="font-semibold text-white truncate">{trigger.metric}</div>
                  <div className="flex items-baseline justify-between font-mono text-[11px]">
                    <span className="text-white">
                      {typeof trigger.observed_value === 'number'
                        ? formatNumber(trigger.observed_value, 2)
                        : String(trigger.observed_value)}{' '}
                      <span className="text-[#64748b]">{trigger.unit}</span>
                    </span>
                    <span className="text-[#64748b]">
                      Limit: {trigger.threshold} {trigger.unit}
                    </span>
                  </div>
                  <p className="text-[10px] text-[#94a3b8] line-clamp-2 pt-0.5">{trigger.description}</p>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* Escalation Notes / Validity Rationale */}
      {warning.escalation_notes && (
        <div className="flex items-start gap-2 bg-[#f59e0b]/10 border border-[#f59e0b]/30 p-2.5 rounded text-xs text-[#fcd34d]">
          <AlertTriangle className="w-4 h-4 shrink-0 mt-0.5 text-[#f59e0b]" />
          <div>
            <span className="font-semibold uppercase tracking-wider text-[10px] block">
              Physical Burst / Escalation Note
            </span>
            <span>{warning.escalation_notes}</span>
          </div>
        </div>
      )}

      {/* Legal & Operational Disclaimer Bar */}
      <div className="flex items-start gap-2 bg-[#121622] border border-[#1e2638] p-2 rounded text-[11px] text-[#64748b]">
        <Info className="w-3.5 h-3.5 shrink-0 mt-0.5 text-[#94a3b8]" />
        <div>
          <span>{warning.disclaimer}</span>
        </div>
      </div>
    </div>
  );
};
