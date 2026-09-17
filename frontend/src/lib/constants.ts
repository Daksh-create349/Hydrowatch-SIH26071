import { PresetLocation } from './types';

export const PRESET_LOCATIONS: PresetLocation[] = [
  {
    id: 'mumbai',
    name: 'Mumbai',
    state: 'Maharashtra',
    latitude: 19.0760,
    longitude: 72.8777,
    defaultZoomAltitude: 18000,
  },
  {
    id: 'pune',
    name: 'Pune',
    state: 'Maharashtra',
    latitude: 18.5204,
    longitude: 73.8567,
    defaultZoomAltitude: 18000,
  },
  {
    id: 'chennai',
    name: 'Chennai',
    state: 'Tamil Nadu',
    latitude: 13.0827,
    longitude: 80.2707,
    defaultZoomAltitude: 18000,
  },
  {
    id: 'guwahati',
    name: 'Guwahati',
    state: 'Assam',
    latitude: 26.1445,
    longitude: 91.7362,
    defaultZoomAltitude: 20000,
  },
];

export const RADAR_DBZ_THRESHOLDS = [
  { max: 20, label: '< 20 dBZ', description: 'Light / Mist / Clear Air', color: '#10b981' },
  { max: 35, label: '20 - 35 dBZ', description: 'Moderate Rain', color: '#06b6d4' },
  { max: 50, label: '35 - 50 dBZ', description: 'Heavy Rain / Convective', color: '#f59e0b' },
  { max: Infinity, label: '> 50 dBZ', description: 'Severe Rain / Hail Core', color: '#ef4444' },
];

export const RISK_LEVEL_CONFIG = {
  LOW: {
    label: 'LOW RISK',
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.12)',
    borderColor: 'rgba(16, 185, 129, 0.35)',
    description: 'Environmental indicators below critical flood thresholds.',
  },
  MODERATE: {
    label: 'MODERATE RISK',
    color: '#06b6d4',
    bgColor: 'rgba(6, 182, 212, 0.12)',
    borderColor: 'rgba(6, 182, 212, 0.35)',
    description: 'Elevated precipitation or saturation detected. Active monitoring advised.',
  },
  HIGH: {
    label: 'HIGH RISK',
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.12)',
    borderColor: 'rgba(245, 158, 11, 0.35)',
    description: 'Convective signatures and significant accumulation forecast. High flood potential.',
  },
  EXTREME: {
    label: 'EXTREME RISK',
    color: '#ef4444',
    bgColor: 'rgba(239, 68, 68, 0.12)',
    borderColor: 'rgba(239, 68, 68, 0.35)',
    description: 'Critical inundation and severe storm triggers active. Urgent readiness recommended.',
  },
};

export const WARNING_STATUS_CONFIG = {
  NO_ALERT: {
    label: 'NO ALERT',
    color: '#10b981',
    bgColor: 'rgba(16, 185, 129, 0.15)',
    borderColor: '#10b981',
  },
  MONITOR: {
    label: 'MONITOR',
    color: '#06b6d4',
    bgColor: 'rgba(6, 182, 212, 0.15)',
    borderColor: '#06b6d4',
  },
  PREPARE: {
    label: 'PREPARE',
    color: '#f59e0b',
    bgColor: 'rgba(245, 158, 11, 0.15)',
    borderColor: '#f59e0b',
  },
  ACTION: {
    label: 'ACTION',
    color: '#ef4444',
    bgColor: 'rgba(239, 68, 68, 0.15)',
    borderColor: '#ef4444',
  },
  INSUFFICIENT_DATA: {
    label: 'INSUFFICIENT DATA',
    color: '#94a3b8',
    bgColor: 'rgba(148, 163, 184, 0.15)',
    borderColor: '#94a3b8',
  },
};
