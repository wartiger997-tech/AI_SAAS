"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { LoginPanel, useAuth } from "@/components/auth";
import { Nav } from "@/components/nav";

export function Shell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const pathname = usePathname();
  const reduce = useReducedMotion();

  if (loading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-ink-50">
        <div className="flex flex-col items-center gap-3">
          <div className="h-10 w-10 animate-spin rounded-full border-2 border-ink-200 border-t-brand-600" />
          <p className="text-sm text-ink-500">Loading workspace…</p>
        </div>
      </div>
    );
  }

  if (!user) return <LoginPanel />;

  return (
    <div className="min-h-screen bg-ink-50">
      <motion.div
        key={pathname}
        initial={reduce ? false : { scaleX: 0 }}
        animate={{ scaleX: 1 }}
        transition={{ duration: 0.45, ease: [0.22, 1, 0.36, 1] }}
        className="fixed inset-x-0 top-0 z-50 h-0.5 origin-left bg-gradient-to-r from-brand-500 via-indigo-500 to-emerald-500"
      />

      <aside className="fixed inset-y-0 left-0 z-40 hidden w-64 flex-col border-r border-ink-200/80 bg-white/80 px-4 py-5 backdrop-blur lg:flex">
        <Link href="/" className="flex items-center gap-2.5 px-2">
          <span className="grid h-9 w-9 place-items-center rounded-xl bg-ink-950 text-sm font-bold text-white shadow-lg shadow-ink-950/15">
            CG
          </span>
          <span className="leading-tight">
            <span className="block text-sm font-semibold tracking-tight text-ink-950">ClauseGuard</span>
            <span className="block text-[10px] font-medium uppercase tracking-[0.16em] text-ink-400">
              Contract review
            </span>
          </span>
        </Link>

        <Link
          href="/documents"
          className="mt-6 flex items-center justify-center gap-1.5 rounded-xl bg-ink-950 px-3 py-2.5 text-xs font-semibold text-white shadow-lg shadow-ink-950/10 transition hover:-translate-y-0.5 hover:bg-ink-800"
        >
          <span className="text-base leading-none">+</span> New review
        </Link>

        <div className="mt-6">
          <Nav />
        </div>

        <div className="mt-auto rounded-xl border border-ink-200/80 bg-white p-3">
          <div className="flex items-center gap-2.5">
            <span className="grid h-8 w-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-brand-500 to-indigo-600 text-[11px] font-bold text-white">
              {(user.full_name || user.email).slice(0, 2).toUpperCase()}
            </span>
            <div className="min-w-0">
              <p className="truncate text-xs font-semibold text-ink-900">{user.full_name || user.email}</p>
              <p className="truncate text-[11px] capitalize text-ink-400">{user.role}</p>
            </div>
          </div>
          <button
            type="button"
            onClick={logout}
            className="mt-2.5 w-full rounded-lg px-2 py-1.5 text-left text-[11px] font-medium text-ink-500 transition hover:bg-ink-50 hover:text-ink-700"
          >
            Sign out
          </button>
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-30 border-b border-ink-200/70 bg-ink-50/85 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between">
            <Link href="/" className="flex items-center gap-2">
              <span className="grid h-8 w-8 place-items-center rounded-lg bg-ink-950 text-xs font-bold text-white">CG</span>
              <span className="text-sm font-semibold text-ink-950">ClauseGuard</span>
            </Link>
            <button type="button" onClick={logout} className="text-xs font-medium text-ink-500">
              Sign out
            </button>
          </div>
          <div className="mt-2">
            <Nav compact />
          </div>
        </header>

        <main className="mx-auto w-full max-w-7xl px-4 py-7 sm:px-6 lg:px-8 lg:py-9">{children}</main>
      </div>
    </div>
  );
}