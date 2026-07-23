"use client";

import { useState, useRef, useCallback, type ReactNode } from "react";
import { Eye, MessagesSquare } from "lucide-react";
import { cn } from "@/lib/utils";

interface SplitPaneProps {
  left: ReactNode;
  right: ReactNode;
  defaultSplit?: number;
}

export function SplitPane({ left, right, defaultSplit = 40 }: SplitPaneProps) {
  const [split, setSplit] = useState(defaultSplit);
  const [mobilePane, setMobilePane] = useState<"activity" | "preview">("activity");
  const containerRef = useRef<HTMLDivElement>(null);
  const dragging = useRef(false);

  const onMouseDown = useCallback(() => {
    dragging.current = true;
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";

    const onMouseMove = (e: MouseEvent) => {
      const rect = containerRef.current!.getBoundingClientRect();
      const pct = ((e.clientX - rect.left) / rect.width) * 100;
      setSplit(Math.min(Math.max(pct, 20), 80));
    };

    const onMouseUp = () => {
      dragging.current = false;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
      window.removeEventListener("mousemove", onMouseMove);
      window.removeEventListener("mouseup", onMouseUp);
    };

    window.addEventListener("mousemove", onMouseMove);
    window.addEventListener("mouseup", onMouseUp);
  }, []);

  return (
    <div ref={containerRef} className="relative flex h-full flex-col overflow-hidden md:flex-row">
      <div className="flex h-11 shrink-0 items-center gap-1 border-b border-border bg-surface/50 p-1.5 md:hidden" role="tablist" aria-label="Workspace view">
        <button
          type="button"
          role="tab"
          aria-selected={mobilePane === "activity"}
          onClick={() => setMobilePane("activity")}
          className={cn("flex min-h-8 flex-1 items-center justify-center gap-2 rounded-md text-xs font-medium", mobilePane === "activity" ? "bg-background text-foreground" : "text-muted")}
        >
          <MessagesSquare className="h-3.5 w-3.5" aria-hidden="true" />
          Activity
        </button>
        <button
          type="button"
          role="tab"
          aria-selected={mobilePane === "preview"}
          onClick={() => setMobilePane("preview")}
          className={cn("flex min-h-8 flex-1 items-center justify-center gap-2 rounded-md text-xs font-medium", mobilePane === "preview" ? "bg-background text-foreground" : "text-muted")}
        >
          <Eye className="h-3.5 w-3.5" aria-hidden="true" />
          Preview
        </button>
      </div>
      <div
        style={{ width: `${split}%` }}
        className={cn("min-h-0 flex-1 flex-shrink-0 overflow-hidden max-md:!w-full md:flex-none", mobilePane !== "activity" && "max-md:hidden")}
        role="tabpanel"
      >
        {left}
      </div>
      <div
        className="hidden w-1 flex-shrink-0 cursor-col-resize bg-border transition-colors hover:bg-accent/50 focus:bg-accent/50 focus:outline-none md:block"
        onMouseDown={onMouseDown}
        role="separator"
        aria-label="Resize activity and preview panels"
        aria-orientation="vertical"
        aria-valuemin={20}
        aria-valuemax={80}
        aria-valuenow={Math.round(split)}
        tabIndex={0}
        onKeyDown={(event) => {
          if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
          event.preventDefault();
          setSplit((value) => Math.min(80, Math.max(20, value + (event.key === "ArrowRight" ? 5 : -5))));
        }}
      />
      <div className={cn("min-h-0 flex-1 overflow-hidden", mobilePane !== "preview" && "max-md:hidden")} role="tabpanel">
        {right}
      </div>
    </div>
  );
}
