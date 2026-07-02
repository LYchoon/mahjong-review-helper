"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Click-to-toggle popover for supplementary explanations. Unlike a bare
 * `title` attribute this works for touch and keyboard users; Escape or an
 * outside click closes it.
 */
export function InfoPopover({
  label,
  buttonClass,
  children,
}: {
  label: React.ReactNode;
  buttonClass?: string;
  children: React.ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLSpanElement>(null);

  useEffect(() => {
    if (!open) return;
    function onPointerDown(e: MouseEvent | TouchEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("touchstart", onPointerDown);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("touchstart", onPointerDown);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <span ref={ref} className="relative inline-block">
      <button
        type="button"
        aria-expanded={open}
        onClick={() => setOpen((v) => !v)}
        className={buttonClass}
      >
        {label}
      </button>
      {open && (
        <span
          role="tooltip"
          className="absolute z-20 bottom-full left-0 mb-1 w-64 max-w-[80vw] bg-stone-950 border border-stone-600 rounded p-2 text-xs text-stone-200 shadow-lg whitespace-pre-line block text-left"
        >
          {children}
        </span>
      )}
    </span>
  );
}
