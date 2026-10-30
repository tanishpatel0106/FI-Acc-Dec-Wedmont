"use client";
// Adapted from Aceternity UI "Expandable Card" (free registry demo): shared-layout expansion into a
// modal card with Escape / outside-click to close. Generalised to arbitrary content.
import React, { useEffect, useRef } from "react";
import { AnimatePresence, motion } from "motion/react";
import { useOutsideClick } from "@/hooks/use-outside-click";

export function ExpandableCard({
  open,
  layoutId,
  onClose,
  children,
  className,
}: {
  open: boolean;
  layoutId: string;
  onClose: () => void;
  children: React.ReactNode;
  className?: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [onClose]);
  useOutsideClick(ref as React.RefObject<HTMLDivElement>, () => open && onClose());
  return (
    <AnimatePresence>
      {open ? (
        <>
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
            className="fixed inset-0 z-[90] h-full w-full bg-black/50 backdrop-blur-sm" />
          <div className="fixed inset-0 z-[100] grid place-items-center p-2 md:p-6">
            <motion.div
              layoutId={layoutId}
              ref={ref}
              className={
                "flex max-h-[94vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl border border-border bg-background shadow-2xl " +
                (className ?? "")
              }
            >
              <div className="flex justify-end p-2">
                <button onClick={onClose} className="rounded-full border border-border px-2 py-0.5 text-xs text-muted-foreground hover:text-foreground">
                  Close (Esc)
                </button>
              </div>
              <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="overflow-y-auto px-4 pb-5 md:px-6">
                {children}
              </motion.div>
            </motion.div>
          </div>
        </>
      ) : null}
    </AnimatePresence>
  );
}
