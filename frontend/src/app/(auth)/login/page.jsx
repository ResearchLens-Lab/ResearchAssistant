"use client";

import React, { Suspense } from "react";
import { LoginForm } from "@/components/auth/LoginForm";

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex h-64 w-full max-w-md items-center justify-center rounded-xl bg-white border border-zinc-200">
          <div className="h-6 w-6 animate-spin rounded-full border-2 border-zinc-900 border-t-transparent" />
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
