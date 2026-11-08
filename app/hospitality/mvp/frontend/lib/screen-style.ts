import raw from "@/screen-style.json";

export type NavPosition = "sidebar" | "topnav" | "minimal";

/** frontend/screen-style.json, written by Ttest at install (null = the theme's own look). */
export interface ScreenStyleFile {
  version: 1;
  preset?: string | null;
  navigation: NavPosition | null;
  appearance: "light" | "dark" | null;
  app_name: string | null;
  logo: "none" | "monogram" | "image" | null;
  logo_path: string | null;
  monogram: string | null;
  fingerprint: string | null;
}

export const screenStyle = raw as ScreenStyleFile;
