import type { Metadata } from "next";
import type { ReactNode } from "react";
import { AuthProvider } from "@/components/auth";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  title: "ClauseGuard — contract review console",
  description:
    "Upload contracts, review playbook findings with page citations, and export tracked-changes redlines.",
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en">
      <body>
        <AuthProvider>
          <Shell>{children}</Shell>
        </AuthProvider>
      </body>
    </html>
  );
}