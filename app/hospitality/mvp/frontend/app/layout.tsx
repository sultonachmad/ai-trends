import type { Metadata } from "next";
import { Space_Grotesk } from "next/font/google";
import "@/styles/globals.css";
import "@/styles/screen-style.css";
import { screenStyle } from "@/lib/screen-style";
import { Providers } from "@/app/providers";
import Sidebar from "@/components/Sidebar";

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-sans",
});

export const metadata: Metadata = {
  title: process.env.NEXT_PUBLIC_APP_NAME ?? "Ttest App",
  description: "Built with Ttest — AI-powered SDLC platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={screenStyle.appearance === "dark" ? "ttest dark" : "ttest"} suppressHydrationWarning>
      <body
        className={`${spaceGrotesk.variable} font-sans antialiased bg-main`}
      >
        <Providers>
          <Sidebar />
          {/* BDAI-2058: margin applied via CSS body:has(aside) so the login
              form stays centred when the Sidebar returns null on /login. */}
          <main className="min-h-screen px-6 py-8 md:px-10">
            {children}
          </main>
        </Providers>
      </body>
    </html>
  );
}
