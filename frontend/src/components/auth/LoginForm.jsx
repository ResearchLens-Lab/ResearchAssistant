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

/**
 * Authoritative Authentication State Machine
 * IDLE → VALIDATING → AUTHENTICATING → SUCCESS / ERROR
 */
export const AuthStatus = {
  IDLE: "IDLE",
  VALIDATING: "VALIDATING",
  AUTHENTICATING: "AUTHENTICATING",
  SUCCESS: "SUCCESS",
  ERROR: "ERROR",
};

function loginErrorMessage(error) {
  if (error?.message && error.message.includes("Desktop request key")) {
    return "Connecting to local desktop services... Please retry in a moment.";
  }
  if (error?.statusCode === 401) {
    return "The username or password is incorrect.";
  }
  if (error?.statusCode === 429) {
    return "Too many sign-in attempts. Please wait before trying again.";
  }
  if (error?.statusCode === 504 || error?.code === "TIMEOUT") {
    return "Connection timed out. Check that the local backend service is running.";
  }
  if (!error?.statusCode) {
    return "Could not connect to ResearchLens. Check that local services are active.";
  }
  return error?.message || "ResearchLens is temporarily unavailable. Please try again shortly.";
}

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const requestedRedirect = searchParams.get("redirect") || "/papers";
  const redirectUrl = requestedRedirect.startsWith("/") && !requestedRedirect.startsWith("//") ? requestedRedirect : "/papers";
  const requestedUsername = searchParams.get("username") || "";

  const [authStatus, setAuthStatus] = useState(AuthStatus.IDLE);
  const [identifier, setIdentifier] = useState(requestedUsername);
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState({ identifier: "", password: "" });
  const [serverError, setServerError] = useState("");
  const [recoveryNotice, setRecoveryNotice] = useState(false);

  const { login, isLoggingIn, isAuthenticated } = useAuth();
  const isNavigatingRef = useRef(false);

  useEffect(() => {
    if (requestedUsername && !identifier) {
      setIdentifier(requestedUsername);
    }
  }, [requestedUsername, identifier]);

  useEffect(() => {
    if (isAuthenticated && !isNavigatingRef.current) {
      isNavigatingRef.current = true;
      router.replace(redirectUrl);
    }
  }, [isAuthenticated, redirectUrl, router]);

  const isPending =
    authStatus === AuthStatus.VALIDATING ||
    authStatus === AuthStatus.AUTHENTICATING ||
    authStatus === AuthStatus.SUCCESS ||
    isLoggingIn;

  const handleIdentifierChange = (event) => {
    setIdentifier(event.target.value);
    if (authStatus === AuthStatus.ERROR) {
      setAuthStatus(AuthStatus.IDLE);
      setServerError("");
    }
    if (fieldErrors.identifier) {
      setFieldErrors((prev) => ({ ...prev, identifier: "" }));
    }
  };

  const handlePasswordChange = (event) => {
    setPassword(event.target.value);
    if (authStatus === AuthStatus.ERROR) {
      setAuthStatus(AuthStatus.IDLE);
      setServerError("");
    }
    if (fieldErrors.password) {
      setFieldErrors((prev) => ({ ...prev, password: "" }));
    }
  };

  const handleSubmit = async (event) => {
    event.preventDefault();

    // Guard against duplicate submission while in progress
    if (isPending) return;

    // Transition: IDLE -> VALIDATING
    setAuthStatus(AuthStatus.VALIDATING);
    setServerError("");

    const trimmedId = (identifier || "").trim();
    const cleanPass = password || "";

    const newFieldErrors = {
      identifier: !trimmedId ? "Enter your username." : "",
      password: !cleanPass ? "Enter your password." : "",
    };

    if (newFieldErrors.identifier || newFieldErrors.password) {
      setFieldErrors(newFieldErrors);
      setAuthStatus(AuthStatus.ERROR);
      return;
    }

    setFieldErrors({ identifier: "", password: "" });

    // Transition: VALIDATING -> AUTHENTICATING
    setAuthStatus(AuthStatus.AUTHENTICATING);

    try {
      await login({ identifier: trimmedId, password: cleanPass });

      // Transition: AUTHENTICATING -> SUCCESS
      // CRITICAL: DO NOT clear password state here. Clearing password while navigating
      // would trigger field validation re-renders. Keep inputs controlled and stable.
      setAuthStatus(AuthStatus.SUCCESS);

      try {
        sessionStorage.setItem("researchlens.auth.success", "1");
      } catch {
        // Optional success banner
      }

      isNavigatingRef.current = true;
      router.replace(redirectUrl);
    } catch (error) {
      // Transition: AUTHENTICATING -> ERROR
      // Preserve the entered password so the user can correct typos rather than losing input.
      setAuthStatus(AuthStatus.ERROR);
      setServerError(loginErrorMessage(error));
    }
  };

  return (
    <Card className="w-full max-w-md rounded-2xl border-[var(--rl-border)] shadow-[0_18px_48px_-24px_rgba(38,120,184,0.28)]">
      <CardHeader className="space-y-2 pb-5 text-left">
        <CardTitle className="text-2xl font-semibold tracking-tight text-[var(--rl-ink)]">Welcome back</CardTitle>
        <CardDescription className="text-sm leading-6 text-[var(--rl-muted)]">
          Sign in to continue your source-grounded research.
        </CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit} noValidate>
        <CardContent className="space-y-4">
          {serverError && (
            <div role="alert" className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">
              <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
              <span>{serverError}</span>
            </div>
          )}

          <div className="space-y-1.5">
            <label htmlFor="login-identifier" className="text-sm font-medium text-[var(--rl-ink)]">
              Username
            </label>
            <Input
              id="login-identifier"
              name="login-identifier"
              value={identifier}
              onChange={handleIdentifierChange}
              autoComplete="username"
              autoCapitalize="none"
              autoFocus
              disabled={isPending}
              required
              aria-invalid={Boolean(fieldErrors.identifier)}
              aria-describedby="login-identifier-help login-identifier-error"
            />
            <p id="login-identifier-help" className="text-xs leading-5 text-[var(--rl-muted)]">
              Existing accounts can also sign in with their email address.
            </p>
            <p id="login-identifier-error" className="min-h-4 text-xs text-red-700">
              {fieldErrors.identifier || " "}
            </p>
          </div>

          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-3">
              <label htmlFor="login-password" className="text-sm font-medium text-[var(--rl-ink)]">
                Password
              </label>
              <button
                type="button"
                onClick={() => setRecoveryNotice((shown) => !shown)}
                className="text-xs font-medium text-[var(--rl-primary)] underline underline-offset-4"
              >
                Forgot password?
              </button>
            </div>
            <PasswordInput
              id="login-password"
              name="login-password"
              value={password}
              onChange={handlePasswordChange}
              autoComplete="current-password"
              disabled={isPending}
              aria-invalid={Boolean(fieldErrors.password)}
              aria-describedby="login-password-error"
            />
            <p id="login-password-error" className="min-h-4 text-xs text-red-700">
              {fieldErrors.password || " "}
            </p>
          </div>

          {recoveryNotice && (
            <div role="status" className="rounded-lg bg-[var(--rl-tint)] p-3 text-xs leading-5 text-[var(--rl-muted)]">
              <strong>Local Account Notice:</strong> ResearchLens Desktop operates privately on your computer. Credentials are stored securely in your local research library. Passwords cannot be recovered via email. If forgotten, create a new local researcher profile or restore from a library backup.
            </div>
          )}
        </CardContent>

        <CardFooter className="flex-col space-y-4 pt-2">
          <Button
            type="submit"
            variant="workbench"
            className="h-11 w-full gap-2 text-sm font-semibold"
            disabled={isPending}
          >
            {isPending ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
                {authStatus === AuthStatus.SUCCESS ? "Signing in…" : "Authenticating…"}
              </>
            ) : (
              <>
                Sign in
                <ArrowRight className="h-4 w-4" aria-hidden="true" />
              </>
            )}
          </Button>

          <p className="text-center text-sm text-[var(--rl-muted)]">
            New to ResearchLens?{" "}
            <Link href="/register" className="font-semibold text-[var(--rl-primary)] underline underline-offset-4 hover:text-[#1f659c]">
              Create an account
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
