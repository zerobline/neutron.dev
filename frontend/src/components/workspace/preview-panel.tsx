"use client";

import { useState, useRef, useCallback, useEffect, useMemo } from "react";
import { useProjectStore } from "@/stores/project-store";
import { Code2, Eye, FileCode, FolderTree, Terminal, MousePointer, Sparkles, ExternalLink, FolderOpen, Download, X, Play, Square, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Textarea } from "@/components/ui/textarea";
import { CodeViewer, getLanguage } from "./code-viewer";
import { ConsolePanel, type ConsoleEntry } from "./console-panel";
import { api, downloadProject } from "@/lib/api";
import { buildSrcDocPreview } from "@/lib/preview-document";
import { cn } from "@/lib/utils";

type RuntimeStatus = "idle" | "installing" | "starting" | "ready" | "error" | "stopped";

interface RuntimeState {
  status: RuntimeStatus;
  url: string | null;
  message: string;
  logs: string[];
}

interface PreviewPanelProps {
  projectId?: string;
  onSendMessage?: (message: string) => void;
}

const SELECT_QUICK_EDITS = [
  "Make this more prominent",
  "Improve the copy",
  "Change the color to match the theme",
  "Hide this element",
];

function buildElementEditPrompt(
  element: { tag: string; text: string; selector: string },
  instruction: string,
): string {
  const text = element.text.trim().slice(0, 120);
  const textPart = text ? ` that currently shows "${text}"` : "";
  return (
    `@engineer Modify the <${element.tag}> element${textPart}` +
    ` (CSS selector hint: ${element.selector || element.tag}). ` +
    `${instruction.trim()} ` +
    `Update HTML/CSS/JS as needed and write files with write_code_file so the preview reflects the change.`
  );
}

export function PreviewPanel({ projectId, onSendMessage }: PreviewPanelProps) {
  const files = useProjectStore((s) => s.files);
  const projectStatus = useProjectStore((s) => s.projectStatus);
  const projectStack = useProjectStore((s) => s.projectStack);
  const isNextStack = projectStack === "nextjs";
  const [activeTab, setActiveTab] = useState<"preview" | "code" | "files" | "console">("preview");
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [selectMode, setSelectMode] = useState(false);
  const [selectedElement, setSelectedElement] = useState<{ tag: string; text: string; selector: string } | null>(null);
  const [editInstruction, setEditInstruction] = useState("");
  const [consoleEntries, setConsoleEntries] = useState<ConsoleEntry[]>([]);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<RuntimeState>({
    status: "idle",
    url: null,
    message: "",
    logs: [],
  });
  const [runtimeBusy, setRuntimeBusy] = useState(false);
  // Bumped on start/stop so the poll loop restarts after the user kicks off a preview.
  const [runtimePollKey, setRuntimePollKey] = useState(0);
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const editInputRef = useRef<HTMLTextAreaElement>(null);
  const hasPackageJson = files.some((f) => f.file_path === "package.json");

  const handleExport = useCallback(async () => {
    if (!projectId) return;
    setExporting(true);
    setExportError(null);
    try {
      await downloadProject(projectId);
    } catch {
      setExportError("Could not download the project ZIP. Try again.");
    } finally {
      setExporting(false);
    }
  }, [projectId]);

  const htmlFile = files.find(
    (f) => f.file_path === "index.html" || f.file_path.endsWith(".html")
  );
  const previewHtml = useMemo(
    () => htmlFile ? injectPreviewScripts(htmlFile.content, files, selectMode) : "",
    [htmlFile, files, selectMode]
  );

  const currentFile = selectedFile
    ? files.find((f) => f.file_path === selectedFile)
    : null;

  useEffect(() => {
    function handleMessage(e: MessageEvent) {
      if (e.origin !== "null") return;
      // Browsers provide a source Window; the null allowance keeps synthetic
      // test events compatible while rejecting messages from other frames.
      if (e.source && e.source !== iframeRef.current?.contentWindow) return;
      if (e.data?.source !== "neutron-preview") return;
      if (e.data.type === "console") {
        const level: ConsoleEntry["level"] = ["error", "warn", "info"].includes(e.data.level) ? e.data.level : "info";
        setConsoleEntries((prev) => [
          ...prev,
          {
            id: crypto.randomUUID(),
            level,
            message: String(e.data.message ?? ""),
            timestamp: Date.now(),
          },
        ].slice(-100));
      }
      if (e.data.type === "element-selected") {
        setSelectedElement({
          tag: String(e.data.tag ?? "element"),
          text: String(e.data.text ?? ""),
          selector: String(e.data.selector ?? ""),
        });
        setEditInstruction("");
        requestAnimationFrame(() => editInputRef.current?.focus());
      }
    }
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, []);

  useEffect(() => {
    if (iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        { type: "set-select-mode", enabled: selectMode },
        "*"
      );
    }
  }, [selectMode]);

  // Poll Next.js runtime status while it's booting or live.
  // runtimePollKey restarts the loop after Start (idle poll only runs once).
  useEffect(() => {
    if (!projectId || !isNextStack) return;
    let cancelled = false;
    let timer: ReturnType<typeof setTimeout> | null = null;

    const poll = async () => {
      try {
        const status = await api.getProjectRuntime(projectId);
        if (cancelled) return;
        setRuntime({
          status: status.status,
          url: status.url,
          message: status.message,
          logs: status.logs ?? [],
        });
        if (status.status === "installing" || status.status === "starting" || status.status === "ready") {
          // Install can be quiet for 30–90s — poll often so the UI shows heartbeats/logs.
          timer = setTimeout(poll, status.status === "ready" ? 4000 : 1000);
        }
      } catch {
        if (!cancelled) {
          setRuntime((prev) => ({
            ...prev,
            status: prev.status === "ready" ? prev.status : "error",
            message: prev.message || "Could not reach preview runtime.",
          }));
        }
      }
    };

    void poll();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
    };
  }, [projectId, isNextStack, files.length, runtimePollKey]);

  const startRuntime = useCallback(async () => {
    if (!projectId) return;
    setRuntimeBusy(true);
    setRuntime((prev) => ({
      ...prev,
      status: "installing",
      message: "Starting npm install…",
      logs: prev.logs,
    }));
    try {
      const status = await api.startProjectRuntime(projectId);
      setRuntime({
        status: status.status,
        url: status.url,
        message: status.message,
        logs: status.logs ?? [],
      });
      // Restart poll loop so we keep following install/start progress.
      setRuntimePollKey((key) => key + 1);
    } catch (error) {
      setRuntime((prev) => ({
        ...prev,
        status: "error",
        message: error instanceof Error ? error.message : "Failed to start Next.js preview.",
      }));
    } finally {
      setRuntimeBusy(false);
    }
  }, [projectId]);

  const stopRuntime = useCallback(async () => {
    if (!projectId) return;
    setRuntimeBusy(true);
    try {
      const status = await api.stopProjectRuntime(projectId);
      setRuntime({
        status: status.status,
        url: status.url,
        message: status.message,
        logs: status.logs ?? [],
      });
      setRuntimePollKey((key) => key + 1);
    } catch {
      setRuntime((prev) => ({ ...prev, message: "Failed to stop preview." }));
    } finally {
      setRuntimeBusy(false);
    }
  }, [projectId]);

  const handleResolve = useCallback(
    (entry: ConsoleEntry) => {
      onSendMessage?.(
        `@engineer Fix this console error in the generated code: "${entry.message}". ` +
          `Update the relevant files with write_code_file.`,
      );
    },
    [onSendMessage]
  );

  const clearSelection = useCallback(() => {
    setSelectedElement(null);
    setEditInstruction("");
  }, []);

  const submitElementEdit = useCallback(
    (instruction: string) => {
      /* v8 ignore next */
      if (!selectedElement || !instruction.trim()) return;
      onSendMessage?.(buildElementEditPrompt(selectedElement, instruction));
      clearSelection();
      setSelectMode(false);
    },
    [selectedElement, onSendMessage, clearSelection],
  );

  const handleOpenPreview = useCallback(() => {
    if (isNextStack) {
      if (runtime.url) {
        window.open(runtime.url, "_blank", "noopener,noreferrer");
      }
      return;
    }
    /* v8 ignore next */
    if (!previewHtml) return;
    const blob = new Blob([previewHtml], { type: "text/html" });
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    window.setTimeout(() => URL.revokeObjectURL(url), 1000);
  }, [previewHtml, isNextStack, runtime.url]);

  if (files.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-center px-6">
        <div className="w-16 h-16 rounded-2xl bg-surface flex items-center justify-center mb-4">
          <Eye className="h-7 w-7 text-muted" />
        </div>
        <h3 className="text-lg font-semibold text-foreground mb-2">Live Preview</h3>
        <p className="text-sm text-muted max-w-sm">
          {projectStatus === "created"
            ? "Start building to see your project here."
            : "Generating files... Preview will appear soon."}
        </p>
        {projectStatus !== "created" && projectStatus !== "complete" && (
          <div className="mt-4 flex items-center gap-2 text-sm text-accent">
            <div className="w-2 h-2 rounded-full bg-accent animate-pulse-dot" />
            Agents are working...
          </div>
        )}
      </div>
    );
  }

  const errorCount = consoleEntries.filter((e) => e.level === "error").length;

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between border-b border-border px-4 py-2">
        <div className="flex gap-1">
          <Button
            variant={activeTab === "preview" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("preview")}
          >
            <Eye className="h-4 w-4 mr-1.5" />
            App Viewer
          </Button>
          <Button
            variant={activeTab === "code" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("code")}
          >
            <Code2 className="h-4 w-4 mr-1.5" />
            Editor
          </Button>
          <Button
            variant={activeTab === "files" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("files")}
          >
            <FolderOpen className="h-4 w-4 mr-1.5" />
            File
          </Button>
          <Button
            variant={activeTab === "console" ? "secondary" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("console")}
          >
            <Terminal className="h-4 w-4 mr-1.5" />
            Console
            {errorCount > 0 && (
              <Badge variant="error" className="ml-1.5 px-1.5 py-0 text-[10px]">
                {errorCount}
              </Badge>
            )}
          </Button>
        </div>
        <div className="flex items-center gap-2">
          {projectId && (
            <button
              type="button"
              onClick={() => void handleExport()}
              disabled={exporting}
              className="inline-flex h-7 items-center rounded-md px-2 text-xs text-muted hover:bg-surface-hover hover:text-foreground transition-colors disabled:opacity-50"
              aria-label="Download project ZIP"
            >
              <Download className="h-3 w-3 mr-1" />
              {exporting ? "Exporting..." : "Export"}
            </button>
          )}
          {activeTab === "preview" && (
            <>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleOpenPreview}
                className="h-7 px-2 text-xs"
                disabled={isNextStack && !runtime.url}
              >
                <ExternalLink className="h-3 w-3 mr-1" />
                Open
              </Button>
              {!isNextStack ? (
                <Button
                  variant={selectMode ? "primary" : "ghost"}
                  size="sm"
                  onClick={() => {
                    setSelectMode((value) => !value);
                    clearSelection();
                  }}
                  className="h-7 px-2 text-xs"
                  title="Click an element in the preview, then describe the change for Ravi"
                >
                  <MousePointer className="h-3 w-3 mr-1" />
                  {selectMode ? "Selecting..." : "Select to edit"}
                </Button>
              ) : runtime.status === "ready" ? (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void stopRuntime()}
                  disabled={runtimeBusy}
                  className="h-7 px-2 text-xs"
                  title="Stop the Next.js dev server"
                >
                  <Square className="h-3 w-3 mr-1" />
                  Stop
                </Button>
              ) : (
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => void startRuntime()}
                  disabled={runtimeBusy || !hasPackageJson || runtime.status === "installing" || runtime.status === "starting"}
                  className="h-7 px-2 text-xs"
                  title="Start local Next.js preview"
                >
                  {runtime.status === "installing" || runtime.status === "starting" ? (
                    <Loader2 className="h-3 w-3 mr-1 animate-spin" />
                  ) : (
                    <Play className="h-3 w-3 mr-1" />
                  )}
                  {runtime.status === "installing" || runtime.status === "starting" ? "Starting…" : "Start"}
                </Button>
              )}
            </>
          )}
          <Badge variant="success">
            {files.length} file{files.length !== 1 && "s"}
          </Badge>
        </div>
      </div>
      {exportError ? (
        <div className="border-b border-red-500/20 bg-red-500/10 px-4 py-2 text-xs text-red-400">
          {exportError}
        </div>
      ) : null}
      {selectMode && activeTab === "preview" && !selectedElement ? (
        <div className="border-b border-accent/20 bg-accent/10 px-4 py-2 text-xs text-accent">
          Click any element in the preview to edit it with AI. Esc or toggle off to cancel.
        </div>
      ) : null}

      {activeTab === "preview" ? (
        <div className="flex-1 relative">
          <div className={cn("h-full bg-white", selectMode && "cursor-crosshair")}>
            {isNextStack ? (
              runtime.status === "ready" && runtime.url ? (
                <iframe
                  key={runtime.url}
                  src={runtime.url}
                  className="h-full w-full border-0 bg-white"
                  title="Next.js preview"
                />
              ) : (
                <div className="flex h-full flex-col bg-background">
                  <div className="flex flex-1 flex-col items-center justify-center gap-3 px-8 text-center">
                    <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-sky-500/30 bg-sky-500/10 text-sky-300">
                      {runtime.status === "installing" || runtime.status === "starting" ? (
                        <Loader2 className="h-7 w-7 animate-spin" />
                      ) : (
                        <Code2 className="h-7 w-7" />
                      )}
                    </div>
                    <h3 className="text-lg font-semibold text-foreground">Next.js live preview</h3>
                    <p className="max-w-md text-sm leading-relaxed text-muted">
                      {runtime.message ||
                        (hasPackageJson
                          ? "Start the local Next.js dev server to preview this project in the App Viewer. First install often takes 1–3 minutes."
                          : "Waiting for package.json — finish the build first.")}
                    </p>
                    {runtime.status === "installing" || runtime.status === "starting" ? (
                      <p className="text-[11px] text-sky-300/90">
                        Live progress updates every second — leave this tab open while npm works.
                      </p>
                    ) : null}
                    <div className="flex flex-wrap items-center justify-center gap-2">
                      {runtime.status === "ready" ? null : (
                        <Button
                          size="sm"
                          onClick={() => void startRuntime()}
                          disabled={runtimeBusy || !hasPackageJson || runtime.status === "installing" || runtime.status === "starting"}
                        >
                          {runtime.status === "installing" || runtime.status === "starting" ? (
                            <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Play className="mr-1.5 h-3.5 w-3.5" />
                          )}
                          {runtime.status === "installing"
                            ? "Installing…"
                            : runtime.status === "starting"
                              ? "Starting…"
                              : runtime.status === "error"
                                ? "Retry preview"
                                : "Start Next.js preview"}
                        </Button>
                      )}
                      {(runtime.status === "installing" || runtime.status === "starting" || runtime.status === "ready") && (
                        <Button size="sm" variant="secondary" onClick={() => void stopRuntime()} disabled={runtimeBusy}>
                          <Square className="mr-1.5 h-3.5 w-3.5" />
                          Stop
                        </Button>
                      )}
                      {runtime.status === "ready" && runtime.url ? (
                        <Button size="sm" variant="ghost" onClick={() => window.open(runtime.url!, "_blank", "noopener,noreferrer")}>
                          <ExternalLink className="mr-1.5 h-3.5 w-3.5" />
                          Open tab
                        </Button>
                      ) : null}
                      {runtime.status === "error" ? (
                        <Button size="sm" variant="ghost" onClick={() => void startRuntime()} disabled={runtimeBusy}>
                          <RefreshCw className="mr-1.5 h-3.5 w-3.5" />
                          Retry
                        </Button>
                      ) : null}
                    </div>
                    <p className="text-[11px] text-muted">
                      {files.length} file{files.length === 1 ? "" : "s"}
                      {hasPackageJson ? " · package.json ready" : ""}
                      {" · requires Node.js/npm on this machine"}
                    </p>
                  </div>
                  {runtime.logs.length > 0 ? (
                    <pre className="max-h-36 overflow-auto border-t border-border bg-[#0b1220] px-3 py-2 font-mono text-[10px] leading-relaxed text-slate-300">
                      {runtime.logs.slice(-30).join("\n")}
                    </pre>
                  ) : null}
                </div>
              )
            ) : htmlFile ? (
              <iframe
                key={previewHtml}
                ref={iframeRef}
                srcDoc={previewHtml}
                className="w-full h-full border-0"
                sandbox="allow-scripts"
                title="Preview"
              />
            ) : (
              <div className="flex items-center justify-center h-full text-muted text-sm bg-background">
                No HTML file found to preview.
              </div>
            )}
          </div>
          {selectedElement ? (
            <div className="absolute bottom-0 left-0 right-0 border-t border-border bg-surface/95 px-4 py-3 shadow-[0_-8px_30px_rgba(0,0,0,0.18)] backdrop-blur-sm animate-slide-up">
              <div className="mb-2 flex items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-[10px] font-semibold uppercase tracking-wide text-muted">
                    Edit with Ravi
                  </p>
                  <p className="mt-0.5 truncate text-sm">
                    <span className="font-mono text-accent">&lt;{selectedElement.tag}&gt;</span>
                    {selectedElement.text.trim() ? (
                      <span className="ml-2 text-muted">
                        {selectedElement.text.trim().slice(0, 72)}
                        {selectedElement.text.trim().length > 72 ? "…" : ""}
                      </span>
                    ) : null}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={clearSelection}
                  className="rounded-md p-1 text-muted hover:bg-surface-hover hover:text-foreground"
                  aria-label="Clear selection"
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
              <div className="mb-2 flex flex-wrap gap-1.5">
                {SELECT_QUICK_EDITS.map((chip) => (
                  <button
                    key={chip}
                    type="button"
                    onClick={() => submitElementEdit(chip)}
                    className="rounded-full border border-border/80 bg-background/50 px-2.5 py-1 text-[10px] font-medium text-muted transition-colors hover:border-accent/30 hover:text-accent"
                  >
                    {chip}
                  </button>
                ))}
              </div>
              <div className="flex gap-2">
                <Textarea
                  ref={editInputRef}
                  value={editInstruction}
                  onChange={(e) => setEditInstruction(e.target.value)}
                  rows={2}
                  aria-label="Describe the change for the selected element"
                  placeholder="Describe the change… e.g. Make the heading say Welcome back"
                  className="min-h-[44px] flex-1 text-sm"
                  onKeyDown={(e) => {
                    if (e.key === "Escape") {
                      e.preventDefault();
                      clearSelection();
                      return;
                    }
                    if (e.key === "Enter" && !e.shiftKey) {
                      e.preventDefault();
                      submitElementEdit(editInstruction);
                    }
                  }}
                />
                <Button
                  size="sm"
                  className="self-end"
                  disabled={!editInstruction.trim()}
                  onClick={() => submitElementEdit(editInstruction)}
                >
                  <Sparkles className="mr-1 h-3.5 w-3.5" />
                  Apply edit
                </Button>
              </div>
            </div>
          ) : null}
        </div>
      ) : activeTab === "console" ? (
        <ConsolePanel
          entries={consoleEntries}
          onClear={() => setConsoleEntries([])}
          onResolve={handleResolve}
        />
      ) : activeTab === "files" ? (
        <div className="flex-1 overflow-auto bg-background p-4">
          <div className="mb-4 text-sm text-muted">
            data / chats / <span className="text-foreground">Generated Project</span>
          </div>
          <div className="overflow-hidden rounded-xl border border-border bg-surface">
            <div className="grid grid-cols-[1fr_120px_180px] border-b border-border px-4 py-3 text-xs font-medium text-muted">
              <span>File Name</span>
              <span>Size</span>
              <span>Last Update</span>
            </div>
            {files.map((file) => (
              <button
                key={file.file_path}
                onClick={() => {
                  setSelectedFile(file.file_path);
                  setActiveTab("code");
                }}
                className="grid w-full grid-cols-[1fr_120px_180px] items-center border-b border-border px-4 py-3 text-left text-sm last:border-b-0 hover:bg-surface-hover transition-colors cursor-pointer"
              >
                <span className="flex items-center gap-2 text-foreground">
                  <FileCode className="h-4 w-4 text-muted" />
                  {file.file_path}
                </span>
                <span className="text-muted">{(file.content.length / 1024).toFixed(2)} KB</span>
                <span className="text-muted">{new Date().toLocaleDateString()}</span>
              </button>
            ))}
          </div>
        </div>
      ) : (
        <div className="flex flex-1 overflow-hidden">
          <div className="w-56 border-r border-border overflow-y-auto py-2">
            <div className="px-3 py-1.5 text-xs font-medium text-muted uppercase tracking-wider flex items-center gap-1.5">
              <FolderTree className="h-3 w-3" />
              Files
            </div>
            {files.map((f) => (
              <button
                key={f.file_path}
                onClick={() => setSelectedFile(f.file_path)}
                className={cn(
                  "w-full text-left px-3 py-1.5 text-sm flex items-center gap-2 hover:bg-surface-hover transition-colors cursor-pointer",
                  selectedFile === f.file_path && "bg-surface-hover text-accent"
                )}
              >
                <FileCode className="h-3.5 w-3.5 flex-shrink-0 text-muted" />
                <span className="truncate">{f.file_path}</span>
              </button>
            ))}
          </div>

          <div className="flex-1 overflow-auto bg-[#011627]">
            {currentFile ? (
              <CodeViewer
                code={currentFile.content}
                language={getLanguage(currentFile.file_path)}
              />
            ) : (
              <div className="flex items-center justify-center h-full text-sm text-muted">
                Select a file to view its code.
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function injectPreviewScripts(
  html: string,
  files: { file_path: string; content: string }[],
  selectMode: boolean
): string {
  let result = buildSrcDocPreview(html, files);

  const bridgeScript = `
<script>
(function() {
  var post = function(data) { window.parent.postMessage(Object.assign({source:'neutron-preview'}, data), '*'); };

  ['error','warn','info'].forEach(function(level) {
    var orig = console[level];
    console[level] = function() {
      var msg = Array.prototype.slice.call(arguments).map(function(a) {
        return typeof a === 'object' ? JSON.stringify(a) : String(a);
      }).join(' ');
      post({type:'console', level:level, message:msg});
      orig.apply(console, arguments);
    };
  });

  window.onerror = function(msg) { post({type:'console', level:'error', message:String(msg)}); };

  var selectMode = ${selectMode ? "true" : "false"};
  var highlight = null;

  window.addEventListener('message', function(e) {
    if (e.data && e.data.type === 'set-select-mode') {
      selectMode = e.data.enabled;
      if (!selectMode && highlight) { highlight.style.outline = ''; highlight = null; }
    }
  });

  document.addEventListener('mouseover', function(e) {
    if (!selectMode) return;
    if (highlight) highlight.style.outline = '';
    e.target.style.outline = '2px solid #6366f1';
    highlight = e.target;
  });

  document.addEventListener('click', function(e) {
    if (!selectMode) return;
    e.preventDefault();
    e.stopPropagation();
    var el = e.target;
    var selector = el.tagName.toLowerCase();
    if (el.id) selector += '#' + el.id;
    else if (el.className && typeof el.className === 'string') selector += '.' + el.className.split(' ')[0];
    post({type:'element-selected', tag:el.tagName.toLowerCase(), text:el.textContent.slice(0,120), selector:selector});
  }, true);
})();
</script>`;

  result = result.replace("</body>", bridgeScript + "</body>");
  return result;
}
