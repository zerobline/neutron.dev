import type { ProjectFile } from "@/types";

/** Neutron-internal paths that must not appear as user project artifacts. */
const HIDDEN_FILE_NAMES = new Set(["connectors.json", "skills.json"]);
const HIDDEN_DIR_NAMES = new Set([".neutron", "__pycache__", ".git", "skills"]);

export function isWorkspaceVisibleFile(filePath: string): boolean {
  const rel = filePath.replace(/\\/g, "/").replace(/^\.\//, "");
  if (!rel) return false;
  const parts = rel.split("/").filter(Boolean);
  if (parts.some((part) => HIDDEN_DIR_NAMES.has(part))) return false;
  if (HIDDEN_FILE_NAMES.has(parts[parts.length - 1] ?? "")) return false;
  return true;
}

export function filterWorkspaceFiles(files: ProjectFile[]): ProjectFile[] {
  return files.filter((file) => isWorkspaceVisibleFile(file.file_path));
}
