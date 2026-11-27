"use client";

import { motion } from "framer-motion";

export default function ErrorPage({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center text-center">
      <motion.div
        initial={{ opacity: 0, scale: 0.9 }}
        animate={{ opacity: 1, scale: 1 }}
        transition={{ duration: 0.4 }}
        className="grid h-14 w-14 place-items-center rounded-2xl bg-red-50 text-red-600"
      >
        <svg viewBox="0 0 24 24" fill="none" className="h-6 w-6">
          <path d="M12 8v5m0 3v.01M10.3 3.9 2.6 17.1A1.6 1.6 0 0 0 4 19.5h16a1.6 1.6 0 0 0 1.4-2.4L13.7 3.9a1.6 1.6 0 0 0-2.8 0Z" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" />
        </svg>
      </motion.div>
      <h1 className="mt-4 text-lg font-semibold text-ink-950">Something went wrong</h1>
      <p className="mt-1 text-sm text-ink-500">
        {error.message || "An unexpected error occurred while loading this view."}
      </p>
      {error.digest && <p className="mt-1 font-mono text-[10px] text-ink-400">ref {error.digest}</p>}
      <button
        type="button"
        onClick={reset}
        className="mt-5 rounded-xl bg-ink-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-800"
      >
        Try again
      </button>
    </div>
  );
}