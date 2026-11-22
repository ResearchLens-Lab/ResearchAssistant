"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, useEffect } from "react";
import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { papersService } from "@/services/papers.service";
import { ShieldCheck, ChevronDown, ChevronUp, AlertCircle, CheckCircle2, Pencil } from "lucide-react";

function statusVariant(status) {
  if (status === "VERIFIED METADATA") return "grounded";
  if (status === "METADATA MISMATCH" || status === "RETRACTION/CORRECTION FLAG") return "warning";
  if (status === "EXTERNAL VERIFICATION UNAVAILABLE" || status === "DISABLED") return "secondary";
  return "outline";
}

export function SourceVerificationCard({ paper, onDoiUpdated }) {
  const queryClient = useQueryClient();
  const [isExpanded, setIsExpanded] = useState(false);
  const [doiInput, setDoiInput] = useState(paper?.doi || "");
  const [isEditingDoi, setIsEditingDoi] = useState(false);
  const [saveError, setSaveError] = useState("");
  const [externalLookups, setExternalLookups] = useState(false);

  useEffect(() => {
    if (typeof window !== "undefined" && window.researchLensDesktop?.getExternalLookups) {
      window.researchLensDesktop
        .getExternalLookups()
        .then(setExternalLookups)
        .catch(() => setExternalLookups(false));
    }
  }, []);

  const verification = useMutation({
    mutationFn: () => papersService.verifySource(paper.id),
  });

  const saveDoiMutation = useMutation({
    mutationFn: (newDoi) => papersService.update(paper.id, { doi: newDoi }),
    onSuccess: (updated) => {
      setIsEditingDoi(false);
      setSaveError("");
      queryClient.invalidateQueries({ queryKey: ["paper", paper.id] });
      if (onDoiUpdated) onDoiUpdated(updated);
      verification.mutate();
    },
    onError: (err) => {
      setSaveError(err.message || "Could not save DOI.");
    },
  });

  const result = verification.data;

  const handleSaveAndVerify = (e) => {
    e.preventDefault();
    const trimmed = doiInput.trim();
    if (!trimmed) {
      setSaveError("Please enter a valid DOI.");
      return;
    }
    saveDoiMutation.mutate(trimmed);
  };

  if (!externalLookups) {
    return (
      <div className="rounded-2xl border border-slate-200/90 bg-slate-50/70 p-4 shadow-2xs text-xs text-slate-600 flex items-center justify-between gap-3">
        <div>
          <p className="font-semibold text-slate-800">Online verification is off.</p>
          <p className="text-[11px] text-slate-500 mt-0.5">Turn it on in Settings to verify DOI metadata.</p>
        </div>
        <Button variant="outline" size="sm" asChild className="h-7 text-xs rounded-full shrink-0">
          <Link href="/settings">Settings</Link>
        </Button>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200/90 bg-white p-3.5 shadow-2xs space-y-2.5">
      {/* Sleek Row */}
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-sky-50 text-[#1d6fc4]">
            <ShieldCheck className="h-4 w-4" />
          </div>
          <div className="min-w-0">
            <h3 className="text-xs font-bold uppercase tracking-wider text-slate-800">
              Bibliographic Verification
            </h3>
            <p className="text-[11px] text-slate-400 truncate">
              {paper.doi ? `DOI: ${paper.doi}` : "Optional for academic papers (Crossref & OpenAlex)"}
            </p>
          </div>
        </div>

        <div className="flex items-center gap-1.5 shrink-0">
          {paper.doi ? (
            <>
              <Button
                size="sm"
                variant="outline"
                onClick={() => verification.mutate()}
                disabled={verification.isPending}
                className="h-7 text-xs rounded-full px-3 text-[#1d6fc4] border-sky-200 hover:bg-sky-50"
              >
                {verification.isPending ? "Checking…" : result ? "Re-verify" : "Verify DOI"}
              </Button>
              <button
                type="button"
                onClick={() => setIsEditingDoi(!isEditingDoi)}
                className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
                title={isEditingDoi ? "Cancel" : "Edit DOI"}
              >
                <Pencil className="h-3.5 w-3.5" />
              </button>
            </>
          ) : (
            <button
              type="button"
              onClick={() => setIsEditingDoi(!isEditingDoi)}
              className="text-xs font-medium text-[#1d6fc4] hover:underline px-2 py-1 rounded-md"
            >
              {isEditingDoi ? "Cancel" : "+ Add DOI"}
            </button>
          )}

          {result && result.status !== "DISABLED" && (
            <button
              type="button"
              onClick={() => setIsExpanded(!isExpanded)}
              className="p-1 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition-colors"
              title={isExpanded ? "Collapse details" : "Expand details"}
            >
              {isExpanded ? <ChevronUp className="h-4 w-4" /> : <ChevronDown className="h-4 w-4" />}
            </button>
          )}
        </div>
      </div>

      {/* Inline DOI Editor: Hidden unless user clicks + Add DOI or has a DOI */}
      {isEditingDoi && (
        <form onSubmit={handleSaveAndVerify} className="pt-2 border-t border-slate-100 space-y-2">
          <p className="text-[11px] text-slate-500">
            Enter paper DOI to verify peer-review & registry metadata against Crossref & OpenAlex:
          </p>
          <div className="flex items-center gap-2">
            <input
              type="text"
              placeholder="e.g. 10.1145/3290605.3300233"
              value={doiInput}
              onChange={(e) => {
                setDoiInput(e.target.value);
                if (saveError) setSaveError("");
              }}
              className="h-8 flex-1 rounded-lg border border-slate-200 px-3 text-xs outline-none focus:border-sky-500 font-mono"
            />
            <Button
              type="submit"
              size="sm"
              disabled={saveDoiMutation.isPending || !doiInput.trim()}
              className="h-8 text-xs bg-[#1d6fc4] hover:bg-[#185ea8] text-white rounded-lg px-3"
            >
              {saveDoiMutation.isPending ? "Saving…" : "Save & Verify"}
            </Button>
          </div>
          {saveError && (
            <p className="text-[11px] text-rose-600 font-medium">{saveError}</p>
          )}
        </form>
      )}

      {/* Verification Result Summary */}
      {result && (
        <div className="pt-2 border-t border-slate-100 space-y-1.5">
          <div className="flex items-center justify-between gap-2">
            <div className="flex items-center gap-1.5 flex-wrap">
              <Badge variant={statusVariant(result.status)} className="text-[11px]">
                {result.status}
              </Badge>
              {result.status !== "DISABLED" && (
                <span className="text-[11px] text-slate-400">
                  Crossref: {result.registries?.crossref || "checked"} · OpenAlex: {result.registries?.openalex || "checked"}
                </span>
              )}
            </div>
            {result.status !== "DISABLED" && (
              <button
                type="button"
                onClick={() => setIsExpanded(!isExpanded)}
                className="text-[11px] text-[#1d6fc4] hover:underline"
              >
                {isExpanded ? "Hide details" : "View registry details"}
              </button>
            )}
          </div>

          {result.message && (
            <p className={result.status === "DISABLED" ? "text-[11px] text-slate-500 leading-relaxed" : "text-[11px] text-slate-600 leading-relaxed"}>
              {result.message}
            </p>
          )}

          {isExpanded && (
            <div className="space-y-1.5 rounded-xl border border-slate-100 bg-slate-50/80 p-2.5 text-xs mt-1">
              {result.title && (
                <div>
                  <p className="text-[11px] uppercase font-semibold text-slate-400">Registry Title</p>
                  <p className="text-slate-800 font-medium text-xs">{result.title}</p>
                </div>
              )}
              <div className="grid grid-cols-2 gap-2 text-[11px] pt-1">
                <div>
                  <span className="text-slate-400">Authors: </span>
                  <span className="text-slate-700">{result.authors?.join(", ") || "N/A"}</span>
                </div>
                <div>
                  <span className="text-slate-400">Publisher: </span>
                  <span className="text-slate-700">{result.publisher || "N/A"}</span>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
