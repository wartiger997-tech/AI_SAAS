import Link from "next/link";

export default function NotFound() {
  return (
    <div className="mx-auto flex min-h-[60vh] max-w-md flex-col items-center justify-center text-center">
      <p className="font-mono text-6xl font-semibold tracking-tight text-ink-200">404</p>
      <h1 className="mt-3 text-lg font-semibold text-ink-950">Page not found</h1>
      <p className="mt-1 text-sm text-ink-500">
        The review or document you are looking for may have moved.
      </p>
      <Link
        href="/"
        className="mt-5 rounded-xl bg-ink-950 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-ink-800"
      >
        Back to overview
      </Link>
    </div>
  );
}