"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ChevronRight, Home } from "lucide-react";

export function Breadcrumbs() {
  const pathname = usePathname();
  const segments = pathname.split("/").filter(Boolean);

  if (segments.length === 0) return null;

  return (
    <nav className="flex items-center space-x-1.5 text-xs text-zinc-500 font-medium select-none">
      <Link
        href="/dashboard"
        className="flex items-center text-zinc-600 hover:text-zinc-900 transition-colors"
      >
        <Home className="h-3.5 w-3.5" />
      </Link>

      {segments.map((segment, index) => {
        const href = `/${segments.slice(0, index + 1).join("/")}`;
        const isLast = index === segments.length - 1;
        const formattedName =
          segment.charAt(0).toUpperCase() + segment.slice(1).replace(/-/g, " ");

        return (
          <React.Fragment key={href}>
            <ChevronRight className="h-3.5 w-3.5 text-zinc-400 shrink-0" />
            {isLast ? (
              <span className="font-semibold text-zinc-900 truncate max-w-[200px] dark:text-zinc-100">
                {formattedName}
              </span>
            ) : (
              <Link
                href={href}
                className="text-zinc-500 hover:text-zinc-900 transition-colors truncate max-w-[150px]"
              >
                {formattedName}
              </Link>
            )}
          </React.Fragment>
        );
      })}
    </nav>
  );
}
