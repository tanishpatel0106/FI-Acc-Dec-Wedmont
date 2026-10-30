"use client";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { motion } from "motion/react";
import { useState } from "react";
import {
  IconBook2, IconChartAreaLine, IconChartDots3, IconFlask2, IconGitCompare, IconHistory, IconLayoutDashboard,
  IconMoon, IconSun, IconTable, IconTimeline, IconWaveSine,
} from "@tabler/icons-react";
import { useTheme } from "next-themes";
import { Sidebar, SidebarBody, useSidebar } from "@/components/ui/sidebar";
import { CommandBar } from "./CommandBar";
import { DataBadge } from "./DataBadge";
import { cn } from "@/lib/utils";

export const NAV = [
  { href: "/", label: "Overview", icon: IconLayoutDashboard },
  { href: "/lab", label: "01 Research Lab", icon: IconChartDots3 },
  { href: "/lab/fixed-income", label: "Fixed Income", icon: IconWaveSine },
  { href: "/simulate", label: "02 Lifecycle Simulator", icon: IconChartAreaLine },
  { href: "/optimize", label: "03 Policy Optimizer", icon: IconFlask2 },
  { href: "/withdrawal-lab", label: "04 Withdrawal Lab", icon: IconTable },
  { href: "/compare", label: "05 Compare & Validate", icon: IconGitCompare },
  { href: "/runs", label: "Runs & Reports", icon: IconHistory },
  { href: "/methodology", label: "Methodology", icon: IconBook2 },
];

function NavLink({ href, label, Icon, active }: { href: string; label: string; Icon: typeof IconBook2; active: boolean }) {
  const { open, animate } = useSidebar();
  return (
    <Link
      href={href}
      className={cn(
        "group/sidebar flex items-center gap-2 rounded-md px-2 py-2 text-sm transition-colors",
        active ? "bg-foreground/10 text-foreground" : "text-muted-foreground hover:bg-foreground/5 hover:text-foreground",
      )}
    >
      <Icon className="h-5 w-5 shrink-0" stroke={1.6} />
      <motion.span
        animate={{ display: animate ? (open ? "inline-block" : "none") : "inline-block", opacity: animate ? (open ? 1 : 0) : 1 }}
        className="whitespace-pre"
      >
        {label}
      </motion.span>
    </Link>
  );
}

function Logo() {
  const { open, animate } = useSidebar();
  return (
    <Link href="/" className="flex items-center gap-2 px-1 py-1">
      <IconTimeline className="h-6 w-6 shrink-0 text-[var(--viz-s1)]" stroke={1.8} />
      <motion.span
        animate={{ display: animate ? (open ? "inline-block" : "none") : "inline-block", opacity: animate ? (open ? 1 : 0) : 1 }}
        className="font-semibold tracking-[0.2em] text-foreground"
      >
        LIFECYCLE
      </motion.span>
    </Link>
  );
}

function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const dark = resolvedTheme !== "light";
  return (
    <button
      aria-label="Toggle theme"
      onClick={() => setTheme(dark ? "light" : "dark")}
      className="rounded-md border border-border p-1.5 text-muted-foreground hover:text-foreground"
    >
      {dark ? <IconSun className="h-4 w-4" /> : <IconMoon className="h-4 w-4" />}
    </button>
  );
}

export function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  return (
    <div className="flex min-h-screen w-full flex-col md:flex-row">
      <Sidebar open={open} setOpen={setOpen}>
        <SidebarBody className="justify-between gap-6 border-r border-border bg-sidebar md:sticky md:top-0 md:h-screen">
          <div className="flex flex-1 flex-col overflow-y-auto overflow-x-hidden">
            <Logo />
            <nav className="mt-6 flex flex-col gap-1">
              {NAV.map((n) => (
                <NavLink key={n.href} href={n.href} label={n.label} Icon={n.icon}
                  active={n.href === "/" ? pathname === "/" : pathname === n.href || (n.href !== "/lab" && pathname.startsWith(n.href))} />
              ))}
            </nav>
          </div>
        </SidebarBody>
      </Sidebar>
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-40 flex h-14 shrink-0 items-center gap-3 border-b border-border bg-background/80 px-4 backdrop-blur">
          <CommandBar />
          <div className="ml-auto flex items-center gap-2">
            <DataBadge />
            <ThemeToggle />
          </div>
        </header>
        <main className="flex-1">
          <div className="mx-auto w-full max-w-[1400px] px-4 py-6 md:px-8">{children}</div>
          <footer className="border-t border-border px-8 py-3 text-[11px] text-muted-foreground">
            Research output only — not investment advice. Every figure is computed server-side and is reproducible
            from its run ID and data catalog hash. Raw WRDS observations never leave the research host.
          </footer>
        </main>
      </div>
    </div>
  );
}
