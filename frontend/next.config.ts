import type { NextConfig } from 'next';

const nextConfig: NextConfig = {
  turbopack: {},
  webpack(config) {
    config.externals = config.externals || [];
    config.resolve = config.resolve || {};
    config.resolve.fallback = {
      ...config.resolve.fallback,
      fs: false,
      http: false,
      https: false,
      zlib: false,
      url: false,
    };
    return config;
  },
};

export default nextConfig;
