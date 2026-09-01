"use client";

import React from "react";
import Link from "next/link";
import { Breadcrumbs } from "./Breadcrumbs";
import { UserDropdown } from "./UserDropdown";
import { Button } from "@/components/ui/button";
import { UploadCloud, GitCompare } from "lucide-react";

export function TopNav() {
  return (
    <header className="flex h-14 w-full items-center justify-between border-b border-zinc-200 bg-white px-5 dark:border-zinc-800 dark:bg-zinc-950 shrink-0">
      {/* Left: Breadcrumb Navigation */}
      <div className="flex items-center gap-3">
        <Breadcrumbs />
      </div>

      {/* Right: Actions */}
      <div className="flex items-center gap-3">
        {/* Quick Compare CTA */}
        <Button
          variant="outline"
          size="sm"
          asChild
          className="hidden sm:inline-flex gap-1.5"
        >
          <Link href="/compare">
            <GitCompare className="h-3.5 w-3.5 text-zinc-500" />
            <span>Compare</span>
          </Link>
        </Button>

        {/* Ingest Action CTA */}
        <Button
          variant="workbench"
          size="sm"
          asChild
          className="gap-1.5 bg-zinc-900 text-white hover:bg-zinc-800"
        >
          <Link href="/papers/upload">
            <UploadCloud className="h-3.5 w-3.5" />
            <span>Upload Paper</span>
          </Link>
        </Button>

        {/* User Profile */}
        <UserDropdown />
      </div>
    </header>
  );
}
