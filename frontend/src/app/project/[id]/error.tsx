"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function ProjectError({
  error,
  unstable_retry,
}: {
  error: Error & { digest?: string };
  unstable_retry: () => void;
}) {
  useEffect(() => {
    console.error(error);
  }, [error]);

  return (
    <div className="flex h-screen items-center justify-center bg-background px-6">
      <div className="max-w-md rounded-2xl border border-border bg-surface p-8 text-center shadow-lg">
        <h1 className="text-2xl font-semibold text-foreground">Workspace crashed</h1>
        <p className="mt-3 text-sm text-muted">
          The project workspace hit an unexpected error. Your generated files remain on the server.
        </p>
        {error.digest && (
          <p className="mt-3 font-mono text-xs text-muted">Error ID: {error.digest}</p>
        )}
        <Button onClick={() => unstable_retry()} className="mt-6">
          Reload workspace
        </Button>
      </div>
    </div>
  );
}
