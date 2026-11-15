/** @type {import('next').NextConfig} */
const nextConfig = {
  // Enable standalone output only for the desktop packaging build so normal
  // web deployment keeps its existing Next.js output behavior.
  ...(process.env.DESKTOP_BUILD === "1" ? { output: "standalone", outputFileTracingRoot: __dirname } : {}),
  reactStrictMode: false,
  images: {
    unoptimized: true,
  },
  transpilePackages: ["react-markdown", "remark-gfm", "remark-math", "rehype-katex"],
  experimental: {
    optimizePackageImports: ["lucide-react", "@tanstack/react-query"],
  },
};

if (process.env.DESKTOP_BUILD === "1") {
  nextConfig.headers = async () => [{
    source: "/:path*",
    headers: [{
      key: "Content-Security-Policy",
      value: "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data: blob:; font-src 'self' data:; connect-src 'self' http://127.0.0.1:*; worker-src 'self' blob:; object-src 'none'; base-uri 'self'; frame-ancestors 'none'; form-action 'self'",
    }, { key: "X-Content-Type-Options", value: "nosniff" }, { key: "Referrer-Policy", value: "no-referrer" }],
  }];
}

module.exports = nextConfig;
