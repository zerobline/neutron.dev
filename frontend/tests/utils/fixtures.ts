import type { Message, Project, ProjectFile, Template } from "@/types";

export const projectFixture: Project = {
  id: "project-1",
  name: "Project One",
  description: "Build a test app",
  status: "created",
  template: null,
  created_at: "2026-01-02T00:00:00.000Z",
  updated_at: "2026-01-03T00:00:00.000Z",
};

export const templateFixture: Template = {
  id: "saas",
  name: "SaaS App",
  description: "A SaaS template",
  category: "Business",
  icon: "rocket",
  prompt: "Build a SaaS app",
};

export const messageFixture: Message = {
  id: "m1",
  role: "system",
  content: "System ready",
  timestamp: 1000,
};

export const fileFixture: ProjectFile = {
  file_path: "index.html",
  content: "<html><head></head><body>Hello</body></html>",
};
