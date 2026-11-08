/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: false,
  images: {
    unoptimized: true,
  },
  transpilePackages: ["react-markdown", "remark-gfm", "remark-math", "rehype-katex"],
  experimental: {
    optimizePackageImports: ["lucide-react", "@tanstack/react-query"],
  },
};

module.exports = nextConfig;
