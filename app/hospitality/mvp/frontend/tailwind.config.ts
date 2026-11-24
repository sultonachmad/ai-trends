import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--sd-font, var(--font-sans))", "system-ui", "sans-serif"],
        stay: ["var(--font-stay)", "-apple-system", "system-ui", "Roboto", "sans-serif"],
      },
      // Public booking page tokens, from DESIGN.md. Staff screens keep the Ttest theme.
      fontSize: {
        "type-display-xl": ["28px", { lineHeight: "1.4", fontWeight: "700" }],
        "type-display-lg": ["22px", { lineHeight: "1.16", fontWeight: "500", letterSpacing: "-0.44px" }],
        "type-display-md": ["21px", { lineHeight: "1.4", fontWeight: "700" }],
        "type-display-sm": ["20px", { lineHeight: "1.18", fontWeight: "600", letterSpacing: "-0.18px" }],
        "type-title": ["16px", { lineHeight: "1.25", fontWeight: "600" }],
        "type-body": ["16px", { lineHeight: "1.5", fontWeight: "400" }],
        "type-body-sm": ["14px", { lineHeight: "1.43", fontWeight: "400" }],
        "type-caption": ["14px", { lineHeight: "1.29", fontWeight: "500" }],
        "type-caption-sm": ["13px", { lineHeight: "1.23", fontWeight: "400" }],
        "type-micro": ["12px", { lineHeight: "1.33", fontWeight: "700" }],
        "type-badge": ["11px", { lineHeight: "1.18", fontWeight: "600" }],
        "type-button": ["16px", { lineHeight: "1.25", fontWeight: "500" }],
      },
      borderRadius: {
        "stay-sm": "8px",
        "stay-md": "14px",
      },
      boxShadow: {
        stay: "rgba(0, 0, 0, 0.02) 0 0 0 1px, rgba(0, 0, 0, 0.04) 0 2px 6px 0, rgba(0, 0, 0, 0.1) 0 4px 8px 0",
      },
      colors: {
        stay: {
          primary: "#0f766e",
          "primary-active": "#115e59",
          "primary-disabled": "#a7d5cf",
          error: "#c13515",
          ink: "#222222",
          body: "#3f3f3f",
          muted: "#6a6a6a",
          "muted-soft": "#929292",
          hairline: "#dddddd",
          "hairline-soft": "#ebebeb",
          "border-strong": "#c1c1c1",
          canvas: "#ffffff",
          "surface-soft": "#f7f7f7",
          "surface-strong": "#f2f2f2",
          "on-primary": "#ffffff",
        },
        background: "var(--background)",
        foreground: "var(--foreground)",
        primary: {
          DEFAULT: "var(--primary-color)",
          hover: "var(--primary-hover-color)",
          foreground: "var(--primary-foreground)",
        },
        secondary: {
          DEFAULT: "var(--secondary-color)",
          foreground: "var(--secondary-foreground)",
        },
        border: "var(--input-border)",
        input: "var(--input-bg)",
        card: {
          DEFAULT: "var(--sub-section-bg)",
          foreground: "var(--card-foreground)",
        },
        muted: {
          DEFAULT: "var(--main-section-bg)",
          foreground: "var(--secondary-color)",
        },
        accent: {
          DEFAULT: "var(--aside-active-bg)",
          foreground: "var(--aside-active-text)",
        },
        destructive: {
          DEFAULT: "var(--delete-button-text)",
          foreground: "var(--destructive-foreground)",
        },
        aside: {
          DEFAULT: "var(--aside-bg)",
          text: "var(--aside-text)",
          muted: "var(--aside-text-muted)",
          border: "var(--aside-border)",
          hover: "var(--aside-hover-bg)",
          active: "var(--aside-active-bg)",
          "active-text": "var(--aside-active-text)",
        },
      },
    },
  },
  plugins: [],
};

export default config;
