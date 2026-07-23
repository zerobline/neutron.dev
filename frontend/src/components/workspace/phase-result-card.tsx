"use client";

import { useState, type ReactNode } from "react";
import {
  CheckCircle2,
  ChevronDown,
  ChevronUp,
  FileCode2,
  ListChecks,
  Palette,
  Sparkles,
  Users,
} from "lucide-react";
import { Avatar } from "@/components/ui/avatar";
import { humanizeHeadline, humanizeText } from "@/lib/humanize";
import { cn, getAgentBgColor } from "@/lib/utils";
import { AGENTS, type PhaseResult, type PhaseResultKind } from "@/types";

const PREVIEW_COUNT = 4;

const FOOTER_BY_KIND: Record<PhaseResultKind, string> = {
  brief: "Brief locked in. Open details for requirements and success criteria.",
  analysis: "Research complete. Open details for workflows and recommendations.",
  plan: "Plan ready. Open details for features, pages, and milestones.",
  architecture: "Architecture set. Open details for components, colors, and files.",
  build: "Files written. Open details for the file list and behaviors.",
  markdown: "Phase complete. Open details for the full breakdown.",
};

function asStringList(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
}

function asRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value as Record<string, unknown>;
}

function clipSummary(text: string, limit = 220): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= limit) return cleaned;
  return `${cleaned.slice(0, limit - 1).trimEnd()}…`;
}

function ItemList({
  items,
  empty,
  defaultOpen = false,
}: {
  items: string[];
  empty?: string;
  defaultOpen?: boolean;
}) {
  const [showAll, setShowAll] = useState(defaultOpen);
  if (items.length === 0) {
    return empty ? <p className="text-xs text-muted">{empty}</p> : null;
  }

  const visible = showAll ? items : items.slice(0, PREVIEW_COUNT);
  const hidden = Math.max(0, items.length - PREVIEW_COUNT);

  return (
    <div className="space-y-2">
      <div className="flex flex-wrap gap-1.5">
        {visible.map((item) => (
          <span
            key={item}
            className="rounded-full border border-border/80 bg-background/55 px-2.5 py-1 text-[11px] leading-none text-foreground/90"
          >
            {item}
          </span>
        ))}
      </div>
      {hidden > 0 ? (
        <button
          type="button"
          onClick={() => setShowAll((value) => !value)}
          className="text-[11px] font-medium text-accent hover:text-accent/80"
        >
          {showAll ? "Show less" : `Show ${hidden} more`}
        </button>
      ) : null}
    </div>
  );
}

function Section({
  title,
  count,
  children,
  defaultOpen = false,
}: {
  title: string;
  count?: number;
  children: ReactNode;
  defaultOpen?: boolean;
}) {
  const [open, setOpen] = useState(defaultOpen);
  if (!children) return null;
  return (
    <div className="rounded-xl border border-border/60 bg-background/25">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex w-full items-center justify-between gap-3 px-3 py-2 text-left"
      >
        <span className="text-[11px] font-semibold uppercase tracking-wide text-muted">
          {title}
          {typeof count === "number" ? (
            <span className="ml-1.5 rounded-full bg-background/70 px-1.5 py-0.5 text-[10px] font-medium normal-case tracking-normal text-foreground/70">
              {count}
            </span>
          ) : null}
        </span>
        {open ? <ChevronUp className="h-3.5 w-3.5 text-muted" /> : <ChevronDown className="h-3.5 w-3.5 text-muted" />}
      </button>
      {open ? <div className="border-t border-border/50 px-3 py-2.5">{children}</div> : null}
    </div>
  );
}

function ColorSwatches({ palette }: { palette: Record<string, unknown> | null }) {
  if (!palette) return null;
  const entries = ["primary", "secondary", "accent", "background", "text"]
    .map((key) => [key, palette[key]] as const)
    .filter((entry): entry is readonly [string, string] => typeof entry[1] === "string");
  if (entries.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2">
      {entries.map(([name, color]) => (
        <div key={name} className="flex items-center gap-1.5 rounded-lg border border-border bg-background/40 px-2 py-1">
          <span className="h-3.5 w-3.5 rounded-full border border-border" style={{ backgroundColor: color }} />
          <span className="text-[11px] capitalize text-muted">{name}</span>
        </div>
      ))}
    </div>
  );
}

function PagesList({ pages }: { pages: unknown }) {
  if (!Array.isArray(pages) || pages.length === 0) return null;
  return (
    <div className="space-y-2">
      {pages.slice(0, 5).map((page, index) => {
        const record = asRecord(page);
        if (!record) return null;
        const name = typeof record.name === "string" ? record.name : `Page ${index + 1}`;
        const purpose = typeof record.purpose === "string" ? record.purpose : "";
        return (
          <div key={`${name}-${index}`} className="rounded-lg border border-border/60 bg-background/30 px-3 py-2">
            <p className="text-xs font-medium text-foreground">{name}</p>
            {purpose ? <p className="mt-0.5 text-[11px] leading-relaxed text-muted">{clipSummary(purpose, 120)}</p> : null}
          </div>
        );
      })}
      {pages.length > 5 ? (
        <p className="text-[11px] text-muted">+{pages.length - 5} more pages</p>
      ) : null}
    </div>
  );
}

function MetricPills({ items }: { items: Array<{ label: string; value: string }> }) {
  if (items.length === 0) return null;
  return (
    <div className="mt-3 flex flex-wrap gap-1.5">
      {items.map((item) => (
        <span
          key={item.label}
          className="inline-flex items-center gap-1 rounded-full border border-border/70 bg-background/50 px-2.5 py-1 text-[11px] text-foreground/85"
        >
          <span className="font-medium text-foreground">{item.value}</span>
          <span className="text-muted">{item.label}</span>
        </span>
      ))}
    </div>
  );
}

function SpecBody({ result }: { result: PhaseResult }) {
  const spec = result.spec ?? null;
  if (!spec) return null;

  if (result.kind === "brief") {
    const users = asStringList(spec.target_users);
    const mvp = asStringList(spec.mvp_inclusions);
    const success = asStringList(spec.success_criteria);
    const assumptions = asStringList(spec.assumptions);
    return (
      <div className="space-y-2">
        <Section title="MVP scope" count={mvp.length} defaultOpen>
          <ItemList items={mvp} />
        </Section>
        <Section title="Success criteria" count={success.length}>
          <ItemList items={success} />
        </Section>
        <Section title="Audience" count={users.length}>
          <ItemList items={users} />
        </Section>
        <Section title="Assumptions" count={assumptions.length}>
          <ItemList items={assumptions} />
        </Section>
      </div>
    );
  }

  if (result.kind === "analysis") {
    return (
      <div className="space-y-2">
        <Section title="Recommendations" count={asStringList(spec.recommendations).length} defaultOpen>
          <ItemList items={asStringList(spec.recommendations)} />
        </Section>
        <Section title="Workflows" count={asStringList(spec.workflows).length}>
          <ItemList items={asStringList(spec.workflows)} />
        </Section>
        <Section title="Risks" count={asStringList(spec.risks).length}>
          <ItemList items={asStringList(spec.risks)} />
        </Section>
        <Section title="Evidence gaps" count={asStringList(spec.evidence_gaps).length}>
          <ItemList items={asStringList(spec.evidence_gaps)} />
        </Section>
      </div>
    );
  }

  if (result.kind === "plan") {
    return (
      <div className="space-y-2">
        <Section title="MVP features" count={asStringList(spec.mvp_features).length} defaultOpen>
          <ItemList items={asStringList(spec.mvp_features)} />
        </Section>
        <Section title="Pages" count={Array.isArray(spec.pages) ? spec.pages.length : 0} defaultOpen>
          <PagesList pages={spec.pages} />
        </Section>
        <Section title="Milestones" count={asStringList(spec.milestones).length}>
          <ItemList items={asStringList(spec.milestones)} />
        </Section>
        <Section title="Acceptance criteria" count={asStringList(spec.acceptance_criteria).length}>
          <ItemList items={asStringList(spec.acceptance_criteria)} />
        </Section>
      </div>
    );
  }

  if (result.kind === "architecture") {
    return (
      <div className="space-y-2">
        <Section title="Palette" defaultOpen>
          <ColorSwatches palette={asRecord(spec.color_palette)} />
        </Section>
        <Section title="Components" count={asStringList(spec.components).length} defaultOpen>
          <ItemList items={asStringList(spec.components)} />
        </Section>
        <Section title="Required files" count={asStringList(spec.required_files).length}>
          <ItemList items={asStringList(spec.required_files)} />
        </Section>
        <Section title="Client behavior" count={asStringList(spec.client_side_behavior).length}>
          <ItemList items={asStringList(spec.client_side_behavior)} />
        </Section>
      </div>
    );
  }

  if (result.kind === "build") {
    return (
      <div className="space-y-2">
        <Section title="Files written" count={asStringList(spec.files_written).length} defaultOpen>
          <ItemList items={asStringList(spec.files_written)} />
        </Section>
        <Section title="Behaviors" count={asStringList(spec.behaviors_implemented).length} defaultOpen>
          <ItemList items={asStringList(spec.behaviors_implemented)} />
        </Section>
        <Section title="Known gaps" count={asStringList(spec.known_gaps).length}>
          <ItemList items={asStringList(spec.known_gaps)} empty="No known gaps reported." />
        </Section>
      </div>
    );
  }

  return null;
}

const kindMeta: Record<
  PhaseResultKind,
  { icon: typeof Sparkles; label: string }
> = {
  brief: { icon: Sparkles, label: "Brief" },
  analysis: { icon: ListChecks, label: "Analysis" },
  plan: { icon: ListChecks, label: "Plan" },
  architecture: { icon: Palette, label: "Architecture" },
  build: { icon: FileCode2, label: "Build" },
  markdown: { icon: Sparkles, label: "Update" },
};

function metricsForResult(result: PhaseResult): Array<{ label: string; value: string }> {
  const spec = result.spec ?? {};
  if (result.kind === "brief") {
    return [
      { label: "users", value: String(asStringList(spec.target_users).length) },
      { label: "MVP items", value: String(asStringList(spec.mvp_inclusions).length) },
      { label: "criteria", value: String(asStringList(spec.success_criteria).length) },
    ].filter((item) => item.value !== "0");
  }
  if (result.kind === "plan") {
    return [
      { label: "features", value: String(asStringList(spec.mvp_features).length) },
      /* v8 ignore next -- pages is almost always an array from the schema */
      { label: "pages", value: String(Array.isArray(spec.pages) ? spec.pages.length : 0) },
      { label: "milestones", value: String(asStringList(spec.milestones).length) },
    ].filter((item) => item.value !== "0");
  }
  if (result.kind === "analysis") {
    return [
      { label: "recs", value: String(asStringList(spec.recommendations).length) },
      { label: "risks", value: String(asStringList(spec.risks).length) },
    ].filter((item) => item.value !== "0");
  }
  if (result.kind === "architecture") {
    return [
      { label: "components", value: String(asStringList(spec.components).length) },
      { label: "files", value: String(asStringList(spec.required_files).length) },
    ].filter((item) => item.value !== "0");
  }
  if (result.kind === "build") {
    return [
      { label: "files", value: String(asStringList(spec.files_written).length) },
      { label: "behaviors", value: String(asStringList(spec.behaviors_implemented).length) },
    ].filter((item) => item.value !== "0");
  }
  return [];
}

export function PhaseResultCard({ result }: { result: PhaseResult }) {
  const [expanded, setExpanded] = useState(false);
  const agent = AGENTS.find((item) => item.id === result.agent);
  /* v8 ignore next -- unknown kind falls back to markdown presentation */
  const meta = kindMeta[result.kind] ?? kindMeta.markdown;
  const Icon = meta.icon;
  const headline = humanizeHeadline(result.headline, "Phase complete");
  const summary = clipSummary(humanizeText(result.summary, headline));
  const hasDetails = Boolean(result.spec) && Object.keys(result.spec ?? {}).length > 0;
  // Cheap pure derivation — avoid manual useMemo so React Compiler can optimize freely.
  const metrics = metricsForResult(result);

  return (
    <div className="flex gap-3 py-2 animate-slide-up">
      {agent ? <Avatar name={agent.name} color={agent.color} size="sm" /> : null}
      <div className="min-w-0 flex-1">
        {agent ? (
          <p className="mb-1 text-xs font-medium" style={{ color: agent.color }}>
            {agent.name} — {agent.role}
          </p>
        ) : null}
        <div
          className={cn(
            "max-w-[92%] rounded-2xl rounded-tl-md border px-4 py-3 text-sm shadow-sm",
            agent ? getAgentBgColor(agent.id) : "border-border bg-surface"
          )}
        >
          <div className="flex items-start gap-2.5">
            <div className="mt-0.5 rounded-lg border border-border/70 bg-background/45 p-1.5 text-accent">
              <Icon className="h-3.5 w-3.5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <p className="font-semibold text-foreground">{headline}</p>
                <span className="rounded-full border border-border/70 bg-background/40 px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide text-muted">
                  {meta.label}
                </span>
              </div>
              {/* v8 ignore next -- empty summaries are collapsed by humanizeText fallbacks */}
              {summary ? (
                <p className="mt-1.5 text-[13px] leading-relaxed text-foreground/90">{summary}</p>
              ) : null}
              <MetricPills items={metrics} />
            </div>
            {hasDetails ? (
              <button
                type="button"
                onClick={() => setExpanded((value) => !value)}
                className="inline-flex shrink-0 items-center gap-1 rounded-md px-1.5 py-1 text-[11px] text-accent hover:bg-background/40 hover:text-accent/90"
              >
                {expanded ? <ChevronUp className="h-3 w-3" /> : <ChevronDown className="h-3 w-3" />}
                {expanded ? "Hide" : "Details"}
              </button>
            ) : (
              <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400/80" />
            )}
          </div>

          {expanded && hasDetails ? (
            <div className="mt-3 border-t border-border/50 pt-3">
              <SpecBody result={result} />
            </div>
          ) : null}

          {!expanded && hasDetails ? (
            <div className="mt-3 flex items-center gap-2 text-[11px] text-muted">
              <Users className="h-3.5 w-3.5" />
              <span>{FOOTER_BY_KIND[result.kind] ?? FOOTER_BY_KIND.markdown}</span>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
