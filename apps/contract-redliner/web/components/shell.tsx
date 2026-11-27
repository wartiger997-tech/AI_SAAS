"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { LoginPanel, useAuth } from "@/components/auth";
import { Nav } from "@/components/nav";

export function Shell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center text-sm text-ink-500">
        Loading workspace…
      </div>
    );
  }

  if (!user) return <div className="min-h-screen bg-ink-50 px-4"><LoginPanel /></div>;

  return (
    <div className="min-h-screen bg-ink-50">
      <aside className="fixed inset-y-0 left-0 hidden w-60 flex-col border-r border-ink-200 bg-white px-4 py-5 lg:flex">
        <Link href="/" className="flex items-center gap-2 px-2">
          <span className="grid h-8 w-8 place-items-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            CG
          </span>
          <span className="text-sm font-semibold text-ink-900">ClauseGuard</span>
        </Link>
        <div className="mt-8">
          <Nav />
        </div>
        <div className="mt-auto border-t border-ink-100 pt-4">
          <p className="truncate px-2 text-xs font-medium text-ink-700">{user.full_name || user.email}</p>
          <p className="truncate px-2 text-xs text-ink-400">{user.role}</p>
          <button
            type="button"
            onClick={logout}
            className="mt-2 w-full rounded-lg px-2 py-1.5 text-left text-xs font-medium text-ink-500 hover:bg-ink-50"
          >
            Sign out
          </button>
        </div>
      </aside>
      <div className="lg:pl-60">
        <header className="flex items-center justify-between border-b border-ink-200 bg-white px-5 py-3 lg:hidden">
          <Link href="/" className="text-sm font-semibold text-ink-900">ClauseGuard</Link>
          <button type="button" onClick={logout} className="text-xs text-ink-500">Sign out</button>
        </header>
        <main className="mx-auto max-w-6xl px-5 py-8">{children}</main>
      </div>
    </div>
  );
}