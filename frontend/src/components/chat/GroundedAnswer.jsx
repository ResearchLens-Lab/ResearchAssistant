"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { CitationBadge } from "@/components/citations/CitationBadge";
import { parseTextWithCitations } from "@/utils/citationParser";

export function GroundedAnswer({ content, sources, compact = false }) {
  const renderTextWithCitations = (text) => {
    const segments = parseTextWithCitations(text);
    return segments.map((seg, i) => {
      if (seg.type === "citation") {
        return (
          <CitationBadge
            key={`${seg.sourceId}-${i}`}
            sourceId={seg.sourceId}
            source={sources?.find((s) => s.source_id === seg.sourceId)}
          />
        );
      }
      return <React.Fragment key={i}>{seg.content}</React.Fragment>;
    });
  };

  return (
    <div className={`prose prose-zinc prose-sm max-w-none text-zinc-900 leading-relaxed dark:prose-invert dark:text-zinc-100 font-sans ${compact ? "prose-h1:mb-4 prose-h1:mt-0 prose-h1:text-2xl prose-h1:leading-tight prose-h2:mb-2 prose-h2:mt-5 prose-h2:text-lg prose-h2:leading-snug prose-h3:mb-2 prose-h3:mt-4 prose-h3:text-base prose-pre:max-w-full prose-pre:overflow-x-auto prose-pre:whitespace-pre-wrap prose-pre:break-words prose-pre:border prose-pre:border-slate-200 prose-pre:bg-slate-50 prose-pre:text-slate-800 prose-code:text-inherit" : ""}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          pre: ({ children }) => compact ? <pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-slate-200 bg-slate-50 p-3 font-sans text-xs leading-5 text-slate-800">{children}</pre> : <pre>{children}</pre>,
          code: ({ children }) => compact ? <code className="rounded bg-slate-100 px-1 font-mono text-inherit before:content-none after:content-none">{children}</code> : <code>{children}</code>,
          p: ({ children }) => {
            if (typeof children === "string") {
              return <p className="mb-2.5">{renderTextWithCitations(children)}</p>;
            }
            return (
              <p className="mb-2.5">
                {React.Children.map(children, (child) => {
                  if (typeof child === "string") {
                    return renderTextWithCitations(child);
                  }
                  return child;
                })}
              </p>
            );
          },
          li: ({ children }) => {
            return (
              <li className="my-0.5">
                {React.Children.map(children, (child) => {
                  if (typeof child === "string") {
                    return renderTextWithCitations(child);
                  }
                  return child;
                })}
              </li>
            );
          },
          table: ({ children }) => (
            <div className="my-3 overflow-x-auto rounded-lg border border-zinc-200 bg-white shadow-2xs dark:border-zinc-800 dark:bg-zinc-900">
              <table className="w-full text-xs text-left">{children}</table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border-b border-zinc-200 bg-zinc-50 px-3 py-2 text-[11px] font-semibold text-zinc-600 uppercase tracking-wider dark:border-zinc-800 dark:bg-zinc-800 dark:text-zinc-300">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border-b border-zinc-100 px-3 py-2 align-top text-xs text-zinc-800 dark:border-zinc-800/60 dark:text-zinc-200">
              {children}
            </td>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
