/**
 * Formatting helpers for coordinates, timestamps, and physical measurements.
 */

export function formatCoordinates(lat: number, lon: number): string {
  const latStr = `${Math.abs(lat).toFixed(4)}° ${lat >= 0 ? 'N' : 'S'}`;
  const lonStr = `${Math.abs(lon).toFixed(4)}° ${lon >= 0 ? 'E' : 'W'}`;
  return `${latStr} · ${lonStr}`;
}

export function formatTimestamp(isoString?: string | null): string {
  if (!isoString) return 'Unavailable';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      timeZoneName: 'short',
      hour12: false,
    });
  } catch {
    return isoString;
  }
}

export function formatRelativeAge(isoString?: string | null): string {
  if (!isoString) return 'Unknown';
  try {
    const past = new Date(isoString).getTime();
    if (isNaN(past)) return 'Unknown';
    const now = Date.now();
    const diffSec = Math.max(0, Math.floor((now - past) / 1000));
    
    if (diffSec < 60) return `${diffSec}s ago`;
    const diffMin = Math.floor(diffSec / 60);
    if (diffMin < 60) return `${diffMin}m ago`;
    const diffHours = Math.floor(diffMin / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    const diffDays = Math.floor(diffHours / 24);
    return `${diffDays}d ago`;
  } catch {
    return 'Unknown';
  }
}

export function formatNumber(val: unknown, decimals = 2): string {
  if (val === null || val === undefined || typeof val !== 'number') {
    return '—';
  }
  return val.toFixed(decimals);
}
