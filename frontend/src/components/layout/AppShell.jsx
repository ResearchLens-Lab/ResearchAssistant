"use client";

import React from "react";
import { TopNav } from "./TopNav";
import { AuthGuard } from "@/components/auth/AuthGuard";

export function AppShell({ children }) {
  return (
    <AuthGuard>
      <div className="flex h-dvh w-full flex-col overflow-hidden bg-[var(--rl-canvas)]">
        <TopNav />
        <main className="min-h-0 flex-1 overflow-y-auto bg-[var(--rl-canvas)]" id="main-content">
          {children}
        </main>
      </div>
    </AuthGuard>
  );
}
