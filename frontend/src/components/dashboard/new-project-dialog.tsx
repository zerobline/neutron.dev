"use client";

import { useState } from "react";
import { Dialog, DialogTitle, DialogDescription } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";

interface NewProjectDialogProps {
  open: boolean;
  onClose: () => void;
  onCreate: (name: string, description: string) => void;
  initialDescription?: string;
}

export function NewProjectDialog({ open, onClose, onCreate, initialDescription }: NewProjectDialogProps) {
  const [name, setName] = useState("");
  const [description, setDescription] = useState(initialDescription ?? "");

  const handleCreate = () => {
    /* v8 ignore if */
    if (!name.trim() || !description.trim()) return;
    onCreate(name.trim(), description.trim());
    setName("");
    setDescription("");
  };

  return (
    <Dialog open={open} onClose={onClose}>
      <DialogTitle>New Project</DialogTitle>
      <DialogDescription>
        Describe what you want to build. Our AI agents will handle the rest.
      </DialogDescription>

      <div className="space-y-4">
        <div>
          <label htmlFor="project-name" className="block text-sm font-medium text-foreground mb-1.5">
            Project Name
          </label>
          <Input
            id="project-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="My Awesome App"
          />
        </div>
        <div>
          <label htmlFor="project-description" className="block text-sm font-medium text-foreground mb-1.5">
            Description
          </label>
          <Textarea
            id="project-description"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Build a modern dashboard with analytics charts, user management, and real-time notifications..."
            rows={4}
          />
        </div>
        <div className="flex justify-end gap-3 pt-2">
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button onClick={handleCreate} disabled={!name.trim() || !description.trim()}>
            Create Project
          </Button>
        </div>
      </div>
    </Dialog>
  );
}
