import type { Metadata, Viewport } from 'next';
import './globals.css';

export const metadata: Metadata = {
  title: 'HydroWatch — Geospatial Environmental & Flood Intelligence',
  description:
    'Commercial-grade multi-source flood risk assessment and early warning platform synthesizing observational weather, NOAA GFS NWP, RainViewer Doppler radar, and Sentinel-2 FloodUNet inundation analytics.',
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  maximumScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <head>
        <link rel="stylesheet" href="/cesium/Widgets/widgets.css" />
      </head>
      <body className="bg-[#08090c] text-[#f1f5f9] min-h-screen selection:bg-[#0284c7]/30 selection:text-[#00e5ff]">
        {children}
      </body>
    </html>
  );
}
