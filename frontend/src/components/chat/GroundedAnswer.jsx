"use client";

import React from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { CitationBadge } from "@/components/citations/CitationBadge";
import { parseTextWithCitations } from "@/utils/citationParser";
import { buildCitationIndex, stripSourceLines } from "@/utils/citationNumbering.mjs";
import { InteractivePieChart } from "./InteractivePieChart";
import { InteractiveFlowchart } from "./InteractiveFlowchart";

function extractText(children) {
  if (typeof children === "string") return children;
  if (typeof children === "number") return String(children);
  if (Array.isArray(children)) {
    return children.map(extractText).join("");
  }
  if (React.isValidElement(children) && children.props?.children) {
    return extractText(children.props.children);
  }
  return "";
}

export function GroundedAnswer({
  rawContent,
  content: contentProp,
  sources,
  compact = false,
  autoSelectFirstCitation = false,
  question = "",
  researchPlan = null,
  messageId = null,
}) {
  const sourceInput = rawContent !== undefined ? rawContent : contentProp;
  const content = React.useMemo(() => stripSourceLines(sourceInput), [sourceInput]);
  const citationIndex = React.useMemo(() => buildCitationIndex(content, sources), [content, sources]);

  let currentHeading = "";
  let didAutoSelectCitation = false;
  const citationClaimsBySource = React.useMemo(() => {
    const claims = new Map();
    for (const line of (content || "").split("\n")) {
      const segments = parseTextWithCitations(line);
      segments.forEach((segment, index) => {
        if (segment.type !== "citation") return;
        let claim = (segments[index - 1]?.content || "")
          .replace(/^[-*+]\s+/, "")
          .replace(/\*\*/g, "")
          .trim();
        if (claim.startsWith("|")) {
          const cells = claim.split("|").map((cell) => cell.trim()).filter(Boolean);
          claim = cells.length > 1 ? cells[1] : claim;
        }
        if (claim.length < 8) return;
        const sourceClaims = claims.get(segment.sourceId) || [];
        sourceClaims.push(claim);
        claims.set(segment.sourceId, sourceClaims);
      });
    }
    return claims;
  }, [content]);

  const renderTextWithCitations = (text, heading = currentHeading) => {
    const segments = parseTextWithCitations(text);
    return segments.map((seg, i) => {
      if (seg.type === "citation") {
        const autoSelect = autoSelectFirstCitation && !didAutoSelectCitation;
        if (autoSelect) didAutoSelectCitation = true;
        const preceding = segments[i - 1]?.content || "";
        const cleanClaim = preceding
          .replace(/^[-*+]\s+/, "")
          .replace(/^[A-Za-z\s]+:\s*/, "") // remove prefixes like "Syllabus Coverage: "
          .replace(/\*\*([^*]+)\*\*/g, "$1")
          .replace(/^[“”"'`]+|[“”"'`]+$/g, "")
          .trim();

        const cleanHeading = (heading || "").trim();
        const highlight = {
          headingText: cleanHeading,
          claimText: cleanClaim,
          relatedClaimTexts: citationClaimsBySource.get(seg.sourceId) || [cleanClaim],
          fullText:
            cleanHeading && cleanClaim
              ? `${cleanHeading} ${cleanClaim}`
              : cleanHeading || cleanClaim,
        };

        return (
          <CitationBadge
            key={`${seg.sourceId}-${i}`}
            sourceId={seg.sourceId}
            source={sources?.find((s) => s.source_id === seg.sourceId)}
            highlight={highlight}
            autoSelect={autoSelect}
            question={question}
            researchPlan={researchPlan}
            number={citationIndex.numberById.get(seg.sourceId)}
            messageId={messageId}
          />
        );
      }
      return <React.Fragment key={i}>{seg.content}</React.Fragment>;
    });
  };

  const mapWithCitations = (children, heading) => {
    return React.Children.map(children, (child) => {
      if (typeof child === "string") {
        return renderTextWithCitations(child, heading);
      }
      if (React.isValidElement(child) && child.props?.children) {
        return React.cloneElement(child, {
          children: mapWithCitations(child.props.children, heading),
        });
      }
      return child;
    });
  };

  return (
    <div
      className={`prose prose-zinc prose-sm max-w-none text-zinc-900 leading-relaxed dark:prose-invert dark:text-zinc-100 font-sans prose-blockquote:border-l-2 prose-blockquote:border-primary/40 prose-blockquote:pl-3 prose-blockquote:italic prose-blockquote:before:content-none prose-blockquote:after:content-none ${
        compact
          ? "prose-h1:mb-4 prose-h1:mt-0 prose-h1:text-2xl prose-h1:leading-tight prose-h2:mb-2 prose-h2:mt-5 prose-h2:text-lg prose-h2:leading-snug prose-h3:mb-2 prose-h3:mt-4 prose-h3:text-base prose-pre:max-w-full prose-pre:overflow-x-auto prose-pre:whitespace-pre-wrap prose-pre:break-words prose-pre:border prose-pre:border-slate-200 prose-pre:bg-slate-50 prose-pre:text-slate-800 prose-code:text-inherit"
          : ""
      }`}
    >
      <ReactMarkdown
        remarkPlugins={[remarkGfm, remarkMath]}
        rehypePlugins={[rehypeKatex]}
        components={{
          h1: ({ children }) => {
            currentHeading = extractText(children);
            return <h1>{children}</h1>;
          },
          h2: ({ children }) => {
            currentHeading = extractText(children);
            return <h2>{children}</h2>;
          },
          h3: ({ children }) => {
            currentHeading = extractText(children);
            return <h3>{children}</h3>;
          },
          h4: ({ children }) => {
            currentHeading = extractText(children);
            return <h4>{children}</h4>;
          },
          pre: ({ children }) => {
            return <div className="not-prose my-2">{children}</div>;
          },
          code: ({ inline, className, children, ...props }) => {
            const matchLang = /language-(\w+)/.exec(className || "");
            const lang = matchLang ? matchLang[1].toLowerCase() : "";
            const textContent = String(children).replace(/\n$/, "");

            if (!inline && (lang === "pie" || lang === "chart")) {
              return <InteractivePieChart code={textContent} />;
            }
            if (!inline && (lang === "mermaid" || lang === "flowchart")) {
              return <InteractiveFlowchart code={textContent} />;
            }
            if (!inline) {
              return (
                <pre className="max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-xl border border-slate-200 bg-slate-50 p-3 font-mono text-xs leading-5 text-slate-800 shadow-2xs">
                  <code>{children}</code>
                </pre>
              );
            }
            return (
              <code className="rounded bg-slate-100 px-1.5 py-0.5 font-mono text-xs text-slate-800 before:content-none after:content-none" {...props}>
                {children}
              </code>
            );
          },
          p: ({ children }) => {
            const heading = currentHeading;
            return <p className="mb-2.5">{mapWithCitations(children, heading)}</p>;
          },
          li: ({ children }) => {
            const heading = currentHeading;
            return <li className="my-0.5">{mapWithCitations(children, heading)}</li>;
          },
          blockquote: ({ children }) => {
            const heading = currentHeading;
            return (
              <blockquote className="border-l-2 border-primary/40 pl-3 italic my-2 before:content-none after:content-none">
                {mapWithCitations(children, heading)}
              </blockquote>
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
          td: ({ children }) => {
            const heading = currentHeading;
            return (
              <td className="border-b border-zinc-100 px-3 py-2 align-top text-xs text-zinc-800 dark:border-zinc-800/60 dark:text-zinc-200">
                {mapWithCitations(children, heading)}
              </td>
            );
          },
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
