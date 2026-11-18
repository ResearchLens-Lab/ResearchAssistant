/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    "./src/pages/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/components/**/*.{js,ts,jsx,tsx,mdx}",
    "./src/app/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  safelist: ["slide-in-from-top-2", "slide-in-from-bottom-2"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar-background))",
          foreground: "hsl(var(--sidebar-foreground))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-foreground": "hsl(var(--sidebar-primary-foreground))",
          accent: "hsl(var(--sidebar-accent))",
          "accent-foreground": "hsl(var(--sidebar-accent-foreground))",
          border: "hsl(var(--sidebar-border))",
          ring: "hsl(var(--sidebar-ring))",
        },
        zinc: {
          50: "#f6f9fc",
          100: "#eef3f8",
          200: "#dce6ef",
          300: "#c3d2e0",
          400: "#6f8398",
          500: "#62758a",
          600: "#4a5d72",
          700: "#384b60",
          800: "#2a3d52",
          900: "#203449",
          950: "#14233a",
        },
        slate: {
          50: "#f6f9fc",
          100: "#eef3f8",
          200: "#dce6ef",
          300: "#c3d2e0",
          400: "#6f8398",
          500: "#62758a",
          600: "#4a5d72",
          700: "#384b60",
          800: "#2a3d52",
          900: "#203449",
          950: "#14233a",
        },
      },
      boxShadow: {
        "2xs": "0 1px 1px 0 rgb(0 0 0 / 0.05)",
      },
      backdropBlur: {
        xs: "2px",
      },
      spacing: {
        4.5: "1.125rem",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      fontFamily: {
        sans: ["var(--font-sans)"],
        mono: ["var(--font-mono)"],
        serif: ["Georgia", "Cambria", "'Times New Roman'", "Times", "serif"],
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
        pulseHighlight: {
          "0%, 100%": { boxShadow: "0 0 0 0 rgba(59, 130, 246, 0)" },
          "50%": { boxShadow: "0 0 0 4px rgba(59, 130, 246, 0.35)" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
        highlight: "pulseHighlight 1.8s ease-in-out infinite",
      },
    },
  },
  plugins: [require("@tailwindcss/typography"), require("tailwindcss-animate")],
};
