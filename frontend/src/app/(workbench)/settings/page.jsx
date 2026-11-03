"use client";

import React, { useState, useEffect } from "react";
import { useAuth } from "@/hooks/useAuth";
import { useQuery } from "@tanstack/react-query";
import { researchService } from "@/services/research.service";
import { Card, CardContent, CardDescription, CardHeader, CardTitle, CardFooter } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Settings, ShieldCheck, User, LogOut, Check } from "lucide-react";
import { formatDate } from "@/utils/formatters";

export default function SettingsPage() {
  const { user, updateProfile, isUpdatingProfile, logout } = useAuth();
  const [fullName, setFullName] = useState("");
  const [saveSuccess, setSaveSuccess] = useState(false);

  useEffect(() => {
    if (user?.full_name) {
      setFullName(user.full_name);
    }
  }, [user]);

  const { data: healthData } = useQuery({
    queryKey: ["healthCheck"],
    queryFn: () => researchService.getHealth(),
  });

  const { data: readyData } = useQuery({
    queryKey: ["readinessCheck"],
    queryFn: () => researchService.getReadiness(),
  });

  const handleProfileSave = async (e) => {
    e.preventDefault();
    await updateProfile({ full_name: fullName.trim() || null });
    setSaveSuccess(true);
    setTimeout(() => setSaveSuccess(false), 3000);
  };

  return (
    <div className="p-6 md:p-8 space-y-6 max-w-4xl mx-auto">
      <div className="border-b border-zinc-200/80 pb-4 dark:border-zinc-800 space-y-1">
        <div className="flex items-center gap-2">
          <Settings className="h-5 w-5 text-zinc-900 dark:text-zinc-100" />
          <h1 className="text-xl font-bold tracking-tight text-zinc-900 dark:text-zinc-100">
            Account & System Settings
          </h1>
        </div>
        <p className="text-xs text-zinc-500 font-mono">
          Manage your researcher profile and monitor backend architecture integration health.
        </p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Profile Settings */}
        <Card className="border-zinc-200 shadow-2xs dark:border-zinc-800">
          <CardHeader className="p-4 pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <User className="h-4 w-4 text-zinc-700 dark:text-zinc-300" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                Researcher Profile
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Update your workspace identity
            </CardDescription>
          </CardHeader>

          <form onSubmit={handleProfileSave}>
            <CardContent className="p-4 space-y-3">
              <div className="space-y-1">
                <label className="text-[11px] font-medium text-zinc-700">
                  Full Name
                </label>
                <Input
                  value={fullName}
                  onChange={(e) => setFullName(e.target.value)}
                  placeholder="Dr. Jane Doe"
                  className="text-xs"
                />
              </div>

              <div className="space-y-1">
                <label className="text-[11px] font-medium text-zinc-700">
                  Email Address
                </label>
                <Input
                  value={user?.email || ""}
                  disabled
                  className="text-xs bg-zinc-100 font-mono cursor-not-allowed dark:bg-zinc-800"
                />
                <p className="text-[10px] text-zinc-400 font-mono">
                  Registered: {user?.created_at ? formatDate(user.created_at) : "--"}
                </p>
              </div>

              {saveSuccess && (
                <div className="flex items-center gap-1.5 text-xs text-emerald-600 font-medium">
                  <Check className="h-3.5 w-3.5" />
                  <span>Profile updated successfully</span>
                </div>
              )}
            </CardContent>

            <CardFooter className="p-4 pt-0 flex justify-between">
              <Button
                type="submit"
                variant="workbench"
                size="sm"
                disabled={isUpdatingProfile}
                className="text-sm"
              >
                {isUpdatingProfile ? "Saving..." : "Save Changes"}
              </Button>

              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => logout()}
                className="text-xs text-red-600 hover:bg-red-50 hover:text-red-700"
              >
                <LogOut className="mr-1.5 h-3.5 w-3.5" />
                <span>Sign Out</span>
              </Button>
            </CardFooter>
          </form>
        </Card>

        {/* Backend & Architecture Status */}
        <Card className="border-zinc-200 shadow-2xs dark:border-zinc-800">
          <CardHeader className="p-4 pb-2 border-b border-zinc-100 dark:border-zinc-800">
            <div className="flex items-center gap-2">
              <ShieldCheck className="h-4 w-4 text-emerald-600" />
              <CardTitle className="text-xs font-bold uppercase tracking-wider text-zinc-800 dark:text-zinc-200">
                System Integration Status
              </CardTitle>
            </div>
            <CardDescription className="text-xs">
              Live status from FastAPI and storage backends
            </CardDescription>
          </CardHeader>

          <CardContent className="p-4 space-y-3 text-xs font-mono">
            <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
              <span className="text-zinc-500">FastAPI Gateway:</span>
              <Badge
                variant={healthData?.status === "ok" ? "grounded" : "destructive"}
                className="text-[10px]"
              >
                {healthData?.status === "ok" ? "200 Healthy" : "Offline"}
              </Badge>
            </div>

            <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
              <span className="text-zinc-500">PostgreSQL DB:</span>
              <Badge
                variant={readyData?.status === "ready" ? "grounded" : "warning"}
                className="text-[10px]"
              >
                {readyData?.status === "ready" ? "Ready" : "Degraded"}
              </Badge>
            </div>

            <div className="flex items-center justify-between border-b border-zinc-100 pb-2 dark:border-zinc-800">
              <span className="text-zinc-500">ChromaDB Vector Store:</span>
              <Badge variant="secondary" className="text-[10px]">
                In-Process / Docker
              </Badge>
            </div>

            <div className="flex items-center justify-between">
              <span className="text-zinc-500">Upload Size Limit:</span>
              <span className="font-semibold text-zinc-700 dark:text-zinc-300">
                1 GiB per file · 1 GiB per batch
              </span>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
