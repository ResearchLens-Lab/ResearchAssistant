"use client";

import React, { useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { PasswordInput } from "@/components/auth/PasswordInput";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { AlertCircle, ArrowRight, Check, Circle, CircleCheck } from "lucide-react";
import { isStrongPassword, normalizeUsername, passwordRequirements, validateUsername } from "@/utils/authValidation.mjs";
import { tokenStorage } from "@/utils/tokenStorage";

function registrationError(error) {
  if (error?.code === "USERNAME_ALREADY_TAKEN") return "That username is already taken. Try another.";
  if (error?.code === "EMAIL_ALREADY_REGISTERED") return "An account is already registered with this email. Please sign in.";
  if (error?.statusCode === 429) return "Too many account creation attempts. Please wait before trying again.";
  if (error?.statusCode === 422) return "Check your email, username, and password requirements.";
  if (!error?.statusCode) return "We couldn't connect to ResearchLens. Check your connection and try again.";
  return "ResearchLens is temporarily unavailable. Please try again shortly.";
}

export function RegisterForm() {
  const router = useRouter();
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [formError, setFormError] = useState("");
  const [createdUsername, setCreatedUsername] = useState("");
  const { register, isRegistering } = useAuth();
  const usernameError = useMemo(() => validateUsername(username), [username]);
  const requirements = useMemo(() => passwordRequirements(password), [password]);
  const mismatch = confirmPassword.length > 0 && password !== confirmPassword;

  const handleSubmit = async (event) => {
    event.preventDefault();
    setFormError("");
    if (usernameError) { setFormError(usernameError); return; }
    if (!email.trim()) { setFormError("Enter your email address."); return; }
    if (!isStrongPassword(password)) { setFormError("Meet all five password requirements before continuing."); return; }
    if (password !== confirmPassword) { setFormError("Passwords don't match."); return; }
    try {
      tokenStorage.clear();
      const canonicalUsername = normalizeUsername(username);
      await register({ username: canonicalUsername, email: email.trim(), password });
      setCreatedUsername(canonicalUsername);
      setPassword("");
      setConfirmPassword("");
    } catch (error) {
      setFormError(registrationError(error));
    }
  };

  if (createdUsername) {
    return <Card role="status" aria-live="polite" className="w-full max-w-md rounded-2xl border-[var(--rl-border)] shadow-[0_18px_48px_-24px_rgba(38,120,184,0.28)]">
      <CardHeader className="items-center space-y-3 pb-4 text-center">
        <span className="flex h-14 w-14 items-center justify-center rounded-full bg-[var(--rl-selected)] text-[var(--rl-primary)] motion-safe:animate-in motion-safe:zoom-in-75"><CircleCheck className="h-8 w-8" aria-hidden="true" /></span>
        <CardTitle className="text-2xl font-semibold text-[var(--rl-ink)]">Your account is ready.</CardTitle>
        <CardDescription className="text-sm leading-6 text-[var(--rl-muted)]">Your ResearchLens account has been created successfully. Sign in to start your first Research Project.</CardDescription>
      </CardHeader>
      <CardContent className="text-center text-sm text-[var(--rl-muted)]">Username: <span className="font-semibold text-[var(--rl-ink)]">{createdUsername}</span></CardContent>
      <CardFooter className="flex-col pt-2">
        <Button type="button" variant="workbench" className="h-11 w-full gap-2 font-semibold" onClick={() => router.push(`/login?username=${encodeURIComponent(createdUsername)}`)}>
          Continue to sign in <ArrowRight className="h-4 w-4" aria-hidden="true" />
        </Button>
      </CardFooter>
    </Card>;
  }

  return (
    <Card className="w-full max-w-md rounded-2xl border-[var(--rl-border)] shadow-[0_18px_48px_-24px_rgba(38,120,184,0.28)]">
      <CardHeader className="min-w-0 space-y-1.5 px-4 pb-2 pt-4 text-left sm:px-5">
        <CardTitle className="text-2xl font-semibold tracking-tight text-[var(--rl-ink)]">Create your account</CardTitle>
        <CardDescription className="text-sm leading-5 text-[var(--rl-muted)]">Set up a private workspace for your research documents.</CardDescription>
      </CardHeader>
      <form onSubmit={handleSubmit} noValidate>
        <CardContent className="min-w-0 space-y-2 px-4 pb-2 pt-0 sm:px-5">
          {formError && <div role="alert" className="flex items-center gap-2 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800"><AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" /><span>{formError}</span></div>}
          <div className="space-y-1">
            <label htmlFor="register-username" className="text-sm font-medium text-[var(--rl-ink)]">Username</label>
            <Input id="register-username" value={username} onChange={(event) => { setUsername(event.target.value); setFormError(""); }} autoComplete="username" autoCapitalize="none" spellCheck="false" required aria-describedby="username-help username-status" aria-invalid={!!username && !!usernameError} />
            <p id="username-help" className="text-[11px] leading-4 text-[var(--rl-muted)]">3–24 characters · letters, numbers, dots, underscores, hyphens.</p>
            <p id="username-status" aria-live="polite" className={`min-h-4 text-xs leading-4 ${username && usernameError ? "text-red-700" : "text-[var(--rl-muted)]"}`}>{username ? usernameError || "Format looks good. Availability is checked on submit." : " "}</p>
          </div>
          <div className="space-y-1">
            <label htmlFor="register-email" className="text-sm font-medium text-[var(--rl-ink)]">Email (used only to sign in, never sent anywhere)</label>
            <Input id="register-email" type="email" value={email} onChange={(event) => { setEmail(event.target.value); setFormError(""); }} autoComplete="email" required />
          </div>
          <div className="space-y-1">
            <label htmlFor="register-password" className="text-sm font-medium text-[var(--rl-ink)]">Password</label>
            <PasswordInput id="register-password" value={password} onChange={(event) => { setPassword(event.target.value); setFormError(""); }} autoComplete="new-password" minLength={12} />
            <ul className="grid grid-cols-2 gap-x-3 gap-y-0.5 pt-0.5 text-[11px] leading-4 text-[var(--rl-muted)] sm:text-xs" aria-label="Password requirements">
              {requirements.map(({ label, valid }) => <li key={label} className="flex items-center gap-1.5"><span className={valid ? "text-[var(--rl-primary)]" : "text-[var(--rl-muted)]"}>{valid ? <Check className="h-3.5 w-3.5" aria-hidden="true" /> : <Circle className="h-3 w-3" aria-hidden="true" />}</span><span>{label}</span></li>)}
            </ul>
            <p className="sr-only" aria-live="polite">{requirements.filter((item) => item.valid).length} of 5 password requirements met.</p>
          </div>
          <div className="space-y-1">
            <label htmlFor="register-confirm-password" className="text-sm font-medium text-[var(--rl-ink)]">Confirm password</label>
            <PasswordInput id="register-confirm-password" value={confirmPassword} onChange={(event) => { setConfirmPassword(event.target.value); setFormError(""); }} autoComplete="new-password" minLength={12} aria-invalid={mismatch} aria-describedby="confirm-password-status" />
            <p id="confirm-password-status" aria-live="polite" className="min-h-4 text-xs text-red-700">{mismatch ? "Passwords don't match." : " "}</p>
          </div>
        </CardContent>
        <CardFooter className="min-w-0 flex-col space-y-2 px-4 pb-4 pt-1 sm:px-5">
          <Button type="submit" variant="workbench" className="h-11 w-full gap-2 text-sm font-semibold" disabled={isRegistering}>
            {isRegistering ? "Creating account…" : "Create account"}<ArrowRight className="h-4 w-4" aria-hidden="true" />
          </Button>
          <p className="text-center text-sm text-[var(--rl-muted)]">Already have an account? <Link href="/login" className="font-semibold text-[var(--rl-primary)] underline underline-offset-4">Sign in</Link></p>
        </CardFooter>
      </form>
    </Card>
  );
}
