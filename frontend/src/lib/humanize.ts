/** Detect and humanize model/provider JSON blobs before they hit chat UI. */

const INVENTORY_HEADING_RE =
  /^(?:#{1,6}\s*)?(?:files?\s+written|file\s+list|files?\s+created|files?\s+updated|behaviors?\s+implemented|known\s+gaps?|implementation\s+notes?|what\s+was\s+built|output\s+files?|project\s+files?)\b/i;
const FILE_LIKE_LINE_RE =
  /^(?:[-*•]\s+)?[`'"]?[\w./\\-]+\.(html|css|js|ts|tsx|jsx|json|md|py|svg|txt)[`'"]?\s*$/i;
const BULLET_LINE_RE = /^[-*•]\s+\S/;

export function looksLikeJsonBlob(text: string | null | undefined): boolean {
  const cleaned = (text ?? "").trim();
  if (!cleaned) return false;
  if (cleaned.startsWith("{") || cleaned.startsWith("[")) return true;
  if (cleaned.startsWith("```")) return true;
  if (cleaned.includes('"headline"') && cleaned.includes('"summary"')) return true;
  return false;
}

/** True when text is mostly a file/behavior inventory dump, not a human summary. */
export function looksLikeInventory(text: string | null | undefined): boolean {
  const cleaned = (text ?? "").trim();
  if (!cleaned) return false;
  const firstLine = cleaned.split("\n", 1)[0]?.trim() ?? "";
  if (INVENTORY_HEADING_RE.test(firstLine)) return true;

  const headingMatches = cleaned.match(
    /(?:^|\n)(?:#{1,6}\s*)?(?:files?\s+written|file\s+list|files?\s+created|behaviors?\s+implemented|known\s+gaps?)\b/gi,
  );
  if (headingMatches && headingMatches.length >= 1 && cleaned.includes("\n")) {
    const lines = cleaned.split("\n").map((ln) => ln.trim()).filter(Boolean);
    const nonHeading = lines.filter((ln) => !ln.startsWith("#"));
    if (nonHeading.length === 0) return true;
    const fileLike = nonHeading.filter((ln) => FILE_LIKE_LINE_RE.test(ln)).length;
    const bullets = nonHeading.filter((ln) => BULLET_LINE_RE.test(ln)).length;
    if (fileLike >= 2 || (bullets >= 3 && fileLike + bullets >= nonHeading.length * 0.6)) {
      return true;
    }
  }

  const lines = cleaned.split("\n").map((ln) => ln.trim()).filter(Boolean);
  if (lines.length >= 2) {
    const fileLike = lines.filter((ln) => FILE_LIKE_LINE_RE.test(ln)).length;
    if (fileLike >= Math.max(2, Math.floor(lines.length * 0.6))) return true;
  }
  return false;
}

function tryParseJson(text: string): unknown {
  const cleaned = text.trim();
  const candidates = [cleaned];

  const fence = cleaned.match(/```(?:json)?\s*([\s\S]*?)```/i);
  if (fence?.[1]) candidates.push(fence[1].trim());

  const start = cleaned.indexOf("{");
  const end = cleaned.lastIndexOf("}");
  if (start >= 0 && end > start) {
    candidates.push(cleaned.slice(start, end + 1));
  }

  for (const candidate of candidates) {
    try {
      return JSON.parse(candidate);
    } catch {
      // continue
    }
  }
  return null;
}

function clip(text: string, limit = 320): string {
  const cleaned = text.replace(/\s+/g, " ").trim();
  if (cleaned.length <= limit) return cleaned;
  return `${cleaned.slice(0, limit - 1).trimEnd()}…`;
}

function summaryFromObject(data: Record<string, unknown>): string {
  for (const key of ["summary", "overview", "user_intent", "system_overview", "headline", "title"]) {
    const value = data[key];
    if (typeof value === "string" && value.trim() && !looksLikeJsonBlob(value)) {
      return clip(value);
    }
  }
  for (const key of ["recommendations", "mvp_features", "workflows", "behaviors_implemented"]) {
    const value = data[key];
    if (Array.isArray(value)) {
      const items = value.filter((item): item is string => typeof item === "string" && item.trim().length > 0);
      /* v8 ignore next -- empty filtered arrays fall through to the final return */
      if (items.length > 0) return clip(items.slice(0, 3).join("; "));
    }
  }
  return "";
}

function proseFromInventory(text: string): string {
  const blocks = text
    .split(/\n\n+/)
    .map((block) => block.trim())
    .filter(Boolean);
  for (const block of blocks) {
    if (block.startsWith("#") || block.startsWith("```")) continue;
    if (looksLikeJsonBlob(block) || looksLikeInventory(block)) continue;
    if (BULLET_LINE_RE.test(block) || FILE_LIKE_LINE_RE.test(block)) continue;
    return clip(block);
  }
  return "";
}

export function humanizeText(text: string | null | undefined, fallback = ""): string {
  const cleaned = (text ?? "").trim();
  if (!cleaned) return fallback;
  if (looksLikeJsonBlob(cleaned)) {
    const parsed = tryParseJson(cleaned);
    if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
      return summaryFromObject(parsed as Record<string, unknown>) || fallback;
    }
    return fallback;
  }
  if (looksLikeInventory(cleaned)) {
    return proseFromInventory(cleaned) || fallback;
  }
  return clip(cleaned);
}

export function humanizeHeadline(text: string | null | undefined, fallback = "Phase complete"): string {
  const cleaned = (text ?? "").trim();
  if (!cleaned || looksLikeJsonBlob(cleaned) || looksLikeInventory(cleaned)) {
    if (looksLikeJsonBlob(cleaned)) {
      const parsed = tryParseJson(cleaned);
      if (parsed && typeof parsed === "object" && !Array.isArray(parsed)) {
        const data = parsed as Record<string, unknown>;
        for (const key of ["headline", "title", "name"]) {
          const value = data[key];
          if (typeof value === "string" && value.trim() && !looksLikeJsonBlob(value)) {
            return clip(value, 80);
          }
        }
        const summary = summaryFromObject(data);
        if (summary) return clip(summary, 80);
      }
    }
    if (looksLikeInventory(cleaned)) {
      const prose = proseFromInventory(cleaned);
      if (prose) return clip(prose, 80);
    }
    return fallback;
  }
  return clip(cleaned, 80);
}
