"use client";

import React, { useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import * as pdfjs from "pdfjs-dist/build/pdf.mjs";
import { tokenStorage } from "@/utils/tokenStorage";
import { refreshAccessToken } from "@/services/api.client";
import { ChevronLeft, ChevronRight, LoaderCircle, Minus, Plus, SearchCheck } from "lucide-react";

pdfjs.GlobalWorkerOptions.workerSrc = new URL("pdfjs-dist/build/pdf.worker.min.mjs", import.meta.url).toString();
const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000/api/v1";

function normalizeText(value) {
  return (value || "")
    .normalize("NFKC")
    .toLocaleLowerCase()
    .replace(/[^\p{L}\p{N}]+/gu, " ")
    .replace(/\s+/g, " ")
    .trim()
}

function makeNormalizedTextMap(root) {
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  const chars = [];
  const positions = [];
  let previousSpace = true;
  let node;
  while ((node = walker.nextNode())) {
    const text = node.nodeValue || "";
    for (let offset = 0; offset < text.length; offset += 1) {
      const raw = text[offset];
      const normalizedChar = raw.normalize("NFKC").toLocaleLowerCase();
      if (!/[\p{L}\p{N}]/u.test(normalizedChar)) {
        if (!previousSpace) {
          chars.push(" ");
          positions.push({ node, offset });
        }
        previousSpace = true;
      } else {
        for (const char of normalizedChar) {
          chars.push(char);
          positions.push({ node, offset });
        }
        previousSpace = false;
      }
    }
  }
  while (chars.at(-1) === " ") { chars.pop(); positions.pop(); }
  return { text: chars.join(""), positions };
}

function selectTextHighlight(root, phrase, pageElement) {
  if (!root || !phrase) return [];
  const normalized = makeNormalizedTextMap(root);
  const needle = normalizeText(phrase);
  const start = normalized.text.indexOf(needle);
  if (start < 0 || !needle) return [];
  const first = normalized.positions[start];
  const last = normalized.positions[start + needle.length - 1];
  if (!first || !last) return [];
  const range = document.createRange();
  range.setStart(first.node, first.offset);
  range.setEnd(last.node, last.offset + 1);
  const pageRect = pageElement.getBoundingClientRect();
  return [...range.getClientRects()].map((rect) => ({
    left: rect.left - pageRect.left,
    top: rect.top - pageRect.top,
    width: rect.width,
    height: rect.height,
  }));
}

async function getAuthorizedPdf(documentId) {
  const endpoint = `${API_BASE}/documents/${encodeURIComponent(documentId)}/file`;
  const request = (token) => fetch(endpoint, { headers: { Authorization: `Bearer ${token}` } });
  let response = await request(tokenStorage.getAccessToken());
  if (response.status === 401 && tokenStorage.getRefreshToken()) {
    const token = await refreshAccessToken();
    if (token) response = await request(token);
  }
  if (!response.ok) throw new Error(`The PDF could not be loaded (${response.status}).`);
  return new Uint8Array(await response.arrayBuffer());
}

export function PdfEvidenceViewer() {
  const params = useSearchParams();
  const documentId = params.get("document_id") || "";
  const filename = params.get("filename") || "Research source";
  const targetPhrase = params.get("highlight") || "";
  const requestedPage = Math.max(1, Number(params.get("page")) || 1);
  const requestedEndPage = Math.max(requestedPage, Number(params.get("end_page")) || requestedPage);
  const [pdf, setPdf] = useState(null);
  const [pageNumber, setPageNumber] = useState(requestedPage);
  const [scale, setScale] = useState(1.2);
  const [status, setStatus] = useState("Loading source PDF…");
  const [error, setError] = useState("");
  const [highlights, setHighlights] = useState([]);
  const canvasRef = useRef(null);
  const textLayerRef = useRef(null);
  const pageRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    let loadingTask;
    if (!documentId) {
      setError("This PDF link is missing its document identifier.");
      setStatus("");
      return undefined;
    }
    setError("");
    setStatus("Loading source PDF…");
    getAuthorizedPdf(documentId)
      .then((data) => {
        if (cancelled) return;
        loadingTask = pdfjs.getDocument({ data });
        return loadingTask.promise;
      })
      .then((loadedPdf) => {
        if (!cancelled && loadedPdf) {
          setPdf(loadedPdf);
          setPageNumber(Math.min(requestedPage, loadedPdf.numPages));
          setStatus("");
        }
      })
      .catch((loadError) => {
        if (!cancelled) {
          setError(loadError?.message || "The PDF could not be loaded.");
          setStatus("");
        }
      });
    return () => {
      cancelled = true;
      loadingTask?.destroy();
    };
  }, [documentId, requestedPage]);

  useEffect(() => {
    if (!pdf || !canvasRef.current || !textLayerRef.current || !pageRef.current) return undefined;
    let cancelled = false;
    let renderTask;
    const renderPage = async () => {
      setError("");
      setStatus(`Opening page ${pageNumber}…`);
      setHighlights([]);
      textLayerRef.current.replaceChildren();
      const page = await pdf.getPage(pageNumber);
      if (cancelled) return;
      const viewport = page.getViewport({ scale });
      const canvas = canvasRef.current;
      const context = canvas.getContext("2d", { alpha: false });
      const pixelRatio = window.devicePixelRatio || 1;
      canvas.width = Math.ceil(viewport.width * pixelRatio);
      canvas.height = Math.ceil(viewport.height * pixelRatio);
      canvas.style.width = `${viewport.width}px`;
      canvas.style.height = `${viewport.height}px`;
      textLayerRef.current.style.width = `${viewport.width}px`;
      textLayerRef.current.style.height = `${viewport.height}px`;
      textLayerRef.current.style.setProperty("--scale-factor", String(scale));
      pageRef.current.style.width = `${viewport.width}px`;
      pageRef.current.style.height = `${viewport.height}px`;
      renderTask = page.render({
        canvasContext: context,
        viewport,
        transform: pixelRatio === 1 ? null : [pixelRatio, 0, 0, pixelRatio, 0, 0],
      });
      await renderTask.promise;
      const textContent = await page.getTextContent();
      if (cancelled) return;
      const textLayer = new pdfjs.TextLayer({ textContentSource: textContent, container: textLayerRef.current, viewport });
      await textLayer.render();
      if (cancelled) return;
      const rects = selectTextHighlight(textLayerRef.current, targetPhrase, pageRef.current);
      setHighlights(rects);
      if (targetPhrase && rects.length === 0) {
        setStatus("Page opened. The cited text could not be matched on this page.");
      } else {
        setStatus("");
      }
    };
    renderPage().catch((renderError) => {
      if (!cancelled) setError(renderError?.message || "The selected PDF page could not be rendered.");
    });
    return () => {
      cancelled = true;
      renderTask?.cancel();
    };
  }, [pdf, pageNumber, scale, targetPhrase]);

  useEffect(() => {
    if (!pdf || !targetPhrase || requestedEndPage <= requestedPage) return undefined;
    let cancelled = false;
    (async () => {
      setStatus("Finding cited passage…");
      const finalPage = Math.min(Math.max(requestedEndPage, requestedPage), pdf.numPages, requestedPage + 10);
      let bestPage = requestedPage;
      let bestScore = 0;
      const targetWords = normalizeText(targetPhrase).split(" ").filter((word) => word.length > 2);
      for (let candidate = requestedPage; candidate <= finalPage; candidate += 1) {
        const page = await pdf.getPage(candidate);
        const content = await page.getTextContent();
        const text = content.items.map((item) => item.str || "").join(" ");
        const normalized = normalizeText(text);
        if (normalized.includes(normalizeText(targetPhrase))) {
          bestPage = candidate;
          break;
        }
        const pageWords = new Set(normalized.split(" "));
        const score = targetWords.reduce((total, word) => total + (pageWords.has(word) ? 1 : 0), 0);
        if (score > bestScore) { bestScore = score; bestPage = candidate; }
      }
      if (!cancelled && bestPage !== pageNumber) setPageNumber(bestPage);
      else if (!cancelled) setStatus("");
    })().catch(() => {});
    return () => { cancelled = true; };
  }, [pdf, requestedPage, requestedEndPage, targetPhrase]);

  return (
    <main className="flex h-dvh flex-col bg-slate-100 text-slate-800">
      <header className="z-10 flex min-h-14 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 shadow-sm">
        <div className="min-w-0">
          <h1 className="truncate text-sm font-semibold" title={filename}>{filename}</h1>
          <p className="text-xs text-slate-500">Cited passage · page {pageNumber}{pdf ? ` of ${pdf.numPages}` : ""}</p>
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <button type="button" aria-label="Previous page" disabled={!pdf || pageNumber <= 1} onClick={() => setPageNumber((page) => Math.max(1, page - 1))} className="rounded-md border border-slate-200 p-2 disabled:opacity-40"><ChevronLeft className="h-4 w-4" /></button>
          <span className="min-w-16 text-center text-xs tabular-nums">{pageNumber}{pdf ? ` / ${pdf.numPages}` : ""}</span>
          <button type="button" aria-label="Next page" disabled={!pdf || pageNumber >= pdf.numPages} onClick={() => setPageNumber((page) => Math.min(pdf.numPages, page + 1))} className="rounded-md border border-slate-200 p-2 disabled:opacity-40"><ChevronRight className="h-4 w-4" /></button>
          <span className="mx-1 h-6 w-px bg-slate-200" />
          <button type="button" aria-label="Zoom out" disabled={scale <= 0.7} onClick={() => setScale((value) => Math.max(0.7, value - 0.15))} className="rounded-md border border-slate-200 p-2 disabled:opacity-40"><Minus className="h-4 w-4" /></button>
          <button type="button" aria-label="Zoom in" disabled={scale >= 2} onClick={() => setScale((value) => Math.min(2, value + 0.15))} className="rounded-md border border-slate-200 p-2 disabled:opacity-40"><Plus className="h-4 w-4" /></button>
        </div>
      </header>
      {targetPhrase && <div className="flex items-center gap-2 border-b border-sky-100 bg-sky-50 px-4 py-2 text-xs text-sky-900"><SearchCheck className="h-4 w-4 shrink-0" /><span className="line-clamp-2">Highlighted passage: {targetPhrase}</span></div>}
      <section className="relative flex min-h-0 flex-1 justify-center overflow-auto p-5">
        {status && <div className={`absolute left-1/2 top-5 z-10 flex max-w-[min(90%,48rem)] -translate-x-1/2 items-center gap-2 rounded-full border px-3 py-2 text-xs shadow-sm ${status.includes("could not be matched") ? "border-amber-200 bg-amber-50/95 text-amber-900" : "border-slate-200 bg-white/95 text-slate-600"}`}>{!status.includes("could not be matched") && <LoaderCircle className="h-4 w-4 shrink-0 animate-spin" />}{status}</div>}
        {error ? <div role="alert" className="m-auto max-w-md rounded-xl border border-rose-200 bg-white p-5 text-sm text-rose-800 shadow-sm">{error}</div> : <div ref={pageRef} className="relative m-auto shrink-0 bg-white shadow-lg ring-1 ring-slate-200">
          <canvas ref={canvasRef} className="block" />
          <div ref={textLayerRef} className="pdfEvidenceTextLayer textLayer" aria-label="PDF text layer" />
          <div className="pointer-events-none absolute inset-0 z-[2]" aria-hidden="true">{highlights.map((rect, index) => <span key={index} className="absolute rounded-sm bg-amber-300/55 outline outline-1 outline-amber-500/70" style={{ left: rect.left, top: rect.top, width: rect.width, height: rect.height }} />)}</div>
        </div>}
      </section>
      <style jsx global>{`
        .pdfEvidenceTextLayer { position:absolute; inset:0; overflow:hidden; opacity:1; line-height:1; transform-origin:0 0; }
        .pdfEvidenceTextLayer span { position:absolute; color:transparent; white-space:pre; cursor:text; transform-origin:0 0; }
        .pdfEvidenceTextLayer ::selection { background:rgba(56, 145, 255, .25); }
      `}</style>
    </main>
  );
}
