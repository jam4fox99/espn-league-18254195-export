import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  typedRoutes: true,
  turbopack: {
    root: process.cwd()
  },
  // ESPN-hosted logos + headshots are served remotely (CDN-cached/optimized by
  // next/image). The ~20 rot-prone CUSTOM_VALID external logos are baked into
  // /public/logos instead (see scripts/bake_logos.py) so they can't rot.
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "a.espncdn.com" },
      { protocol: "https", hostname: "g.espncdn.com" },
      { protocol: "https", hostname: "*.fantasy.espn.com" }
    ]
  },
  typescript: {
    ignoreBuildErrors: false,
    tsconfigPath: "tsconfig.json"
  }
};

export default nextConfig;
