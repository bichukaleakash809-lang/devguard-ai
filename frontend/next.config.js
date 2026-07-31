/** @type {import('next').NextConfig} */
const nextConfig = {
  // Required by frontend/Dockerfile: emits .next/standalone with a self-contained
  // server.js and only the node_modules actually reachable at runtime, which is
  // what keeps the runtime image from needing the full dependency tree.
  output: 'standalone',
};

module.exports = nextConfig;
