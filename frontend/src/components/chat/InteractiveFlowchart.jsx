"use client";

import React, { useMemo } from "react";
import { GitCommit, ArrowDown, Workflow } from "lucide-react";

export function InteractiveFlowchart({ code }) {
  const { nodes, edges } = useMemo(() => {
    if (!code) return { nodes: [], edges: [] };

    const lines = code.trim().split("\n");
    const nodeMap = new Map();
    const edgeList = [];

    let nodeIndex = 0;
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("flowchart") || trimmed.startsWith("graph")) continue;

      // Match edge: Node1 --> Node2
      const edgeMatch = trimmed.match(/^([A-Za-z0-9_-]+)\s*-->\s*([A-Za-z0-9_-]+)/);
      if (edgeMatch) {
        edgeList.push({ from: edgeMatch[1], to: edgeMatch[2] });
        continue;
      }

      // Match node declaration: Node1["Label text"] or Node1[Label text]
      const nodeMatch = trimmed.match(/^([A-Za-z0-9_-]+)\s*\[["']?([^"'\]]+)["']?\]/);
      if (nodeMatch) {
        nodeIndex++;
        nodeMap.set(nodeMatch[1], {
          id: nodeMatch[1],
          label: nodeMatch[2].trim(),
          step: nodeIndex,
        });
      }
    }

    return {
      nodes: Array.from(nodeMap.values()),
      edges: edgeList,
    };
  }, [code]);

  if (!nodes.length) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-500 font-serif">
        No flowchart nodes parsed from diagram specification.
      </div>
    );
  }

  return (
    <div className="my-4 rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm font-serif">
      {/* Flowchart Header */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-2.5 mb-4">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-sky-50 text-[#1d6fc4]">
            <Workflow className="h-3.5 w-3.5" />
          </span>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
            Process & Curriculum Flow ({nodes.length} stages)
          </span>
        </div>
        <span className="text-[10px] text-slate-400">Deterministic Flow Progression</span>
      </div>

      {/* Vertical Step Flow with Connecting Lines */}
      <div className="relative pl-6 sm:pl-8 space-y-3">
        {/* Continuous vertical timeline connector line */}
        <div className="absolute left-3.5 sm:left-4.5 top-3 bottom-5 w-0.5 bg-sky-200/70" />

        {nodes.map((node, index) => {
          const isLast = index === nodes.length - 1;
          return (
            <div key={node.id} className="relative group">
              {/* Step indicator node icon */}
              <div className="absolute -left-6 sm:-left-8 top-2.5 flex h-5 w-5 items-center justify-center rounded-full bg-white border-2 border-[#1d6fc4] text-[9px] font-bold text-[#1d6fc4] shadow-xs group-hover:bg-[#1d6fc4] group-hover:text-white transition-colors">
                {node.step}
              </div>

              {/* Node content card */}
              <div className="rounded-xl border border-slate-200/90 bg-slate-50/70 hover:bg-sky-50/60 hover:border-sky-300 p-3 transition-all duration-200 shadow-2xs">
                <div className="flex items-center justify-between gap-2 mb-0.5">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-sky-700">
                    Stage {node.step}
                  </span>
                  {!isLast && (
                    <span className="text-[10px] text-slate-400 flex items-center gap-0.5">
                      <span>Next</span>
                      <ArrowDown className="h-2.5 w-2.5 text-sky-500" />
                    </span>
                  )}
                </div>
                <h4 className="text-xs font-bold text-slate-900 leading-snug">
                  {node.label}
                </h4>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}

