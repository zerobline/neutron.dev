"use client";

import { AlertTriangle, XCircle, Info, Trash2, Wrench } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export interface ConsoleEntry {
  id: string;
  level: "error" | "warn" | "info";
  message: string;
  timestamp: number;
}

interface ConsolePanelProps {
  entries: ConsoleEntry[];
  onClear: () => void;
  onResolve: (entry: ConsoleEntry) => void;
}

const levelIcon = {
  error: XCircle,
  warn: AlertTriangle,
  info: Info,
};

const levelColor = {
  error: "text-red-400",
  warn: "text-yellow-400",
  info: "text-blue-400",
};

export function ConsolePanel({ entries, onClear, onResolve }: ConsolePanelProps) {
  if (entries.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-sm text-muted">
        <Info className="h-8 w-8 mb-2 opacity-40" />
        No console output yet.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="text-xs text-muted">
          {entries.length} message{entries.length !== 1 && "s"}
        </span>
        <Button variant="ghost" size="sm" onClick={onClear} className="h-6 px-2 text-xs">
          <Trash2 className="h-3 w-3 mr-1" />
          Clear
        </Button>
      </div>
      <div className="flex-1 overflow-y-auto font-mono text-xs">
        {entries.map((entry) => {
          const Icon = levelIcon[entry.level];
          return (
            <div
              key={entry.id}
              className={cn(
                "flex items-start gap-2 px-3 py-1.5 border-b border-border/50 hover:bg-surface/50 group",
                entry.level === "error" && "bg-red-500/5"
              )}
            >
              <Icon className={cn("h-3.5 w-3.5 mt-0.5 flex-shrink-0", levelColor[entry.level])} />
              <span className="flex-1 break-all text-foreground/80">{entry.message}</span>
              {entry.level === "error" && (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => onResolve(entry)}
                  className="h-5 px-1.5 text-[10px] opacity-0 group-hover:opacity-100 transition-opacity"
                >
                  <Wrench className="h-3 w-3 mr-0.5" />
                  Resolve
                </Button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
