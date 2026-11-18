"use client";

import React, { useState, useMemo } from "react";
import { PieChart as PieIcon, Check } from "lucide-react";

const PALETTE = [
  "#1d6fc4", // primary sky
  "#10b981", // emerald
  "#f59e0b", // amber
  "#6366f1", // indigo
  "#ec4899", // pink
  "#14b8a6", // teal
  "#8b5cf6", // violet
  "#06b6d4", // cyan
  "#f97316", // orange
  "#64748b", // slate
];

export function InteractivePieChart({ code }) {
  const [hoveredIdx, setHoveredIdx] = useState(null);

  const data = useMemo(() => {
    if (!code) return [];
    const lines = code.trim().split("\n");
    const items = [];
    for (const line of lines) {
      const trimmed = line.trim();
      if (!trimmed || trimmed.startsWith("//") || trimmed.startsWith("#")) continue;
      // Categories can contain colons themselves, e.g. "Section 1: Algebra": 94.
      // Match the delimiter that is followed by the numeric value.
      const match = trimmed.match(/^["']?(.*?)["']?\s*:\s*(\d+(?:\.\d+)?)\s*%?\s*$/);
      if (match) {
        items.push({
          label: match[1].trim(),
          value: parseFloat(match[2]),
        });
      }
    }
    return items;
  }, [code]);

  const total = useMemo(() => {
    return data.reduce((acc, curr) => acc + curr.value, 0);
  }, [data]);

  const slices = useMemo(() => {
    if (total <= 0) return [];
    let cumulativeAngle = -Math.PI / 2; // start from top (12 o'clock)
    return data.map((item, index) => {
      const angle = (item.value / total) * 2 * Math.PI;
      const startAngle = cumulativeAngle;
      const endAngle = cumulativeAngle + angle;
      const midAngle = startAngle + angle / 2;
      cumulativeAngle = endAngle;

      const percentage = ((item.value / total) * 100).toFixed(1);
      const color = PALETTE[index % PALETTE.length];

      return {
        ...item,
        startAngle,
        endAngle,
        midAngle,
        percentage,
        color,
        index,
      };
    });
  }, [data, total]);

  if (!data.length || total <= 0) {
    return (
      <div className="rounded-xl border border-slate-200 bg-slate-50 p-4 text-xs text-slate-500">
        No numeric proportions found for pie chart.
      </div>
    );
  }

  const cx = 110;
  const cy = 110;
  const outerR = 82;
  const innerR = 46;

  const activeSlice = hoveredIdx !== null ? slices[hoveredIdx] : null;

  return (
    <div className="my-4 rounded-2xl border border-slate-200/90 bg-white p-4 shadow-sm">
      {/* Chart Title / Toolbar */}
      <div className="flex items-center justify-between border-b border-slate-100 pb-2.5 mb-3">
        <div className="flex items-center gap-2">
          <span className="flex h-6 w-6 items-center justify-center rounded-lg bg-sky-50 text-[#1d6fc4]">
            <PieIcon className="h-3.5 w-3.5" />
          </span>
          <span className="text-xs font-bold uppercase tracking-wider text-slate-800">
            Document Content Distribution ({data.length} segments)
          </span>
        </div>
        <span className="text-[11px] text-slate-400">Proportions from selected source text</span>
      </div>

      <div className="flex flex-col md:flex-row items-center gap-6">
        {/* SVG Donut / Pie View */}
        <div className="relative shrink-0">
          <svg width={220} height={220} viewBox="0 0 220 220" className="overflow-visible">
            {slices.map((slice) => {
              const isHovered = hoveredIdx === slice.index;
              const offset = isHovered ? 6 : 0;
              const shiftX = Math.cos(slice.midAngle) * offset;
              const shiftY = Math.sin(slice.midAngle) * offset;

              // Outer arc points
              const x1 = cx + shiftX + outerR * Math.cos(slice.startAngle);
              const y1 = cy + shiftY + outerR * Math.sin(slice.startAngle);
              const x2 = cx + shiftX + outerR * Math.cos(slice.endAngle);
              const y2 = cy + shiftY + outerR * Math.sin(slice.endAngle);

              // Inner arc points
              const x3 = cx + shiftX + innerR * Math.cos(slice.endAngle);
              const y3 = cy + shiftY + innerR * Math.sin(slice.endAngle);
              const x4 = cx + shiftX + innerR * Math.cos(slice.startAngle);
              const y4 = cy + shiftY + innerR * Math.sin(slice.startAngle);

              const isLargeArc = slice.endAngle - slice.startAngle > Math.PI ? 1 : 0;

              const pathData = [
                `M ${x1} ${y1}`,
                `A ${outerR} ${outerR} 0 ${isLargeArc} 1 ${x2} ${y2}`,
                `L ${x3} ${y3}`,
                `A ${innerR} ${innerR} 0 ${isLargeArc} 0 ${x4} ${y4}`,
                "Z",
              ].join(" ");

              return (
                <path
                  key={slice.index}
                  d={pathData}
                  fill={slice.color}
                  stroke="#ffffff"
                  strokeWidth={2}
                  className="transition-all duration-200 cursor-pointer hover:opacity-90"
                  onMouseEnter={() => setHoveredIdx(slice.index)}
                  onMouseLeave={() => setHoveredIdx(null)}
                />
              );
            })}

            {/* Central Donut Hole Content */}
            <circle cx={cx} cy={cy} r={innerR - 2} fill="#ffffff" />
            <text
              x={cx}
              y={cy - 5}
              textAnchor="middle"
              className="fill-slate-800 text-[13px] font-bold"
            >
              {activeSlice ? `${activeSlice.percentage}%` : `${data.length}`}
            </text>
            <text
              x={cx}
              y={cy + 12}
              textAnchor="middle"
              className="fill-slate-400 text-[11px] font-medium"
            >
              {activeSlice ? "of scope" : "Sections"}
            </text>
          </svg>
        </div>

        {/* Legend / Breakdown List */}
        <div className="flex-1 w-full max-h-56 overflow-y-auto space-y-1.5 pr-1">
          {slices.map((slice) => {
            const isHovered = hoveredIdx === slice.index;
            return (
              <div
                key={slice.index}
                onMouseEnter={() => setHoveredIdx(slice.index)}
                onMouseLeave={() => setHoveredIdx(null)}
                className={`flex items-center justify-between rounded-lg px-2.5 py-1 text-xs transition-colors cursor-pointer ${
                  isHovered ? "bg-sky-50/80 ring-1 ring-sky-300" : "hover:bg-slate-50"
                }`}
              >
                <div className="flex items-center gap-2 min-w-0 pr-2">
                  <span
                    className="h-2.5 w-2.5 rounded-full shrink-0 shadow-2xs"
                    style={{ backgroundColor: slice.color }}
                  />
                  <span
                    className={`truncate font-medium ${
                      isHovered ? "text-[#1d6fc4] font-semibold" : "text-slate-700"
                    }`}
                    title={slice.label}
                  >
                    {slice.label}
                  </span>
                </div>
                <span className="shrink-0 font-mono text-[11px] text-slate-500 font-semibold">
                  {slice.percentage}%
                </span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
}

