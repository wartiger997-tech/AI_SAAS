"use client";

import dynamic from "next/dynamic";
import { motion, useReducedMotion } from "framer-motion";
import { EASE } from "@/components/motion";

const HeroScene = dynamic(() => import("@/components/hero-scene"), {
  ssr: false,
  loading: () => (
    <div className="flex h-full w-full items-center justify-center">
      <div className="h-56 w-40 animate-pulse rounded-2xl bg-white/70 shadow-xl" />
    </div>
  ),
});

const POINTS = [
  "Page-level citations on every finding",
  "Tracked-changes DOCX in one click",
  "Your playbook, versioned and enforced",
];

export function Hero({
  onPrimary,
  onSecondary,
  primaryLabel = "Start a review",
  secondaryLabel = "Explore playbooks",
}: {
  onPrimary?: () => void;
  onSecondary?: () => void;
  primaryLabel?: string;
  secondaryLabel?: string;
}) {
  const reduce = useReducedMotion();
  return (
    <section className="relative overflow-hidden rounded-3xl border border-ink-200/70 bg-white px-6 py-10 shadow-card sm:px-10 sm:py-14">
      <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-brand-200/40 blur-3xl" />
      <div className="pointer-events-none absolute -bottom-32 -left-20 h-72 w-72 rounded-full bg-emerald-200/30 blur-3xl" />
      <div className="relative grid items-center gap-10 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <motion.span
            initial={reduce ? false : { opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: EASE }}
            className="inline-flex items-center gap-2 rounded-full border border-brand-100 bg-brand-50 px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-brand-700"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-75" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-600" />
            </span>
            Contract intelligence, cited
          </motion.span>

          <motion.h1
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.05 }}
            className="mt-5 text-4xl font-semibold tracking-tight text-ink-950 sm:text-5xl"
          >
            Review contracts at the{" "}
            <span className="bg-gradient-to-r from-brand-600 via-indigo-500 to-emerald-500 bg-clip-text text-transparent">
              speed of thought
            </span>
            .
          </motion.h1>

          <motion.p
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.12 }}
            className="mt-4 max-w-xl text-base leading-7 text-ink-500"
          >
            ClauseGuard extracts every clause, checks it against your playbook, and returns a
            reviewable redline — with the exact page and quote behind every finding.
          </motion.p>

          <motion.div
            initial={reduce ? false : { opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.55, ease: EASE, delay: 0.18 }}
            className="mt-7 flex flex-wrap gap-3"
          >
            <button
              type="button"
              onClick={onPrimary}
              className="group relative overflow-hidden rounded-xl bg-ink-950 px-5 py-3 text-sm font-semibold text-white shadow-lg shadow-ink-950/10 transition hover:-translate-y-0.5 hover:shadow-xl"
            >
              <span className="relative z-10">{primaryLabel}</span>
              <span className="absolute inset-0 -translate-x-full bg-gradient-to-r from-brand-600 to-indigo-500 transition-transform duration-300 group-hover:translate-x-0" />
            </button>
            <button
              type="button"
              onClick={onSecondary}
              className="rounded-xl border border-ink-200 bg-white px-5 py-3 text-sm font-semibold text-ink-700 transition hover:-translate-y-0.5 hover:border-ink-300 hover:bg-ink-50"
            >
              {secondaryLabel}
            </button>
          </motion.div>

          <motion.ul
            initial={reduce ? false : { opacity: 0 }}
            animate={{ opacity: 1 }}
            transition={{ duration: 0.6, delay: 0.3 }}
            className="mt-7 grid gap-2 text-sm text-ink-600 sm:grid-cols-1"
          >
            {POINTS.map((point) => (
              <li key={point} className="flex items-center gap-2">
                <span className="grid h-5 w-5 place-items-center rounded-full bg-emerald-50 text-emerald-600">
                  <svg viewBox="0 0 20 20" fill="none" className="h-3 w-3">
                    <path d="m5 10 3 3 7-7" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" />
                  </svg>
                </span>
                {point}
              </li>
            ))}
          </motion.ul>
        </div>

        <motion.div
          initial={reduce ? false : { opacity: 0, scale: 0.96 }}
          animate={{ opacity: 1, scale: 1 }}
          transition={{ duration: 0.7, ease: EASE, delay: 0.15 }}
          className="relative h-[360px] sm:h-[420px]"
        >
          <div className="absolute inset-0 rounded-[2rem] bg-gradient-to-br from-brand-50 via-white to-emerald-50/60 ring-1 ring-ink-200/60" />
          <div className="absolute inset-0 opacity-[0.35] [background-image:linear-gradient(to_right,rgba(27,32,41,.08)_1px,transparent_1px),linear-gradient(to_bottom,rgba(27,32,41,.08)_1px,transparent_1px)] [background-size:28px_28px]" />
          <HeroScene className="relative h-full w-full" />
          <div className="absolute bottom-4 left-4 right-4 flex items-center justify-between rounded-xl border border-white/60 bg-white/80 px-3 py-2 text-[11px] font-medium text-ink-600 backdrop-blur">
            <span className="flex items-center gap-1.5">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Citation verified
            </span>
            <span className="font-mono text-ink-400">p. 12 · § 4.2</span>
          </div>
        </motion.div>
      </div>
    </section>
  );
}