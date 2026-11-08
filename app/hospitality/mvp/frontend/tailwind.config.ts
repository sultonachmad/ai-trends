import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["var(--sd-font, var(--font-sans))", "system-ui", "sans-serif"],
      },
      colors: {
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
