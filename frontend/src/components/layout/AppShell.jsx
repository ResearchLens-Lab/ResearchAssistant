"use client";

import React from "react";
import { AppSidebar } from "./AppSidebar";
import { TopNav } from "./TopNav";
import { AuthGuard } from "@/components/auth/AuthGuard";

export function AppShell({ children }) {
  return (
    <AuthGuard>
      <div className="flex h-screen w-screen overflow-hidden bg-zinc-50 dark:bg-zinc-950 font-sans">
        <AppSidebar />
        <div className="flex flex-1 flex-col overflow-hidden">
          <TopNav />
          <main className="flex-1 overflow-y-auto bg-zinc-50/50 dark:bg-zinc-950/50">
            {children}
          </main>
        </div>
      </div>
    </AuthGuard>
  );
}
