import type { Metadata, Viewport } from "next";
import type { ReactNode } from "react";
import { AuthProvider } from "@/components/auth";
import { Shell } from "@/components/shell";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL(process.env.NEXT_PUBLIC_SITE_URL || "https://clauseguard.vercel.app"),
  title: {
    default: "ClauseGuard — contract review, cited",
    template: "%s · ClauseGuard",
  },
  description:
    "Upload contracts, review playbook findings with page-level citations, and export tracked-changes redlines in minutes.",
  applicationName: "ClauseGuard",
  keywords: ["contract review", "legal AI", "redlining", "playbook", "RFP analysis"],
  openGraph: {
    title: "ClauseGuard — contract review, cited",
    description:
      "Every finding cites the page. Every redline is reviewable and exportable as tracked changes.",
    type: "website",
    siteName: "ClauseGuard",
  },
  twitter: {
    card: "summary_large_image",
    title: "ClauseGuard — contract review, cited",
    description: "Page-cited contract review and tracked-changes redlines.",
  },
  robots: { index: true, follow: true },
};

export const viewport: Viewport = {
  themeColor: "#11151c",
  width: "device-width",
  initialScale: 1,
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