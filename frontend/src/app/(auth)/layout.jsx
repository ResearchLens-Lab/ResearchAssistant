import React from "react";

export default function AuthLayout({ children }) {
  return (
    <div className="flex min-h-screen w-full items-center justify-center bg-zinc-50 p-4 dark:bg-zinc-950">
      {children}
    </div>
  );
}
