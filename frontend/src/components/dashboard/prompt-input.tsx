"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { Plus, ArrowUp, BarChart3, X, FileText } from "lucide-react";
import { api, type LlmProvider, type ProviderSummary } from "@/lib/api";
import { BuildModeDropdown, type DashboardBuildMode } from "./build-mode-dropdown";

interface PromptInputProps {
  onSubmit: (prompt: string, mode: DashboardBuildMode, files: File[], stack: "static" | "nextjs") => void;
  initialValue?: string;
  initialStack?: "static" | "nextjs";
  disabled?: boolean;
  onOpenConnectors?: () => void;
}

export function PromptInput({
  onSubmit,
  initialValue = "",
  initialStack = "static",
  disabled,
  onOpenConnectors,
}: PromptInputProps) {
  const [input, setInput] = useState(initialValue);
  const [mode, setMode] = useState<DashboardBuildMode>("goal");
  const [stack, setStack] = useState<"static" | "nextjs">(initialStack);
  const [files, setFiles] = useState<File[]>([]);
  const [providers, setProviders] = useState<ProviderSummary[]>([]);
  const [selectedProvider, setSelectedProvider] = useState<LlmProvider | "">("");
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    const ta = textareaRef.current;
    /* v8 ignore if */
    if (ta) {
      ta.style.height = "0";
      ta.style.height = Math.min(ta.scrollHeight, 160) + "px";
    }
  }, [input]);

  useEffect(() => {
    api.listProviderSettings()
      .then((data) => {
        setProviders(data.providers);
        setSelectedProvider(data.active_provider);
      })
      .catch(() => {});
  }, []);

  const addFiles = useCallback((incoming: FileList | File[]) => {
    setFiles((current) => [...current, ...Array.from(incoming)]);
  }, []);

  const handleProviderChange = useCallback((provider: LlmProvider) => {
    setSelectedProvider(provider);
    void api.activateProvider(provider).catch(() => {});
  }, []);

  const handleSubmit = useCallback(() => {
    const text = input.trim();
    if ((!text && files.length === 0) || disabled) return;
    onSubmit(text || "Build from uploaded files", mode, files, stack);
  }, [input, mode, files, stack, disabled, onSubmit]);

  return (
    <div className="w-full rounded-2xl border border-border bg-surface shadow-lg shadow-black/20">
      <input
        ref={fileInputRef}
        type="file"
        multiple
        className="hidden"
        onChange={(e) => {
          if (e.target.files) addFiles(e.target.files);
          e.target.value = "";
        }}
      />
      <div className="px-4 pt-4 pb-2">
        <textarea
          ref={textareaRef}
          value={input}
          aria-label="Project description"
          onChange={(e) => setInput(e.target.value)}
          onPaste={(e) => {
            const pasted = Array.from(e.clipboardData.items)
              .filter((item) => item.kind === "file")
              .map((item) => item.getAsFile())
              .filter((file): file is File => Boolean(file));
            if (pasted.length) {
              e.preventDefault();
              addFiles(pasted);
            }
          }}
          placeholder="@agent to chat, # files, or describe what to build..."
          rows={1}
          disabled={disabled}
          className="w-full bg-transparent text-foreground text-sm placeholder:text-muted focus:outline-none resize-none min-h-[46px]"
          onKeyDown={(e) => {
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              handleSubmit();
            }
          }}
        />
      </div>

      {files.length > 0 && (
        <div className="px-4 pb-2 flex flex-wrap gap-1.5">
          {files.map((file, index) => (
            <span key={`${file.name}-${index}`} className="inline-flex items-center gap-1.5 rounded-full bg-accent/10 text-accent px-2 py-1 text-xs">
              <FileText className="h-3 w-3" />
              {file.name}
              <button
                type="button"
                onClick={() => setFiles((current) => current.filter((_, i) => i !== index))}
                className="hover:text-foreground cursor-pointer"
                aria-label={`Remove ${file.name}`}
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}

      <div className="flex items-center justify-between px-3 pb-3">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-surface-hover text-muted hover:text-foreground transition-colors cursor-pointer"
          title="Upload files"
        >
          <Plus className="h-4 w-4" />
        </button>

        <div className="flex items-center gap-2">
          {providers.length > 0 && (
            <select
              value={selectedProvider}
              onChange={(e) => handleProviderChange(e.target.value as LlmProvider)}
              className="max-w-44 rounded-full border border-border bg-surface px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
              aria-label="AI provider"
              title="AI provider"
            >
              {providers.map((provider) => (
                <option key={provider.provider} value={provider.provider}>
                  {provider.label} · {provider.model}
                </option>
              ))}
            </select>
          )}

          <BuildModeDropdown value={mode} onChange={setMode} />

          <select
            value={stack}
            onChange={(e) => setStack(e.target.value === "nextjs" ? "nextjs" : "static")}
            className="max-w-40 rounded-full border border-border bg-surface px-3 py-1.5 text-sm text-foreground focus:outline-none focus:ring-2 focus:ring-accent/50"
            aria-label="Project stack"
            title="HTML/CSS/JS is fastest. Next.js generates a real App Router project."
          >
            <option value="static">HTML / CSS / JS</option>
            <option value="nextjs">Next.js</option>
          </select>

          <button
            type="button"
            onClick={onOpenConnectors}
            className="flex items-center justify-center w-8 h-8 rounded-lg hover:bg-surface-hover text-muted hover:text-foreground transition-colors cursor-pointer"
            title="Connect tools"
          >
            <BarChart3 className="h-4 w-4" />
          </button>

          <button
            type="button"
            onClick={handleSubmit}
            disabled={(!input.trim() && files.length === 0) || disabled}
            className="flex items-center justify-center w-9 h-9 rounded-full bg-accent hover:bg-accent-hover text-white transition-colors disabled:opacity-30 disabled:pointer-events-none cursor-pointer"
            title="Start building"
          >
            <ArrowUp className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}
