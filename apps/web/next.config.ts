import type { NextConfig } from "next";
const apiBaseUrl = process.env.ZAOJING_API_URL ?? "http://127.0.0.1:8010";
const config: NextConfig = {
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${apiBaseUrl}/api/:path*`,
      },
    ];
  },
};
export default config;
