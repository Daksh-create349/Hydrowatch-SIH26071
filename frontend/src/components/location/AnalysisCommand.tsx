'use client';

import React, { useState } from 'react';
import { Play, Settings2, MapPin, ChevronDown, Check, AlertCircle, Loader2 } from 'lucide-react';
import { PRESET_LOCATIONS } from '@/lib/constants';
import { formatCoordinates } from '@/lib/formatters';
import { PresetLocation } from '@/lib/types';

interface AnalysisCommandProps {
  selectedLocation: PresetLocation | null;
  onSelectPreset: (preset: PresetLocation) => void;
  onSelectCustom: (lat: number, lon: number, name: string) => void;
  onRunAnalysis: () => void;
  isLoading: boolean;
  predictionDate: string;
  onChangeDate: (date: string) => void;
  nwpHorizonHours: number;
  onChangeNwpHorizon: (hours: number) => void;
  satelliteMaxCloud: number;
  onChangeSatelliteMaxCloud: (cloud: number) => void;
}

export const AnalysisCommand: React.FC<AnalysisCommandProps> = ({
  selectedLocation,
  onSelectPreset,
  onSelectCustom,
  onRunAnalysis,
  isLoading,
  predictionDate,
  onChangeDate,
  nwpHorizonHours,
  onChangeNwpHorizon,
  satelliteMaxCloud,
  onChangeSatelliteMaxCloud,
}) => {
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const [isCustomMode, setIsCustomMode] = useState(false);
  const [customLat, setCustomLat] = useState('');
  const [customLon, setCustomLon] = useState('');
  const [customName, setCustomName] = useState('');
  const [customError, setCustomError] = useState<string | null>(null);
  const [showSettings, setShowSettings] = useState(false);

  const handleSelectPreset = (preset: PresetLocation) => {
    setIsCustomMode(false);
    setIsDropdownOpen(false);
    setCustomError(null);
    onSelectPreset(preset);
  };

  const handleApplyCustom = (e: React.FormEvent) => {
    e.preventDefault();
    const lat = parseFloat(customLat);
    const lon = parseFloat(customLon);

    if (isNaN(lat) || lat < -90 || lat > 90) {
      setCustomError('Latitude must be a valid number between -90.0 and 90.0');
      return;
    }
    if (isNaN(lon) || lon < -180 || lon > 180) {
      setCustomError('Longitude must be a valid number between -180.0 and 180.0');
      return;
    }

    setCustomError(null);
    setIsDropdownOpen(false);
    onSelectCustom(lat, lon, customName.trim() || `Custom Point (${lat.toFixed(2)}, ${lon.toFixed(2)})`);
  };

  return (
    <div className="relative z-30 bg-[#0c0f17]/95 border border-[#1e2638] rounded-lg p-2.5 shadow-2xl backdrop-blur-md max-w-4xl mx-auto">
      <div className="flex flex-wrap items-center justify-between gap-3">
        {/* Preset Selector Dropdown */}
        <div className="relative flex-1 min-w-[260px]">
          <button
            type="button"
            id="location-selector-button"
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
            className="w-full flex items-center justify-between gap-2 px-3 py-2 rounded-md bg-[#141824] border border-[#2a3449] hover:border-[#00e5ff]/50 text-left transition-colors"
          >
            <div className="flex items-center gap-2 overflow-hidden">
              <MapPin className="w-4 h-4 text-[#00e5ff] shrink-0" />
              <div className="truncate">
                <div className="font-semibold text-white text-xs sm:text-sm truncate">
                  {selectedLocation ? `${selectedLocation.name}, ${selectedLocation.state}` : 'Select Location'}
                </div>
                {selectedLocation && (
                  <div className="font-mono text-[11px] text-[#94a3b8] truncate">
                    {formatCoordinates(selectedLocation.latitude, selectedLocation.longitude)}
                  </div>
                )}
              </div>
            </div>
            <ChevronDown className={`w-4 h-4 text-[#94a3b8] transition-transform ${isDropdownOpen ? 'rotate-180' : ''}`} />
          </button>

          {/* Dropdown Menu */}
          {isDropdownOpen && (
            <div className="absolute top-full left-0 mt-1.5 w-full min-w-[300px] rounded-md bg-[#10141e] border border-[#2a3449] shadow-2xl z-50 p-1.5">
              <div className="text-[10px] font-mono uppercase text-[#64748b] px-2.5 py-1">
                Monitored Metros
              </div>
              {PRESET_LOCATIONS.map((preset) => {
                const isSelected = selectedLocation?.id === preset.id && !isCustomMode;
                return (
                  <button
                    key={preset.id}
                    type="button"
                    onClick={() => handleSelectPreset(preset)}
                    className={`w-full flex items-center justify-between px-2.5 py-2 rounded text-left text-xs transition-colors ${
                      isSelected ? 'bg-[#0284c7]/20 text-[#00e5ff]' : 'hover:bg-[#161b26] text-white'
                    }`}
                  >
                    <div>
                      <div className="font-medium">{preset.name}, {preset.state}</div>
                      <div className="font-mono text-[10px] text-[#64748b]">
                        {formatCoordinates(preset.latitude, preset.longitude)}
                      </div>
                    </div>
                    {isSelected && <Check className="w-4 h-4 text-[#00e5ff]" />}
                  </button>
                );
              })}

              <div className="border-t border-[#1e2638] my-1" />

              <button
                type="button"
                id="custom-coordinates-toggle"
                onClick={() => setIsCustomMode(!isCustomMode)}
                className="w-full flex items-center justify-between px-2.5 py-2 rounded text-left text-xs text-[#cbd5e1] hover:bg-[#161b26]"
              >
                <span>Enter Custom Coordinates</span>
                <span className="font-mono text-[10px] text-[#00e5ff]">WGS84</span>
              </button>

              {isCustomMode && (
                <form onSubmit={handleApplyCustom} className="p-2 space-y-2 bg-[#0a0c12] rounded mt-1 border border-[#1e2638]">
                  {customError && (
                    <div className="flex items-center gap-1.5 text-[11px] text-[#ef4444] bg-[#ef4444]/10 p-1.5 rounded">
                      <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                      <span>{customError}</span>
                    </div>
                  )}
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="text-[10px] font-mono text-[#94a3b8]">LATITUDE (-90 to 90)</label>
                      <input
                        type="number"
                        step="any"
                        placeholder="19.076"
                        value={customLat}
                        onChange={(e) => setCustomLat(e.target.value)}
                        className="w-full bg-[#141824] border border-[#2a3449] rounded px-2 py-1 text-xs text-white font-mono focus:border-[#00e5ff] focus:outline-none"
                        required
                      />
                    </div>
                    <div>
                      <label className="text-[10px] font-mono text-[#94a3b8]">LONGITUDE (-180 to 180)</label>
                      <input
                        type="number"
                        step="any"
                        placeholder="72.877"
                        value={customLon}
                        onChange={(e) => setCustomLon(e.target.value)}
                        className="w-full bg-[#141824] border border-[#2a3449] rounded px-2 py-1 text-xs text-white font-mono focus:border-[#00e5ff] focus:outline-none"
                        required
                      />
                    </div>
                  </div>
                  <div>
                    <label className="text-[10px] font-mono text-[#94a3b8]">LOCATION NAME (OPTIONAL)</label>
                    <input
                      type="text"
                      placeholder="e.g. Mithi River Basin"
                      value={customName}
                      onChange={(e) => setCustomName(e.target.value)}
                      className="w-full bg-[#141824] border border-[#2a3449] rounded px-2 py-1 text-xs text-white focus:border-[#00e5ff] focus:outline-none"
                    />
                  </div>
                  <button
                    type="submit"
                    className="w-full py-1.5 bg-[#0284c7] hover:bg-[#0284c7]/90 text-white font-semibold text-xs rounded transition-colors"
                  >
                    Set Coordinate & Fly Camera
                  </button>
                </form>
              )}
            </div>
          )}
        </div>

        {/* Action Controls */}
        <div className="flex items-center gap-2">
          {/* Analysis Settings Drawer Toggle */}
          <button
            type="button"
            onClick={() => setShowSettings(!showSettings)}
            className={`p-2 rounded-md border text-xs flex items-center gap-1.5 transition-colors ${
              showSettings
                ? 'bg-[#0284c7]/20 border-[#00e5ff]/50 text-[#00e5ff]'
                : 'bg-[#141824] border-[#2a3449] text-[#94a3b8] hover:text-white'
            }`}
            title="Analysis parameters"
          >
            <Settings2 className="w-4 h-4" />
            <span className="hidden sm:inline">Settings</span>
          </button>

          {/* Run Analysis Trigger */}
          <button
            type="button"
            id="run-analysis-button"
            onClick={onRunAnalysis}
            disabled={isLoading || !selectedLocation}
            className="flex items-center gap-2 px-5 py-2 rounded-md bg-[#0284c7] hover:bg-[#0369a1] active:scale-[0.98] disabled:opacity-50 text-white font-semibold text-xs tracking-wider transition-all shadow-lg shadow-[#0284c7]/20"
          >
            {isLoading ? (
              <>
                <Loader2 className="w-4 h-4 animate-spin text-white" />
                <span>SYNTHESIZING...</span>
              </>
            ) : (
              <>
                <Play className="w-4 h-4 fill-white" />
                <span>RUN ANALYSIS</span>
              </>
            )}
          </button>
        </div>
      </div>

      {/* Advanced Settings Drawer */}
      {showSettings && (
        <div className="mt-2.5 pt-2.5 border-t border-[#1e2638] grid grid-cols-1 sm:grid-cols-3 gap-3 text-xs">
          <div>
            <label className="block text-[10px] font-mono text-[#64748b] uppercase mb-1">
              Target Prediction Date
            </label>
            <input
              type="date"
              value={predictionDate}
              onChange={(e) => onChangeDate(e.target.value)}
              className="w-full bg-[#141824] border border-[#2a3449] rounded px-2.5 py-1.5 text-white font-mono focus:border-[#00e5ff] focus:outline-none"
            />
          </div>
          <div>
            <label className="block text-[10px] font-mono text-[#64748b] uppercase mb-1">
              NWP Forecast Window
            </label>
            <select
              value={nwpHorizonHours}
              onChange={(e) => onChangeNwpHorizon(parseInt(e.target.value, 10))}
              className="w-full bg-[#141824] border border-[#2a3449] rounded px-2.5 py-1.5 text-white font-mono focus:border-[#00e5ff] focus:outline-none"
            >
              <option value={12}>12 Hours (Rapid Synoptic)</option>
              <option value={24}>24 Hours (Operational Standard)</option>
              <option value={48}>48 Hours (Extended Outlook)</option>
              <option value={72}>72 Hours (3-Day Horizon)</option>
            </select>
          </div>
          <div>
            <label className="block text-[10px] font-mono text-[#64748b] uppercase mb-1">
              Sentinel-2 Max Cloud Cover ({satelliteMaxCloud}%)
            </label>
            <input
              type="range"
              min="0"
              max="60"
              step="5"
              value={satelliteMaxCloud}
              onChange={(e) => onChangeSatelliteMaxCloud(parseFloat(e.target.value))}
              className="w-full accent-[#0284c7] mt-1.5"
            />
          </div>
        </div>
      )}
    </div>
  );
};
