import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  cacheComponents: true,
  /**
   * Retired routes of the earlier two-generation app. Query values in the request are passed through to
   * the destination (e.g. /simulate?gamma=6&run=… keeps both), so old bookmarks keep working.
   */
  async redirects() {
    return [
      { source: "/lab", destination: "/scenarios?section=historical-analytics", permanent: false },
      { source: "/lab/fixed-income", destination: "/fixed-income", permanent: false },
      { source: "/simulate", destination: "/lifecycle-flows?section=simulator", permanent: false },
    ];
  },
  partialPrefetching: true,
  turbopack: {
    rules: {
      "*.css": {
        loaders: ["@tailwindcss/turbopack"],
        as: "*.css",
      },
    },
  },
};

export default nextConfig;
