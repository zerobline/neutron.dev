"use client";

import { useEffect } from "react";
import { Button } from "@/components/ui/button";

export default function Error({
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
    <main className="flex min-h-screen items-center justify-center bg-background px-6">
      <div className="max-w-md rounded-2xl border border-border bg-surface p-8 text-center shadow-lg">
        <h1 className="text-2xl font-semibold text-foreground">Something went wrong</h1>
        <p className="mt-3 text-sm text-muted">
          The app hit an unexpected error. Try again or refresh the page.
        </p>
        {error.digest && (
          <p className="mt-3 font-mono text-xs text-muted">Error ID: {error.digest}</p>
        )}
        <Button onClick={() => unstable_retry()} className="mt-6">
          Try again
        </Button>
      </div>
    </main>
  );
}
