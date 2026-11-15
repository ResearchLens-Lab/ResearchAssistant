"use client";

import React, { Suspense } from "react";
import { PdfEvidenceViewer } from "@/components/pdf/PdfEvidenceViewer";

export default function PdfViewerPage() {
  return <Suspense fallback={<main className="grid h-dvh place-items-center bg-slate-100 text-sm text-slate-600">Loading PDF viewer…</main>}><PdfEvidenceViewer /></Suspense>;
}
