"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Avatar } from "@/components/ui/avatar";
import { AGENTS } from "@/types";
import { ArrowRight, Sparkles } from "lucide-react";

export function Hero() {
  return (
    <section className="relative overflow-hidden py-24 md:py-32">
      {/* Background gradient orbs */}
      <div className="absolute inset-0 -z-10">
        <div className="absolute top-1/4 left-1/2 -translate-x-1/2 w-[800px] h-[600px] bg-accent/8 rounded-full blur-[120px]" />
        <div className="absolute top-1/3 left-1/3 w-[400px] h-[400px] bg-leader/5 rounded-full blur-[100px]" />
        <div className="absolute top-1/2 right-1/4 w-[300px] h-[300px] bg-architect/5 rounded-full blur-[80px]" />
      </div>

      {/* Subtle grid overlay */}
      <div
        className="absolute inset-0 -z-10 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(var(--foreground) 1px, transparent 1px), linear-gradient(90deg, var(--foreground) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <div className="mx-auto max-w-4xl px-6 text-center">
        {/* Badge */}
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-accent/20 bg-accent/5 px-4 py-1.5 text-sm text-accent">
          <Sparkles className="h-4 w-4" />
          Public beta, built with CrewAI
        </div>

        {/* Headline */}
        <h1 className="text-5xl md:text-7xl font-bold tracking-tight text-foreground mb-6 leading-[1.1]">
          Turn an idea into a{" "}
          <span
            className="bg-clip-text text-transparent"
            style={{
              backgroundImage:
                "linear-gradient(135deg, var(--accent), var(--leader), var(--architect))",
            }}
          >
            working prototype
          </span>
        </h1>

        {/* Subheadline */}
        <p className="text-lg md:text-xl text-muted max-w-2xl mx-auto mb-10 leading-relaxed">
          Give Neutron a project brief. A small CrewAI team researches, plans,
          and builds an editable web project while you follow the work.
        </p>

        {/* CTA */}
        <Link href="/dashboard">
          <Button size="lg" className="text-base px-8 py-4 rounded-xl shadow-xl shadow-accent/20">
            Try the beta
            <ArrowRight className="ml-2 h-5 w-5" />
          </Button>
        </Link>

        {/* Agent avatars */}
        <div className="mt-16 flex items-center justify-center gap-6 md:gap-10 flex-wrap">
          {AGENTS.map((agent) => (
            <div key={agent.id} className="flex flex-col items-center gap-2">
              <div
                className="relative"
                style={{
                  filter: `drop-shadow(0 0 12px color-mix(in srgb, ${agent.color} 40%, transparent))`,
                }}
              >
                <Avatar name={agent.name} color={agent.color} size="lg" />
              </div>
              <div className="text-center">
                <p className="text-sm font-medium text-foreground">{agent.name}</p>
                <p className="text-xs text-muted">{agent.role}</p>
              </div>
            </div>
          ))}
        </div>

        {/* Subtle trust line */}
        <p className="mt-10 text-xs text-muted/60">
          Bring your own supported model provider key.
        </p>
      </div>
    </section>
  );
}
