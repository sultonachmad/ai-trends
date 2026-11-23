import type { NextConfig } from "next";

// A pay or guest-booking link's token is its credential: the page must not be cached, must not hand
// its address to other sites as a referrer, and must stay out of search indexes.
const TOKEN_PAGE_HEADERS = [
  { key: "Cache-Control", value: "no-store" },
  { key: "Referrer-Policy", value: "no-referrer" },
  { key: "X-Robots-Tag", value: "noindex, nofollow" },
];

const nextConfig: NextConfig = {
  basePath: process.env.NEXT_PUBLIC_BASE_PATH || '',
  async headers() {
    return [
      { source: "/pay/:token*", headers: TOKEN_PAGE_HEADERS },
      { source: "/booking/:token*", headers: TOKEN_PAGE_HEADERS },
    ];
  },
};

export default nextConfig;
