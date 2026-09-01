"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { CitationBadge } from "@/components/citations/CitationBadge";
import { parseTextWithCitations } from "@/utils/citationParser";

export function GroundedAnswer({ content, sources }) {
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
    <div className="prose prose-zinc prose-sm max-w-none text-zinc-900 leading-relaxed dark:prose-invert dark:text-zinc-100 font-sans">
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
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
