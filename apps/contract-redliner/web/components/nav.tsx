"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "framer-motion";

const LINKS = [
  { href: "/", label: "Overview", icon: "M3 10.5 12 3l9 7.5V21H3z" },
  { href: "/documents", label: "Documents", icon: "M7 3h7l4 4v14H7zM14 3v5h5" },
  { href: "/playbooks", label: "Playbooks", icon: "M4 5h16v14H4zM8 9h8M8 13h5" },
  { href: "/search", label: "Precedent search", icon: "M11 4a7 7 0 1 0 0 14 7 7 0 0 0 0-14zm5 12 4 4" },
];

export function Nav({ compact = false }: { compact?: boolean }) {
  const pathname = usePathname();
  return (
    <nav className={compact ? "flex gap-1 overflow-x-auto" : "flex flex-col gap-1"}>
      {LINKS.map((link) => {
        const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={[
              "group relative flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition",
              compact ? "shrink-0" : "",
              active ? "text-brand-800" : "text-ink-500 hover:bg-ink-50 hover:text-ink-900",
            ].join(" ")}
          >
            {active && !compact && (
              <motion.span
                layoutId="nav-active"
                className="absolute inset-0 rounded-lg bg-brand-50 ring-1 ring-brand-100"
                transition={{ type: "spring", stiffness: 400, damping: 34 }}
              />
            )}
            <svg
              viewBox="0 0 24 24"
              fill="none"
              className={["relative h-4 w-4", active ? "text-brand-600" : "text-ink-400 group-hover:text-ink-600"].join(" ")}
            >
              <path d={link.icon} stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
            <span className="relative">{link.label}</span>
          </Link>
        );
      })}
    </nav>
  );
}