"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { Check, X } from "lucide-react";

export function AuthSuccessToast() {
  const pathname = usePathname();
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (pathname === "/login") return;
    try {
      if (sessionStorage.getItem("researchlens.auth.success") === "1") {
        sessionStorage.removeItem("researchlens.auth.success");
        setVisible(true);
      }
    } catch { /* Storage may be disabled; authentication still succeeds. */ }
  }, [pathname]);

  useEffect(() => {
    if (!visible) return undefined;
    const timer = window.setTimeout(() => setVisible(false), 3600);
    return () => window.clearTimeout(timer);
  }, [visible]);

  if (!visible) return null;
  return <div role="status" aria-live="polite" className="fixed right-4 top-4 z-[100] flex max-w-[calc(100vw-2rem)] items-center gap-3 rounded-xl border border-[#c8deef] bg-white px-4 py-3 text-sm font-medium text-[var(--rl-ink)] shadow-[0_12px_36px_-16px_rgba(38,120,184,0.4)] motion-safe:animate-in motion-safe:fade-in motion-safe:slide-in-from-top-2">
    <span className="flex h-7 w-7 items-center justify-center rounded-full bg-[var(--rl-selected)] text-[var(--rl-primary)]"><Check className="h-4 w-4" aria-hidden="true" /></span>
    <span>Signed in successfully — welcome back.</span>
    <button type="button" className="ml-1 rounded-md p-1 text-[var(--rl-muted)] hover:bg-[var(--rl-tint)]" aria-label="Dismiss notification" onClick={() => setVisible(false)}><X className="h-4 w-4" aria-hidden="true" /></button>
  </div>;
}
