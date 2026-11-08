"use client";
import { LoginForm } from "@/components/LoginForm";
import { GoogleSSOForm } from "@/components/GoogleSSOForm";
import { MicrosoftSSOForm } from "@/components/MicrosoftSSOForm";
// PREFAB:login-imports

const APP_NAME = process.env.NEXT_PUBLIC_APP_NAME ?? "Ttest App";

export default function LoginPage() {

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 px-6 bg-main">
      <div className="flex flex-col items-center gap-2 text-center">
        <h1 className="text-2xl font-bold text-main-color">
          {APP_NAME}
        </h1>
        <p className="text-sm text-secondary-color">
          Sign in to continue
        </p>
      </div>


      <LoginForm />
      <GoogleSSOForm />
      <MicrosoftSSOForm />
      {/* PREFAB:login-extra */}
    </main>
  );
}
