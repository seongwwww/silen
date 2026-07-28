"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const TABS = [
  { href: "/", label: "오늘", mark: "○" },
  { href: "/diary", label: "일기", mark: "▤" },
  { href: "/settings", label: "설정", mark: "···" },
] as const;

function isActive(pathname: string, href: string): boolean {
  return href === "/" ? pathname === "/" : pathname.startsWith(href);
}

export function TabBar() {
  const pathname = usePathname();

  return (
    <nav
      aria-label="주요 화면"
      className="fixed inset-x-0 bottom-0 z-50 border-t bg-background/95 backdrop-blur"
    >
      <div className="mx-auto grid h-14 max-w-lg grid-cols-3 px-4">
        {TABS.map((tab) => {
          const active = isActive(pathname, tab.href);
          return (
            <Link
              key={tab.href}
              href={tab.href}
              aria-current={active ? "page" : undefined}
              className={[
                "flex min-h-11 flex-col items-center justify-center gap-0.5 text-xs transition-colors",
                active
                  ? "font-semibold text-foreground"
                  : "text-muted-foreground hover:text-foreground",
              ].join(" ")}
            >
              <span aria-hidden="true" className="text-base leading-none">
                {tab.mark}
              </span>
              {tab.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
