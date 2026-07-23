"use client";

import { Dialog, DialogDescription, DialogTitle } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import type { Project } from "@/types";

interface DeleteProjectDialogProps {
  project: Project | null;
  open: boolean;
  deleting: boolean;
  error: string | null;
  onClose: () => void;
  onConfirm: () => void;
}

export function DeleteProjectDialog({
  project,
  open,
  deleting,
  error,
  onClose,
  onConfirm,
}: DeleteProjectDialogProps) {
  const handleClose = () => {
    if (!deleting) onClose();
  };

  return (
    <Dialog open={open} onClose={handleClose}>
      <DialogTitle>Delete project?</DialogTitle>
      <DialogDescription>
        This will permanently delete {project ? `“${project.name}”` : "this project"} and its generated files.
        This action cannot be undone.
      </DialogDescription>

      <div className="space-y-4">
        {error ? <p className="text-sm text-red-400">{error}</p> : null}
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose} disabled={deleting}>
            Cancel
          </Button>
          <Button variant="danger" onClick={onConfirm} disabled={deleting || !project}>
            {deleting ? "Deleting..." : "Delete Project"}
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
