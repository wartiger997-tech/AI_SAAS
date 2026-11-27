"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/documents", label: "Documents" },
  { href: "/playbooks", label: "Playbooks" },
  { href: "/search", label: "Precedent search" },
];

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className="flex flex-col gap-1">
      {LINKS.map((link) => {
        const active = link.href === "/" ? pathname === "/" : pathname.startsWith(link.href);
        return (
          <Link
            key={link.href}
            href={link.href}
            className={[
              "rounded-lg px-3 py-2 text-sm font-medium transition",
              active
                ? "bg-brand-50 text-brand-700 ring-1 ring-brand-100"
                : "text-ink-600 hover:bg-ink-50 hover:text-ink-900",
            ].join(" ")}
          >
            {link.label}
          </Link>
        );
      })}
    </nav>
  );
}