"use client";

import { useState, useRef, useEffect } from "react";
import { ChevronDown, Check } from "lucide-react";

type DashboardBuildMode = "build" | "goal";

const modes: { id: DashboardBuildMode; label: string; description: string; badge?: string }[] = [
  { id: "goal", label: "Auto build", description: "Plans and builds to completion", badge: "Recommended" },
  { id: "build", label: "Review steps", description: "Approve each planning phase" },
];

interface BuildModeDropdownProps {
  value: DashboardBuildMode;
  onChange: (mode: DashboardBuildMode) => void;
}

export function BuildModeDropdown({ value, onChange }: BuildModeDropdownProps) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    }
    if (open) document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, [open]);

  const current = modes.find((m) => m.id === value)!;

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-surface hover:bg-surface-hover text-sm font-medium text-foreground transition-colors cursor-pointer"
      >
        {current.label}
        <ChevronDown className="h-3.5 w-3.5 text-muted" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-2 w-56 rounded-xl border border-border bg-surface shadow-xl shadow-black/30 z-50 overflow-hidden animate-slide-up">
          {modes.map((m) => (
            <button
              key={m.id}
              type="button"
              onClick={() => {
                onChange(m.id);
                setOpen(false);
              }}
              className="flex items-start gap-3 w-full px-4 py-3 text-left hover:bg-surface-hover transition-colors cursor-pointer"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-medium text-foreground">{m.label}</span>
                  {m.badge && (
                    <span className="text-[10px] font-semibold px-1.5 py-0.5 rounded bg-accent/20 text-accent">
                      {m.badge}
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted mt-0.5">{m.description}</p>
              </div>
              {value === m.id && <Check className="h-4 w-4 text-accent mt-0.5 shrink-0" />}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

export type { DashboardBuildMode };
