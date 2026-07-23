import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Features } from "@/components/landing/features";
import { Hero } from "@/components/landing/hero";
import { HowItWorks } from "@/components/landing/how-it-works";
import { TemplateShowcase } from "@/components/landing/template-showcase";
import { AGENTS } from "@/types";

describe("landing components", () => {
  it("renders hero with agents and CTA", () => {
    render(<Hero />);
    expect(screen.getByRole("heading", { name: /Turn an idea into a working prototype/ })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Try the beta/ })).toHaveAttribute("href", "/dashboard");
    AGENTS.forEach((agent) => {
      expect(screen.getByText(agent.name)).toBeInTheDocument();
      expect(screen.getByText(agent.role)).toBeInTheDocument();
    });
  });

  it("renders all feature cards", () => {
    render(<Features />);
    ["A CrewAI team", "Start with a brief", "Follow the run", "A usable starting point", "Templates when useful", "Take the files with you"].forEach((title) => {
      expect(screen.getByText(title)).toBeInTheDocument();
    });
  });

  it("renders ordered steps", () => {
    render(<HowItWorks />);
    ["01", "02", "03", "Write a brief", "Review the work", "Keep building"].forEach((text) => {
      expect(screen.getByText(text)).toBeInTheDocument();
    });
  });

  it("renders template showcase links", () => {
    render(<TemplateShowcase />);
    expect(screen.getByRole("link", { name: /SaaS Application/ })).toHaveAttribute("href", "/dashboard?template=saas");
    expect(screen.getByRole("link", { name: /E-Commerce Store/ })).toHaveAttribute("href", "/dashboard?template=ecommerce");
    expect(screen.getByRole("link", { name: /Describe your own project/ })).toHaveAttribute("href", "/dashboard");
  });
});
