"use client";

import { useState } from "react";
import { Eye, Code2, FileCode, X, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CodeViewer, getLanguage } from "./code-viewer";
import { useProjectStore } from "@/stores/project-store";
import { buildSrcDocPreview } from "@/lib/preview-document";
import { cn } from "@/lib/utils";

interface ArtifactCardProps {
  filePath: string;
}

export function ArtifactCard({ filePath }: ArtifactCardProps) {
  const file = useProjectStore((s) => s.files.find((f) => f.file_path === filePath));
  const files = useProjectStore((s) => s.files);
  const [expanded, setExpanded] = useState(false);
  const [view, setView] = useState<"preview" | "code">("preview");

  if (!file) return null;

  const isHtml = filePath.endsWith(".html") || filePath.endsWith(".htm");
  const ext = filePath.includes(".") ? filePath.slice(filePath.lastIndexOf(".") + 1).toLowerCase() : "";

  const iconColors: Record<string, string> = {
    html: "text-orange-400",
    css: "text-blue-400",
    js: "text-yellow-400",
    ts: "text-blue-500",
    json: "text-green-400",
  };

  if (!expanded) {
    return (
      <button
        onClick={() => setExpanded(true)}
        className="flex items-center gap-2.5 w-full px-3 py-2.5 rounded-lg border border-border bg-surface/50 hover:bg-surface-hover transition-colors text-left cursor-pointer group"
      >
        <FileCode className={cn("h-4 w-4 flex-shrink-0", iconColors[ext] ?? "text-muted")} />
        <span className="text-sm font-medium text-foreground truncate flex-1">{filePath}</span>
        <span className="text-xs text-muted">{formatSize(file.content.length)}</span>
        <Maximize2 className="h-3.5 w-3.5 text-muted opacity-0 group-hover:opacity-100 transition-opacity" />
      </button>
    );
  }

  return (
    <div className="rounded-xl border border-border bg-surface overflow-hidden animate-slide-up">
      <div className="flex items-center justify-between border-b border-border px-3 py-2">
        <div className="flex items-center gap-2">
          <FileCode className={cn("h-4 w-4", iconColors[ext] ?? "text-muted")} />
          <span className="text-sm font-medium text-foreground">{filePath}</span>
        </div>
        <div className="flex items-center gap-1">
          {isHtml && (
            <>
              <Button
                variant={view === "preview" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setView("preview")}
                className="h-7 px-2 text-xs"
              >
                <Eye className="h-3 w-3 mr-1" />
                Preview
              </Button>
              <Button
                variant={view === "code" ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setView("code")}
                className="h-7 px-2 text-xs"
              >
                <Code2 className="h-3 w-3 mr-1" />
                Code
              </Button>
            </>
          )}
          <Button variant="ghost" size="sm" onClick={() => setExpanded(false)} className="h-7 px-1.5" aria-label={`Close ${filePath}`}>
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      <div className="h-64 overflow-auto">
        {isHtml && view === "preview" ? (
          <iframe
            srcDoc={buildSrcDocPreview(file.content, files)}
            className="w-full h-full border-0 bg-white"
            sandbox="allow-scripts"
            title={`Preview ${filePath}`}
          />
        ) : (
          <CodeViewer code={file.content} language={getLanguage(filePath)} />
        )}
      </div>
    </div>
  );
}

function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  return `${(bytes / 1024).toFixed(1)} KB`;
}
