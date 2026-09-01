"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useAuth } from "@/hooks/useAuth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Card, CardContent, CardDescription, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Sparkles, AlertCircle, ArrowRight } from "lucide-react";

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const redirectUrl = searchParams.get("redirect") || "/dashboard";

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState("");

  const { login, isLoggingIn } = useAuth();

  const handleSubmit = async (e) => {
    e.preventDefault();
    setFormError("");

    if (!email || !password) {
      setFormError("Please enter both email and password.");
      return;
    }

    try {
      await login({ email, password });
      router.replace(redirectUrl);
    } catch (err) {
      setFormError(err.message || "Invalid credentials. Please try again.");
    }
  };

  return (
    <Card className="w-full max-w-md border-zinc-200 shadow-md dark:border-zinc-800">
      <CardHeader className="space-y-2 text-center pb-4">
        <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-zinc-900 text-white dark:bg-zinc-50 dark:text-zinc-900 shadow-2xs">
          <Sparkles className="h-5 w-5" />
        </div>
        <CardTitle className="text-xl font-bold tracking-tight">
          Welcome to ResearchLens
        </CardTitle>
        <CardDescription className="text-xs">
          Sign in to access your literature workspace and RAG assistant
        </CardDescription>
      </CardHeader>

      <form onSubmit={handleSubmit}>
        <CardContent className="space-y-3.5">
          {formError && (
            <div className="flex items-center gap-2 rounded-lg bg-red-50 p-2.5 text-xs text-red-700 border border-red-200">
              <AlertCircle className="h-4 w-4 shrink-0" />
              <span>{formError}</span>
            </div>
          )}

          <div className="space-y-1 text-left">
            <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
              Email address
            </label>
            <Input
              type="email"
              placeholder="researcher@university.edu"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="text-xs"
            />
          </div>

          <div className="space-y-1 text-left">
            <div className="flex items-center justify-between">
              <label className="text-xs font-medium text-zinc-700 dark:text-zinc-300">
                Password
              </label>
            </div>
            <Input
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              className="text-xs"
            />
          </div>
        </CardContent>

        <CardFooter className="flex flex-col space-y-3 pt-2">
          <Button
            type="submit"
            variant="workbench"
            className="w-full h-9 text-xs font-semibold gap-1.5"
            disabled={isLoggingIn}
          >
            {isLoggingIn ? "Authenticating..." : "Sign In to Workbench"}
            <ArrowRight className="h-3.5 w-3.5" />
          </Button>

          <p className="text-center text-xs text-zinc-500">
            Don&apos;t have an account?{" "}
            <Link
              href="/register"
              className="font-semibold text-zinc-900 underline hover:text-zinc-700 dark:text-zinc-100"
            >
              Create Account
            </Link>
          </p>
        </CardFooter>
      </form>
    </Card>
  );
}
