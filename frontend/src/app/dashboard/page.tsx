"use client";

import { Suspense, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { ProjectCard } from "@/components/dashboard/project-card";
import { DeleteProjectDialog } from "@/components/dashboard/delete-project-dialog";
import { PromptInput } from "@/components/dashboard/prompt-input";
import { ConnectorsModal } from "@/components/dashboard/connectors-modal";
import { SkillsPanel } from "@/components/workspace/skills-panel";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import {
  countEnabledLocalSkills,
  getBuildConnectorPayload,
  getBuildSkillPayload,
  getLocalCustomSkills,
} from "@/lib/local-settings";
import { useAuthStore } from "@/stores/auth-store";
import type { BuildMode, Project } from "@/types";
import type { DashboardBuildMode } from "@/components/dashboard/build-mode-dropdown";
import { Plug, GitBranch, BarChart3, Database, Sparkles } from "lucide-react";

const buildModeByDashboardMode: Record<DashboardBuildMode, BuildMode> = {
  build: "team",
  goal: "goal",
};

function DashboardContent() {
  const router = useRouter();
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [templatePrompt, setTemplatePrompt] = useState("");
  const [templateMeta, setTemplateMeta] = useState<{ id?: string; stack?: string }>({});
  const [connectorsOpen, setConnectorsOpen] = useState(false);
  const [skillsOpen, setSkillsOpen] = useState(false);
  const [enabledSkillsCount, setEnabledSkillsCount] = useState(() => countEnabledLocalSkills());
  const [createError, setCreateError] = useState<string | null>(null);
  const [projectToDelete, setProjectToDelete] = useState<Project | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const [loadError, setLoadError] = useState(false);
  const user = useAuthStore((s) => s.user);
  const authLoading = useAuthStore((s) => s.loading);

  useEffect(() => {
    if (authLoading) return;
    if (!user) {
      return;
    }
    api.listProjects()
      .then((p) => setProjects(p as Project[]))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));

    const templateId = new URLSearchParams(window.location.search).get("template");
    if (templateId) {
      api
        .getTemplate(templateId)
        .then((t) => {
          const tmpl = t as { id?: string; prompt?: string; stack?: string };
          /* v8 ignore next */
          if (typeof tmpl.prompt !== "string") return;
          if (tmpl.prompt.length === 0) return;
          setTemplatePrompt(tmpl.prompt);
          setTemplateMeta({
            id: typeof tmpl.id === "string" ? tmpl.id : templateId,
            stack: typeof tmpl.stack === "string" ? tmpl.stack : "static",
          });
        })
        .catch(() => setCreateError("Could not load template."));
    }
  }, [authLoading, user]);

  const handleSubmit = async (
    prompt: string,
    mode: DashboardBuildMode,
    files: File[],
    stack: "static" | "nextjs" = "static",
  ) => {
    if (!user) {
      router.push("/login");
      return;
    }
    setCreateError(null);
    setSubmitting(true);
    try {
      const name = prompt.length > 50 ? prompt.slice(0, 50) + "..." : prompt;
      // Explicit stack from the prompt UI wins; templates pre-select Next.js when relevant.
      const resolvedStack = stack || templateMeta.stack || "static";
      const project = (await api.createProject({
        name,
        description: prompt,
        ...(templateMeta.id ? { template: templateMeta.id } : {}),
        stack: resolvedStack,
      })) as Project;
      for (const file of files) {
        await api.uploadFile(project.id, file);
      }
      await api.saveProjectConnectors(project.id, getBuildConnectorPayload());
      // Attach dashboard skill drafts (custom packs first, then full assignment list).
      for (const custom of getLocalCustomSkills()) {
        await api.createProjectSkill(project.id, {
          name: custom.name,
          description: custom.description,
          body: custom.body,
          agents: custom.agents,
          enabled: custom.enabled,
        });
      }
      const skillPayload = getBuildSkillPayload();
      if (skillPayload.length > 0) {
        await api.saveProjectSkills(project.id, skillPayload);
      }
      const buildMode = buildModeByDashboardMode[mode];
      router.push(`/project/${project.id}?autostart=true&mode=${buildMode}`);
    } catch {
      setCreateError("Could not create the project. Please try again.");
      setSubmitting(false);
    }
  };

  const handleRequestDelete = (project: Project) => {
    setDeleteError(null);
    setProjectToDelete(project);
  };

  const handleCancelDelete = () => {
    setProjectToDelete(null);
    setDeleteError(null);
  };

  const handleCloseSkills = () => {
    setEnabledSkillsCount(countEnabledLocalSkills());
    setSkillsOpen(false);
  };

  const handleConfirmDelete = async () => {
    /* v8 ignore next */
    if (!projectToDelete) return;
    setDeleteError(null);
    setDeletingId(projectToDelete.id);
    try {
      await api.deleteProject(projectToDelete.id);
      setProjects((items) => items.filter((p) => p.id !== projectToDelete.id));
      setProjectToDelete(null);
    } catch {
      setDeleteError("Could not delete project. Try again.");
    } finally {
      setDeletingId(null);
    }
  };

  if (!authLoading && !user) {
    return (
      <main className="flex-1 min-h-[calc(100vh-4rem)]">
        <div className="mx-auto max-w-2xl px-6 pt-20 pb-12 text-center">
          <h1 className="text-3xl font-bold text-foreground mb-3">Log in to start building.</h1>
          <p className="text-sm text-muted mb-6">Projects and provider keys are saved to your account.</p>
          <Link href="/login" className="inline-flex items-center justify-center rounded-lg bg-accent px-4 py-2 text-sm font-medium text-white shadow-lg shadow-accent/25 transition-all duration-200 hover:bg-accent-hover focus:outline-none focus:ring-2 focus:ring-accent/50">Log in</Link>
        </div>
      </main>
    );
  }

  return (
    <>
      <main className="flex-1 min-h-[calc(100vh-4rem)]">
        <div className="mx-auto max-w-2xl px-6 pt-20 pb-12">
          <div className="flex justify-center mb-5">
            <div className="rounded-full border border-border bg-surface px-3 py-1 text-xs text-muted">
              Create products with Neutron
            </div>
          </div>
          <h1 className="text-3xl font-bold text-foreground text-center mb-2">
            Your next product starts here.
          </h1>
          <p className="text-sm text-muted text-center mb-8">
            Ask the team to bring your idea to life.
          </p>
          <PromptInput
            key={`${templatePrompt}:${templateMeta.stack ?? "static"}`}
            onSubmit={handleSubmit}
            initialValue={templatePrompt}
            initialStack={templateMeta.stack === "nextjs" ? "nextjs" : "static"}
            disabled={submitting}
            onOpenConnectors={() => setConnectorsOpen(true)}
          />
          {createError && (
            <p className="mt-3 rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400">
              {createError}
            </p>
          )}
          <div className="mt-2 grid grid-cols-1 sm:grid-cols-2 gap-2">
            <button
              type="button"
              onClick={() => setConnectorsOpen(true)}
              className="w-full rounded-2xl border border-border bg-surface-hover/60 px-4 py-2.5 text-left text-sm text-muted hover:text-foreground transition-colors cursor-pointer"
            >
              <span className="inline-flex items-center gap-2">
                <Plug className="h-4 w-4" />
                Connectors
                <span className="ml-1 inline-flex items-center gap-1 text-accent">
                  <GitBranch className="h-3.5 w-3.5" />
                  <Database className="h-3.5 w-3.5" />
                  <BarChart3 className="h-3.5 w-3.5" />
                </span>
              </span>
            </button>
            <button
              type="button"
              onClick={() => setSkillsOpen(true)}
              className="w-full rounded-2xl border border-border bg-surface-hover/60 px-4 py-2.5 text-left text-sm text-muted hover:text-foreground transition-colors cursor-pointer"
            >
              <span className="inline-flex items-center gap-2">
                <Sparkles className="h-4 w-4 text-accent" />
                Team Skills
                {enabledSkillsCount > 0 ? (
                  <span className="rounded-full bg-accent/15 px-1.5 py-0.5 text-[10px] text-accent">
                    {enabledSkillsCount} enabled
                  </span>
                ) : (
                  <span className="text-xs text-muted">Optional</span>
                )}
              </span>
            </button>
          </div>
        </div>

        <div className="mx-auto max-w-7xl px-6 pb-10">
          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {Array.from({ length: 3 }).map((_, i) => (
                <Skeleton key={i} className="h-48 rounded-xl" />
              ))}
            </div>
          ) : loadError ? (
            <p className="text-center text-sm text-red-400">Unable to load projects. Please try again later.</p>
          ) : projects.length > 0 ? (
            <section className="rounded-3xl border border-border bg-surface/60 p-6">
              <div className="flex items-center gap-4 text-sm mb-5">
                <span className="rounded-full bg-background px-4 py-2 font-medium text-foreground">My Projects</span>
                <Link href="/templates" className="text-muted hover:text-foreground transition-colors">Templates</Link>
              </div>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                {projects.map((p) => (
                  <ProjectCard key={p.id} project={p} onDelete={handleRequestDelete} />
                ))}
              </div>
            </section>
          ) : (
            <section className="rounded-3xl border border-dashed border-border bg-surface/40 p-8 text-center">
              <h2 className="text-lg font-semibold text-foreground mb-2">No projects yet</h2>
              <p className="text-sm text-muted mb-4 max-w-md mx-auto">
                Describe what you want to build above, or start from a template. Connect an AI provider in Settings before your first build.
              </p>
              <Link href="/templates" className="inline-flex items-center justify-center rounded-lg border border-border bg-background px-4 py-2 text-sm font-medium text-foreground hover:bg-surface-hover transition-colors">
                Browse templates
              </Link>
            </section>
          )}
        </div>
      </main>

      <ConnectorsModal open={connectorsOpen} onClose={() => setConnectorsOpen(false)} />
      <SkillsPanel open={skillsOpen} onClose={handleCloseSkills} />
      <DeleteProjectDialog
        project={projectToDelete}
        open={projectToDelete !== null}
        deleting={deletingId === projectToDelete?.id}
        error={deleteError}
        onClose={handleCancelDelete}
        onConfirm={handleConfirmDelete}
      />
    </>
  );
}

export default function DashboardPage() {
  return (
    <>
      <Header />
      <Suspense
        fallback={
          <main className="flex-1">
            <div className="mx-auto max-w-2xl px-6 pt-16 pb-12">
              <Skeleton className="h-8 w-64 mx-auto mb-2" />
              <Skeleton className="h-4 w-48 mx-auto mb-8" />
              <Skeleton className="h-24 rounded-2xl" />
            </div>
          </main>
        }
      >
        <DashboardContent />
      </Suspense>
      <Footer />
    </>
  );
}
