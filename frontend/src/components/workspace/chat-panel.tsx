"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { Send, Paperclip } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { MessageBubble } from "./message-bubble";
import { FeedbackPanel } from "./feedback-panel";
import { FileTag } from "./file-tag";
import { LiveSession } from "./live-session";
import { NextSteps } from "./next-steps";
import { EditDiffPanel } from "./edit-diff-panel";
import { useProjectStore } from "@/stores/project-store";
import { api } from "@/lib/api";
import { AGENTS, type AgentName } from "@/types";

interface UploadedFile {
  name: string;
  size: number;
  path: string;
}

interface ChatPanelProps {
  projectId: string;
  onSend: (message: string, targetAgent?: AgentName) => void;
  onStartBuild: (prompt: string) => void;
  onResumeBuild: (prompt: string) => void;
  onFeedback: (action: "approve" | "revise", feedback?: string) => void;
  onUndo?: () => void;
  projectDescription: string;
}

const resumeCommands = new Set(["continue", "resume", "keep going", "restart build"]);
const mentionPattern = /(^|\s)@([a-z]*)$/i;
const MENTIONABLE = AGENTS.map((agent) => ({
  id: agent.id,
  name: agent.name,
  role: agent.role,
  aliases: (
    {
      engineer: ["engineer", "ravi"],
      team_leader: ["kai", "team_leader", "leader"],
      product_manager: ["nina", "pm", "product_manager"],
      architect: ["theo", "architect"],
      data_scientist: ["zara", "scientist", "data_scientist", "analyst"],
    } as Record<AgentName, string[]>
  )[agent.id],
  color: agent.color,
  blurb:
    agent.id === "engineer"
      ? "Edit project files directly"
      : agent.id === "product_manager"
        ? "Product scope & prioritization advice"
        : agent.id === "team_leader"
          ? "Scope, risks, and next decisions"
          : agent.id === "architect"
            ? "Structure & design advice"
            : "Data, metrics, and mock datasets",
}));
const routedMentionPattern =
  /^@(engineer|ravi|kai|team_leader|leader|nina|pm|product_manager|theo|architect|zara|scientist|data_scientist|analyst)\b/i;

function resolveMentionTarget(text: string): AgentName | undefined {
  const match = text.match(routedMentionPattern);
  if (!match) return undefined;
  const key = match[1].toLowerCase();
  for (const item of MENTIONABLE) {
    if (item.aliases.includes(key) || item.id === key) return item.id;
  }
  return undefined;
}

export function ChatPanel({
  projectId,
  onSend,
  onStartBuild,
  onResumeBuild,
  onFeedback,
  onUndo,
  projectDescription,
}: ChatPanelProps) {
  const messages = useProjectStore((s) => s.messages);
  const projectStatus = useProjectStore((s) => s.projectStatus);
  const pendingFeedback = useProjectStore((s) => s.pendingFeedback);
  const agents = useProjectStore((s) => s.agents);
  const thinkingMessages = useProjectStore((s) => s.thinkingMessages);
  const activities = useProjectStore((s) => s.activities);
  const [input, setInput] = useState("");
  const [attachedFiles, setAttachedFiles] = useState<UploadedFile[]>([]);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const agentsIdle = agents.every((agent) => agent.status === "idle");
  const canResumeBuild = projectStatus === "error" || (
    projectStatus !== "created" &&
    projectStatus !== "complete" &&
    pendingFeedback === null &&
    agentsIdle
  );
  const mentionMatch = projectStatus === "complete" ? input.match(mentionPattern) : null;
  const mentionQuery = mentionMatch?.[2].toLowerCase() ?? "";
  const mentionOptions = MENTIONABLE.filter((item) =>
    item.aliases.some((alias) => alias.startsWith(mentionQuery)) ||
    item.name.toLowerCase().startsWith(mentionQuery),
  );
  const showMentionMenu = Boolean(mentionMatch && mentionOptions.length > 0);

  const insertMention = (alias = "engineer") => {
    if (mentionMatch?.index !== undefined) {
      const prefix = input.slice(0, mentionMatch.index) + mentionMatch[1];
      setInput(`${prefix}@${alias} `);
    } else {
      setInput(`@${alias} `);
    }
    requestAnimationFrame(() => inputRef.current?.focus());
  };

  const insertEngineerMention = () => insertMention("engineer");

  useEffect(() => {
    const el = scrollRef.current;
    /* v8 ignore if */
    if (!el) return;
    const nearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 150;
    /* v8 ignore if */
    if (!nearBottom) return;
    /* v8 ignore next */
    if (el.scrollTo) el.scrollTo({ top: el.scrollHeight, behavior: "smooth" });
    else el.scrollTop = el.scrollHeight;
  }, [messages, pendingFeedback, thinkingMessages, activities]);

  const handleUpload = useCallback(
    async (files: FileList | File[]) => {
      setUploadError(null);
      setUploading(true);
      try {
        for (const file of Array.from(files)) {
          const result = await api.uploadFile(projectId, file);
          setAttachedFiles((prev) => [...prev, result]);
        }
      } catch {
        setUploadError("Could not upload file. Please try again.");
      } finally {
        setUploading(false);
      }
    },
    [projectId]
  );

  const handlePaste = useCallback(
    (e: React.ClipboardEvent) => {
      const items = e.clipboardData?.items;
      if (!items) return;
      const imageFiles: File[] = [];
      for (const item of Array.from(items)) {
        if (item.type.startsWith("image/")) {
          const file = item.getAsFile();
          if (file) imageFiles.push(file);
        }
      }
      if (imageFiles.length > 0) {
        e.preventDefault();
        handleUpload(imageFiles);
      }
    },
    [handleUpload]
  );

  const handleSubmit = () => {
    const text = input.trim();
    if (!text && attachedFiles.length === 0) return;

    const fileRefs = attachedFiles.map((f) => `#${f.name}`).join(" ");
    const fullMessage = fileRefs ? `${text} ${fileRefs}`.trim() : text;

    setInput("");
    setAttachedFiles([]);

    if (projectStatus === "created") {
      onStartBuild(fullMessage);
    } else if (canResumeBuild && resumeCommands.has(text.toLowerCase())) {
      onResumeBuild(projectDescription);
    } else {
      const targetAgent = resolveMentionTarget(text);
      if (targetAgent) onSend(fullMessage, targetAgent);
      else onSend(fullMessage);
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-4 py-4 space-y-1" role="log" aria-live="polite">
        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full text-center px-6">
            <div className="w-16 h-16 rounded-2xl bg-accent/10 flex items-center justify-center mb-4">
              <Send className="h-7 w-7 text-accent" />
            </div>
            <h3 className="text-lg font-semibold text-foreground mb-2">Ready to Build</h3>
            <p className="text-sm text-muted max-w-md mb-6">
              Your project: &quot;{projectDescription}&quot;
            </p>
            <Button onClick={() => onStartBuild(projectDescription)}>
              Start Building
            </Button>
          </div>
        )}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        <LiveSession />
        <EditDiffPanel onUndo={onUndo} />
        <NextSteps projectId={projectId} onSend={onSend} onInsertMention={insertEngineerMention} onUndo={onUndo} />
        {canResumeBuild ? (
          <div className="px-12 py-3">
            <div className="rounded-xl border border-accent/20 bg-accent/10 p-3 text-sm text-accent">
              Build was interrupted or failed. Resume from the last CrewAI checkpoint to continue where the team left off.
              <Button className="mt-3" size="sm" onClick={() => onResumeBuild(projectDescription)}>
                Resume from checkpoint
              </Button>
            </div>
          </div>
        ) : null}
      </div>

      {pendingFeedback && <FeedbackPanel onFeedback={onFeedback} />}

      <div className="border-t border-border p-4">
        {attachedFiles.length > 0 && (
          <div className="flex flex-wrap gap-1.5 mb-2">
            {attachedFiles.map((f) => (
              <FileTag
                key={f.path}
                name={f.name}
                onRemove={() => setAttachedFiles((prev) => prev.filter((x) => x.path !== f.path))}
              />
            ))}
          </div>
        )}
        {uploadError ? (
          <p className="mb-2 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-xs text-red-400">
            {uploadError}
          </p>
        ) : null}
        <div className="relative flex gap-2">
          {showMentionMenu ? (
            <div
              className="absolute bottom-full left-10 right-12 z-20 mb-2 max-h-64 overflow-auto rounded-xl border border-border bg-surface shadow-xl"
              role="listbox"
              aria-label="Agent mentions"
            >
              {mentionOptions.map((item, index) => {
                const primaryAlias = item.aliases[0];
                return (
                  <button
                    key={item.id}
                    type="button"
                    role="option"
                    aria-selected={index === 0}
                    onMouseDown={(event) => event.preventDefault()}
                    onClick={() => insertMention(primaryAlias)}
                    className="flex w-full items-center gap-3 px-3 py-2.5 text-left transition-colors hover:bg-accent/10 focus:bg-accent/10 focus:outline-none"
                  >
                    <span
                      className="flex h-8 w-8 items-center justify-center rounded-lg text-sm font-semibold"
                      style={{
                        color: item.color,
                        backgroundColor: `color-mix(in srgb, ${item.color} 14%, transparent)`,
                      }}
                    >
                      {item.name.slice(0, 1)}
                    </span>
                    <span className="min-w-0">
                      <span className="block text-sm font-medium text-foreground">
                        @{primaryAlias} · {item.name}
                      </span>
                      <span className="block truncate text-xs text-muted">{item.blurb}</span>
                    </span>
                  </button>
                );
              })}
            </div>
          ) : null}
          <input
            ref={fileInputRef}
            type="file"
            multiple
            className="hidden"
            onChange={(e) => {
              if (e.target.files) handleUpload(e.target.files);
              e.target.value = "";
            }}
          />
          <Button
            variant="ghost"
            size="sm"
            className="self-end px-2"
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            aria-label="Attach file"
          >
            <Paperclip className="h-4 w-4" />
          </Button>
          <Textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onPaste={handlePaste}
            aria-label="Chat message"
            placeholder={
              projectStatus === "created"
                ? "Describe what to build, or click Start Building..."
                : projectStatus === "complete"
                  ? "Describe an update, or type @ for Kai, Nina, Theo, Zara, or Ravi..."
                  : "Send a message..."
            }
            rows={2}
            className="min-h-[44px]"
            onKeyDown={(e) => {
              if (showMentionMenu && (e.key === "Enter" || e.key === "Tab")) {
                e.preventDefault();
                insertMention(mentionOptions[0]?.aliases[0] ?? "engineer");
                return;
              }
              if (showMentionMenu && e.key === "Escape") {
                e.preventDefault();
                setInput(input.replace(mentionPattern, "$1"));
                return;
              }
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                handleSubmit();
              }
            }}
          />
          <Button
            onClick={handleSubmit}
            size="sm"
            className="self-end px-3"
            disabled={!input.trim() && attachedFiles.length === 0}
            aria-label="Send message"
          >
            <Send className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}
