/** @type {import('next').NextConfig} */
const BACKEND = process.env.HVA_BACKEND || "http://127.0.0.1:8777";

const nextConfig = {
  reactStrictMode: true,
  images: { unoptimized: true },
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${BACKEND}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
