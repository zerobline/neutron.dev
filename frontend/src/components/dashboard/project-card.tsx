import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Project } from "@/types";
import { Clock, FolderOpen, Trash2 } from "lucide-react";

const statusVariant: Record<string, "default" | "success" | "warning" | "error" | "info"> = {
  created: "default",
  leading: "info",
  analyzing: "info",
  planning: "info",
  architecting: "info",
  building: "warning",
  awaiting_feedback: "warning",
  complete: "success",
  error: "error",
};

interface ProjectCardProps {
  project: Project;
  onDelete?: (project: Project) => void;
}

export function ProjectCard({ project, onDelete }: ProjectCardProps) {
  return (
    <Card className="relative h-full hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5 group">
      <Link href={`/project/${project.id}`} className="block h-full cursor-pointer" aria-label={`Open ${project.name}`}>
        <CardContent className={onDelete ? "pr-12" : undefined}>
          <div className="flex items-start justify-between mb-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-accent/10 text-accent group-hover:bg-accent/20 transition-colors">
              <FolderOpen className="h-5 w-5" />
            </div>
            <Badge variant={statusVariant[project.status] ?? "default"}>
              {project.status}
            </Badge>
          </div>
          <h3 className="font-semibold text-foreground mb-1 truncate">{project.name}</h3>
          <p className="text-sm text-muted line-clamp-2 mb-3">{project.description}</p>
          <div className="flex items-center gap-1.5 text-xs text-muted">
            <Clock className="h-3 w-3" />
            {new Date(project.created_at).toLocaleDateString()}
          </div>
        </CardContent>
      </Link>
      {onDelete ? (
        <Button
          type="button"
          variant="danger"
          size="sm"
          className="absolute right-6 top-6 px-2"
          aria-label={`Delete ${project.name}`}
          onClick={() => onDelete(project)}
        >
          <Trash2 className="h-3.5 w-3.5" />
        </Button>
      ) : null}
    </Card>
  );
}
