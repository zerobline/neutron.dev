"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAuthStore } from "@/stores/auth-store";

export function LoginForm() {
  const router = useRouter();
  const login = useAuthStore((s) => s.login);
  const register = useAuthStore((s) => s.register);
  const loading = useAuthStore((s) => s.loading);
  const error = useAuthStore((s) => s.error);
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [displayName, setDisplayName] = useState("");

  const handleSubmit = async (event: FormEvent) => {
    event.preventDefault();
    if (mode === "register") {
      await register(email, password, displayName);
    } else {
      await login(email, password);
    }
    router.push("/dashboard");
  };

  return (
    <div className="w-full max-w-md rounded-2xl border border-border bg-surface p-6 shadow-sm">
      <div className="mb-6">
        <h1 className="text-2xl font-semibold text-foreground">
          {mode === "register" ? "Create your account" : "Log in to Neutron"}
        </h1>
        <p className="mt-2 text-sm text-muted">
          Save your projects and use your own LLM provider keys.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="space-y-4">
        {mode === "register" && (
          <label className="block text-sm font-medium text-foreground">
            Display name
            <Input
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="Your name"
              className="mt-1"
            />
          </label>
        )}
        <label className="block text-sm font-medium text-foreground">
          Email
          <Input
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            type="email"
            autoComplete="email"
            required
            placeholder="you@example.com"
            className="mt-1"
          />
        </label>
        <label className="block text-sm font-medium text-foreground">
          Password
          <Input
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            type="password"
            autoComplete={mode === "register" ? "new-password" : "current-password"}
            minLength={8}
            required
            placeholder="At least 8 characters"
            className="mt-1"
          />
        </label>

        {error && (
          <p className="rounded-lg border border-red-500/20 bg-red-500/10 px-3 py-2 text-sm text-red-400">
            {error}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={loading}>
          {loading ? "Working..." : mode === "register" ? "Create account" : "Log in"}
        </Button>
      </form>

      <button
        type="button"
        onClick={() => setMode(mode === "register" ? "login" : "register")}
        className="mt-4 text-sm text-accent hover:text-accent/80"
      >
        {mode === "register" ? "Already have an account? Log in" : "Need an account? Create one"}
      </button>
    </div>
  );
}
