"use client";

import React from "react";

export function ResearchLensLogo({ className = "h-5 w-5", size = 24, variant = "default" }) {
  const isInverse = variant === "inverse";
  const strokeColor = isInverse ? "#ffffff" : "#0284c7";
  const docStroke = isInverse ? "#38bdf8" : "#0369a1";

  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      aria-hidden="true"
    >
      <defs>
        <linearGradient id="rl-lens-ring" x1="2" y1="2" x2="16" y2="16" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#38bdf8" />
          <stop offset="100%" stopColor="#0284c7" />
        </linearGradient>
        <linearGradient id="rl-lens-fill" x1="3" y1="3" x2="15" y2="15" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#f0f9ff" stopOpacity="0.85" />
          <stop offset="100%" stopColor="#e0f2fe" stopOpacity="0.4" />
        </linearGradient>
      </defs>

      {/* Optical Lens Glass Body */}
      <circle
        cx="10"
        cy="10"
        r="7.5"
        fill="url(#rl-lens-fill)"
        stroke={isInverse ? "#ffffff" : "url(#rl-lens-ring)"}
        strokeWidth="1.75"
      />

      {/* Internal Document / Academic Page Geometry */}
      <path
        d="M8 6.75H11.25L13 8.5V13.25H8V6.75Z"
        fill={isInverse ? "#0369a1" : "#ffffff"}
        stroke={docStroke}
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
      {/* Page Fold Corner */}
      <path
        d="M11.25 6.75V8.5H13"
        fill="#bae6fd"
        stroke={docStroke}
        strokeWidth="1.1"
        strokeLinejoin="round"
      />
      {/* Research Passage Lines Inside Lens Focus */}
      <line x1="9.25" y1="9.75" x2="11.25" y2="9.75" stroke={isInverse ? "#ffffff" : "#0284c7"} strokeWidth="0.9" strokeLinecap="round" />
      <line x1="9.25" y1="11.5" x2="11.75" y2="11.5" stroke={isInverse ? "#ffffff" : "#0284c7"} strokeWidth="0.9" strokeLinecap="round" />

      {/* Optical Lens Precision Handle / Reticle */}
      <path
        d="M15.5 15.5L20.5 20.5"
        stroke={strokeColor}
        strokeWidth="2.2"
        strokeLinecap="round"
      />
      {/* Precision Optical Grip Detail */}
      <circle cx="18" cy="18" r="0.6" fill={isInverse ? "#0284c7" : "#ffffff"} />
    </svg>
  );
}

