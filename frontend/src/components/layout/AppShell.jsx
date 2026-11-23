"use client";

import React, { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  FlaskConical,
  GitCompareArrows,
  UploadCloud,
  Settings,
} from "lucide-react";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { ResearchLensLogo } from "@/components/brand/ResearchLensLogo";
import { UserDropdown } from "./UserDropdown";
import { CommandPalette } from "./CommandPalette";
import { AddSourcesModal } from "@/components/upload/AddSourcesModal";
import { usePapers } from "@/hooks/usePapers";
import { useCitationStore } from "@/store/citationStore";
import { cn } from "@/utils/cn";

function AppShellContent({ children }) {
  const pathname = usePathname();
  const { closeDrawer } = useCitationStore();
  const [addSourcesOpen, setAddSourcesOpen] = useState(false);
  const [paletteOpen, setPaletteOpen] = useState(false);
  const { papers = [] } = usePapers(1, 50);

  useEffect(() => {
    if (pathname && !pathname.startsWith("/chat")) {
      closeDrawer();
    }
  }, [pathname, closeDrawer]);

  // Status bar state
  const [externalLookups, setExternalLookups] = useState(false);
  const [engineType, setEngineType] = useState(null);
  const [appVersion, setAppVersion] = useState("v0.1.0-alpha.2");

  useEffect(() => {
    const updateDiagnostics = async () => {
      if (typeof window === "undefined") return;
      const bridge = window.researchLensDesktop;
      if (!bridge) return;

      try {
        if (bridge.getExternalLookups) {
          const lookups = await bridge.getExternalLookups();
          setExternalLookups(Boolean(lookups));
        }
      } catch {}

      try {
        if (bridge.getDiagnostics) {
          const diag = await bridge.getDiagnostics();
          if (diag?.localIntelligence?.engine) {
            setEngineType(diag.localIntelligence.engine);
          }
          if (diag?.appVersion) {
            setAppVersion(diag.appVersion.startsWith("v") ? diag.appVersion : `v${diag.appVersion}`);
          }
        }
      } catch {}
    };

    updateDiagnostics();
    const interval = setInterval(updateDiagnostics, 30000);
    const handleOpenSources = () => setAddSourcesOpen(true);
    window.addEventListener("researchlens:open-add-sources", handleOpenSources);
    return () => {
      clearInterval(interval);
      window.removeEventListener("researchlens:open-add-sources", handleOpenSources);
    };
  }, []);

  const navItems = [
    {
      label: "Library",
      href: "/papers",
      icon: BookOpen,
      isActive: pathname.startsWith("/papers") || pathname === "/dashboard",
    },
    {
      label: "Research Desk",
      href: "/chat",
      icon: FlaskConical,
      isActive: pathname.startsWith("/chat"),
    },
    {
      label: "Compare & Reports",
      href: "/compare",
      icon: GitCompareArrows,
      isActive: pathname.startsWith("/compare"),
    },
  ];

  return (
    <div className="flex h-dvh w-full flex-col overflow-hidden bg-[var(--rl-canvas)] select-none">
        {/* B2: 40px Drag Strip Row */}
        <header
          style={{ WebkitAppRegion: "drag", paddingRight: "140px" }}
          className="flex h-10 w-full shrink-0 items-center justify-between border-b border-slate-200/70 bg-white/95 px-3 select-none backdrop-blur-sm z-30"
          aria-label="Application title bar"
        >
          <div
            style={{ WebkitAppRegion: "no-drag" }}
            className="flex items-center gap-2"
          >
            <span className="flex h-6 w-6 items-center justify-center rounded-md bg-sky-50 text-[var(--rl-primary)]">
              <ResearchLensLogo className="h-4 w-4" />
            </span>
            <span className="text-xs font-semibold tracking-tight text-slate-800">
              ResearchLens
            </span>
          </div>
          <div
            style={{ WebkitAppRegion: "no-drag" }}
            className="hidden sm:flex items-center gap-2 text-[11px] text-slate-400"
          >
            <kbd className="rounded border border-slate-200 bg-slate-50 px-1.5 py-0.5 font-mono text-[10px]">
              Ctrl+K
            </kbd>
            <span>Command palette</span>
          </div>
        </header>

        {/* Center Workspace: Left Icon Rail + Content */}
        <div className="flex min-h-0 flex-1 overflow-hidden">
          {/* C1: 64px Left Icon Rail */}
          <aside
            aria-label="Primary navigation rail"
            className="flex w-16 shrink-0 flex-col items-center justify-between border-r border-slate-200/80 bg-white py-3 z-20"
          >
            {/* Top Navigation Destinations */}
            <nav className="flex flex-col items-center gap-2 w-full px-2" aria-label="Main destinations">
              {navItems.map(({ label, href, icon: Icon, isActive }) => (
                <Link
                  key={href}
                  href={href}
                  title={label}
                  aria-label={label}
                  aria-current={isActive ? "page" : undefined}
                  className={cn(
                    "relative flex h-10 w-10 items-center justify-center rounded-xl transition-all outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
                    isActive
                      ? "bg-sky-50 text-[#1d6fc4] font-semibold shadow-2xs"
                      : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                  )}
                >
                  <Icon className="h-5 w-5" />
                  {isActive && (
                    <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-[#1d6fc4]" />
                  )}
                </Link>
              ))}
            </nav>

            {/* Bottom Utility Controls */}
            <div className="flex flex-col items-center gap-3 w-full px-2">
              <button
                type="button"
                onClick={() => setAddSourcesOpen(true)}
                title="Add sources"
                aria-label="Add sources"
                className="flex h-10 w-10 items-center justify-center rounded-xl bg-sky-50 text-[#1d6fc4] transition-all hover:bg-sky-100 outline-none focus-visible:ring-2 focus-visible:ring-sky-500 cursor-pointer"
              >
                <UploadCloud className="h-5 w-5" />
              </button>

              <Link
                href="/settings"
                title="Settings"
                aria-label="Settings"
                aria-current={pathname === "/settings" ? "page" : undefined}
                className={cn(
                  "relative flex h-10 w-10 items-center justify-center rounded-xl transition-all outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
                  pathname === "/settings"
                    ? "bg-sky-50 text-[#1d6fc4] shadow-2xs"
                    : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                )}
              >
                <Settings className="h-5 w-5" />
                {pathname === "/settings" && (
                  <span className="absolute left-0 top-2 bottom-2 w-1 rounded-r-full bg-[#1d6fc4]" />
                )}
              </Link>

              <div className="pt-1 border-t border-slate-100 w-full flex justify-center">
                <UserDropdown />
              </div>
            </div>
          </aside>

          {/* Main Content Area */}
          <main
            className="min-h-0 flex-1 overflow-y-auto bg-[var(--rl-canvas)]"
            id="main-content"
          >
            {children}
          </main>
        </div>

        {/* C1: 24px Bottom Status Bar */}
        <footer
          className="flex h-6 w-full shrink-0 items-center justify-between border-t border-slate-200/80 bg-slate-50/90 px-3 text-[11px] text-slate-500 select-none z-20"
          aria-label="Status bar"
        >
          <div className="flex items-center gap-2">
            <span
              className={cn(
                "h-1.5 w-1.5 rounded-full",
                externalLookups ? "bg-emerald-500" : "bg-slate-400"
              )}
            />
            <span>{externalLookups ? "Online verification on" : "Offline"}</span>
          </div>

          <div className="font-mono text-[10px] text-slate-400">
            {appVersion}
          </div>
        </footer>

        {/* Global Modals */}
        <CommandPalette
          isOpen={paletteOpen}
          onOpenChange={setPaletteOpen}
          onOpenAddSources={() => setAddSourcesOpen(true)}
        />
        <AddSourcesModal
          isOpen={addSourcesOpen}
          onClose={() => setAddSourcesOpen(false)}
          papers={papers}
        />
      </div>
  );
}

export function AppShell({ children }) {
  return (
    <AuthGuard>
      <AppShellContent>{children}</AppShellContent>
    </AuthGuard>
  );
}
