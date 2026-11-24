import { Inter } from "next/font/google";
import type { ReactNode } from "react";

const inter = Inter({ subsets: ["latin"], variable: "--font-stay" });

/** Full-bleed white canvas for the guest-facing page; cancels the root layout's padding. */
export default function BookingPageLayout({ children }: { children: ReactNode }) {
  return (
    <div
      className={`${inter.variable} -mx-6 -my-8 min-h-screen bg-stay-canvas font-stay text-type-body text-stay-ink antialiased md:-mx-10`}
    >
      {children}
    </div>
  );
}
