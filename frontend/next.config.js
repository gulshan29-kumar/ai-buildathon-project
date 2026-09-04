/** @type {import('next').NextConfig} */
const rawBackendUrl =
  process.env.BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_BACKEND_API_URL ||
  process.env.NEXT_PUBLIC_API_URL;

let apiDestination = 'http://127.0.0.1:8000/api/:path*';

if (rawBackendUrl) {
  const cleanUrl = rawBackendUrl.replace(/\/+$/, '');
  apiDestination = cleanUrl.endsWith('/api') ? `${cleanUrl}/:path*` : `${cleanUrl}/api/:path*`;
}

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: apiDestination,
      },
    ];
  },
};

module.exports = nextConfig;

