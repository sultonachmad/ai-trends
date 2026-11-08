import { redirect } from "next/navigation";

/**
 * /admin — redirects to /admin/users as the default admin landing page.
 *
 * This is a Server Component (no "use client") so the redirect runs before
 * any HTML is sent to the browser.
 */
export default function AdminPage() {
  redirect("/admin/users");
}
