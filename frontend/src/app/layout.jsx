import "katex/dist/katex.min.css";
import "./globals.css";
import { Providers } from "./providers";

export const metadata = {
  title: "ResearchLens — Evidence-First Research",
  description:
    "Research workspace for grounded questions, source inspection, and cross-paper comparison.",
  icons: { icon: "/favicon.ico" },
};

export default function RootLayout({ children }) {
  return (
    <html lang="en" className="h-full" suppressHydrationWarning>
      <body className="h-full bg-background text-foreground antialiased" suppressHydrationWarning>
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
