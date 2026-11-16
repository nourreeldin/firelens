/** @type {import('next').NextConfig} */
const nextConfig = {
  // Keep metadata in <head>. Extension DOM injection is handled separately
  // in instrumentation-client.ts; this option alone cannot prevent it.
  devIndicators: false,
  htmlLimitedBots: /.*/,
  images: {
    unoptimized: true,
  },
}

export default nextConfig
