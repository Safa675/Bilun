import type { NextConfig } from "next";
import path from "node:path";

const backendOrigin = (process.env.API_PROXY_TARGET ?? "http://localhost:8001").replace(/\/$/, "");

// Bilun repo root (frontend/..) — not Documents/ (frontend/../..)
const REPO_ROOT = path.resolve(__dirname, "..");

const nextConfig: NextConfig = {
  devIndicators: false,
  output: "standalone",
  outputFileTracingRoot: REPO_ROOT,
  turbopack: {
    root: REPO_ROOT,
    resolveAlias: {},
  },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${backendOrigin}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
