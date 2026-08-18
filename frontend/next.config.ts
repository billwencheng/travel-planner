import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Allow all dev origins to fix the HMR error
  allowedDevOrigins: [
    "b2607f8b04800100000b60345ac11480a0bb8000000000000000001.proxy.googlers.com", 
    "localhost",
    "127.0.0.1"
  ],
  output: 'export',
  async rewrites() {
    return [
      {
        source: "/api/a2a/:path*",
        destination: "http://127.0.0.1:8000/a2a/:path*", 
      },
      {
        source: "/api/apps/:path*",
        destination: "http://127.0.0.1:8000/apps/:path*",
      },
    ];
  },
};

export default nextConfig;
