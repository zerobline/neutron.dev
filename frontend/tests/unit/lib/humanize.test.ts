import { describe, expect, it } from "vitest";
import {
  humanizeHeadline,
  humanizeText,
  looksLikeInventory,
  looksLikeJsonBlob,
} from "@/lib/humanize";

describe("humanize", () => {
  it("detects json blobs", () => {
    expect(looksLikeJsonBlob('{"headline":"x","summary":"y"}')).toBe(true);
    expect(looksLikeJsonBlob("Plain prose summary")).toBe(false);
    expect(looksLikeJsonBlob("  ")).toBe(false);
  });

  it("extracts human fields from json", () => {
    const blob = '{"headline":"Admin Dashboard","summary":"A polished admin UI with analytics."}';
    expect(humanizeText(blob)).toBe("A polished admin UI with analytics.");
    expect(humanizeHeadline(blob)).toBe("Admin Dashboard");
  });

  it("falls back when json is unusable", () => {
    expect(humanizeText("{broken", "Fallback")).toBe("Fallback");
    expect(humanizeHeadline("{broken", "Phase complete")).toBe("Phase complete");
    expect(humanizeText(null, "Empty")).toBe("Empty");
    expect(humanizeText("", "Empty")).toBe("Empty");
  });

  it("clips long plain text and prefers list fields in objects", () => {
    const long = "word ".repeat(100);
    expect(humanizeText(long).endsWith("…")).toBe(true);
    const fromLists = JSON.stringify({
      recommendations: ["Ship MVP", "Add auth"],
      risks: ["scope creep"],
    });
    expect(humanizeText(fromLists)).toContain("Ship MVP");
    expect(humanizeHeadline(JSON.stringify({ title: "Launch Plan" }))).toBe("Launch Plan");
    expect(humanizeHeadline(JSON.stringify({ name: "Named" }))).toBe("Named");
    expect(humanizeHeadline(JSON.stringify({ overview: "From overview field that is long enough" }))).toContain(
      "From overview",
    );
  });

  it("returns fallback for arrays and non-object JSON", () => {
    expect(humanizeText("[1,2,3]", "Array")).toBe("Array");
    expect(humanizeHeadline("[1,2,3]", "Phase complete")).toBe("Phase complete");
    expect(humanizeText("{}", "Empty object")).toBe("Empty object");
    expect(humanizeHeadline('{"summary":"{\\"nested\\":true}"}', "Phase complete")).toBe(
      "Phase complete",
    );
  });

  it("parses fenced JSON and embedded objects", () => {
    const fenced = '```json\n{"headline":"Fenced","summary":"From fence"}\n```';
    expect(humanizeText(fenced)).toBe("From fence");
    expect(humanizeHeadline(fenced)).toBe("Fenced");
    const noisy = 'prefix {"headline":"Embedded","summary":"Middle"} suffix';
    expect(looksLikeJsonBlob(noisy)).toBe(true);
    expect(humanizeText(noisy)).toBe("Middle");
    expect(humanizeText('{"mvp_features":["A","B"]}')).toContain("A");
    expect(humanizeText('{"recommendations":["",1,"ok"]}')).toContain("ok");
    expect(humanizeHeadline(null as unknown as string, "Default")).toBe("Default");
  });

  it("rejects markdown file inventories and keeps prose summaries", () => {
    const inventory =
      "## Files written\n\n- index.html\n- styles.css\n- app.js\n\n## Behaviors implemented\n\n- Tabs\n";
    expect(looksLikeInventory(inventory)).toBe(true);
    expect(humanizeText(inventory, "Project files ready")).toBe("Project files ready");
    expect(humanizeHeadline(inventory, "Project files ready")).toBe("Project files ready");

    const withProse =
      "Built a fraud operations console with alert triage.\n\n## Files written\n\n- index.html\n- styles.css\n";
    expect(humanizeText(withProse)).toContain("fraud operations console");
  });
});
