import "katex/dist/katex.min.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
  title: "ResearchLens — AI Research Assistant",
  description:
    "AI-powered research intelligence platform for paper understanding, grounded RAG Q&A, and citation analysis.",
  icons: {
    icon: "/favicon.ico",
  },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="h-full" suppressHydrationWarning>
      <body
        className="h-full bg-zinc-50 text-zinc-900 antialiased selection:bg-indigo-100 selection:text-indigo-900"
        suppressHydrationWarning
      >
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
