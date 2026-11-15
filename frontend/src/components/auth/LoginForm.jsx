"use client";

import React, { useState, useEffect, useRef } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, ArrowRight, Loader2 } from "lucide-react";

function loginError(error) {
  if (error?.statusCode === 401) return "The username or password is incorrect.";
  if (error?.statusCode === 429) return "Too many sign-in attempts. Please wait before trying again.";
  if (error?.statusCode === 504 || error?.code === "TIMEOUT") return "Connection timed out. Check that the backend server is running.";
  if (!error?.statusCode) return "We couldn't connect to ResearchLens. Check your connection and try again.";
  return "ResearchLens is temporarily unavailable. Please try again shortly.";
}

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedRedirect = searchParams.get("redirect") || "/papers";
  const redirectUrl = requestedRedirect.startsWith("/") && !requestedRedirect.startsWith("//") ? requestedRedirect : "/papers";
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState("");
  const [recoveryNotice, setRecoveryNotice] = useState(false);
  const [submitted, setSubmitted] = useState(false);
  const { login, isLoggingIn, isAuthenticated } = useAuth();
  const submittingRef = useRef(false);

  useEffect(() => {
    if (isAuthenticated) {
      router.replace(redirectUrl);
    }
  }, [isAuthenticated, redirectUrl, router]);

  const handleSubmit = async (event) => {
    event.preventDefault();
    if (submittingRef.current || isLoggingIn) return;
    setSubmitted(true);
    setFormError("");

    const form = event.currentTarget;
    const rawId = form.elements["login-identifier"]?.value ?? identifier;
    const rawPass = form.elements["login-password"]?.value ?? password;
    const trimmedId = (rawId || "").trim();

    if (!trimmedId) { setFormError("Enter your username."); return; }
    if (!rawPass) { setFormError("Enter your password."); return; }

    submittingRef.current = true;
    try {
      await login({ identifier: trimmedId, password: rawPass });
      setPassword("");
      try { sessionStorage.setItem("researchlens.auth.success", "1"); } catch { /* Toast is optional; authentication is complete. */ }
      router.replace(redirectUrl);
    } catch (error) {
      submittingRef.current = false;
      setPassword("");
      setFormError(loginError(error));
    }
  };

  return (
    <Card className="w-full max-w-md rounded-2xl border-[var(--rl-border)] shadow-[0_18px_48px_-24px_rgba(38,120,184,0.28)]">
      <CardHeader className="space-y-2 pb-5 text-left">
        <CardTitle className="text-2xl font-semibold tracking-tight text-[var(--rl-ink)]">Welcome back</CardTitle>
        <CardDescription className="text-sm leading-6 text-[var(--rl-muted)]">Sign in to continue your source-grounded research.</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit} noValidate>
        <CardContent className="space-y-4">
          {formError && <div role="alert" className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"><AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" /><span>{formError}</span></div>}
          <div className="space-y-1.5">
            <label htmlFor="login-identifier" className="text-sm font-medium text-[var(--rl-ink)]">Username</label>
            <Input id="login-identifier" value={identifier} onChange={(event) => { setIdentifier(event.target.value); setFormError(""); }} autoComplete="username" autoCapitalize="none" autoFocus required aria-invalid={submitted && !identifier.trim()} aria-describedby="login-identifier-help login-identifier-error" />
            <p id="login-identifier-help" className="text-xs leading-5 text-[var(--rl-muted)]">Existing accounts can also sign in with their email address.</p>
            <p id="login-identifier-error" className="min-h-4 text-xs text-red-700">{submitted && !identifier.trim() ? "Enter your username." : " "}</p>
          </div>
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-3"><label htmlFor="login-password" className="text-sm font-medium text-[var(--rl-ink)]">Password</label><button type="button" onClick={() => setRecoveryNotice((shown) => !shown)} className="text-xs font-medium text-[var(--rl-primary)] underline underline-offset-4">Forgot password?</button></div>
            <PasswordInput id="login-password" value={password} onChange={(event) => { setPassword(event.target.value); setFormError(""); }} autoComplete="current-password" aria-invalid={submitted && !password} aria-describedby="login-password-error" />
            <p id="login-password-error" className="min-h-4 text-xs text-red-700">{submitted && !password ? "Enter your password." : " "}</p>
          </div>
          {recoveryNotice && <p role="status" className="rounded-lg bg-[var(--rl-tint)] p-3 text-xs leading-5 text-[var(--rl-muted)]">Password recovery is not configured in this application yet. Contact your workspace administrator for help.</p>}
        </CardContent>
        <CardFooter className="flex-col space-y-4 pt-2">
          <Button type="submit" variant="workbench" className="h-11 w-full gap-2 text-sm font-semibold" disabled={isLoggingIn}>
            {isLoggingIn ? <><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />Signing in…</> : <>Sign in<ArrowRight className="h-4 w-4" aria-hidden="true" /></>}
          </Button>
          <p className="text-center text-sm text-[var(--rl-muted)]">New to ResearchLens? <Link href="/register" className="font-semibold text-[var(--rl-primary)] underline underline-offset-4 hover:text-[#1f659c]">Create an account</Link></p>
        </CardFooter>
      </form>
    </Card>
  );
}
