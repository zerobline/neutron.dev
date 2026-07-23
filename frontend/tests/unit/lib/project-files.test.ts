import { describe, expect, it } from "vitest";
import { filterWorkspaceFiles, isWorkspaceVisibleFile } from "@/lib/project-files";

describe("project-files visibility", () => {
  it("hides connectors.json, skills.json, skills dir, and neutron internals", () => {
    expect(isWorkspaceVisibleFile("connectors.json")).toBe(false);
    expect(isWorkspaceVisibleFile("skills.json")).toBe(false);
    expect(isWorkspaceVisibleFile("skills/brand-voice/SKILL.md")).toBe(false);
    expect(isWorkspaceVisibleFile(".neutron/last_edit.json")).toBe(false);
    expect(isWorkspaceVisibleFile("index.html")).toBe(true);
    expect(isWorkspaceVisibleFile("app.js")).toBe(true);
    expect(isWorkspaceVisibleFile("uploads/note.txt")).toBe(true);
  });

  it("filters mixed file lists", () => {
    const files = filterWorkspaceFiles([
      { file_path: "index.html", content: "<html></html>" },
      { file_path: "connectors.json", content: "{}" },
      { file_path: "skills.json", content: "{}" },
      { file_path: "skills/foo/SKILL.md", content: "---" },
      { file_path: ".neutron/last_edit.json", content: "{}" },
      { file_path: "styles.css", content: "body{}" },
    ]);
    expect(files.map((f) => f.file_path)).toEqual(["index.html", "styles.css"]);
  });
});
