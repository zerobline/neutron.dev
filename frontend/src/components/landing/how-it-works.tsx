import { MessageSquareText, BotMessageSquare, Rocket } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Step {
  number: string;
  icon: LucideIcon;
  title: string;
  description: string;
  color: string;
}

const steps: Step[] = [
  {
    number: "01",
    icon: MessageSquareText,
    title: "Write a brief",
    description:
      "Describe the product, the people using it, and the constraints you already know about.",
    color: "var(--leader)",
  },
  {
    number: "02",
    icon: BotMessageSquare,
    title: "Review the work",
    description:
      "The team works through the brief in stages. You can approve a direction or ask for a revision when it matters.",
    color: "var(--accent)",
  },
  {
    number: "03",
    icon: Rocket,
    title: "Keep building",
    description:
      "Preview the result, inspect the files, and download the project when you are ready to continue locally.",
    color: "var(--architect)",
  },
];

export function HowItWorks() {
  return (
    <section className="py-24">
      <div className="mx-auto max-w-5xl px-6">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            How it works
          </h2>
          <p className="text-lg text-muted">
            A short loop for turning an early idea into something concrete.
          </p>
        </div>

        {/* Steps */}
        <div className="relative space-y-12">
          {/* Vertical connector line */}
          <div className="absolute left-7 top-14 bottom-14 w-px bg-border hidden md:block" />

          {steps.map((step) => (
            <div key={step.number} className="flex items-start gap-6 md:gap-8">
              {/* Step number badge */}
              <div
                className="relative flex-shrink-0 flex h-14 w-14 items-center justify-center rounded-2xl text-lg font-bold z-10"
                style={{
                  backgroundColor: `color-mix(in srgb, ${step.color} 15%, transparent)`,
                  color: step.color,
                }}
              >
                {step.number}
              </div>

              {/* Step content */}
              <div className="pt-1">
                <h3 className="text-xl font-semibold text-foreground mb-2 flex items-center gap-3">
                  <step.icon className="h-5 w-5 text-muted flex-shrink-0" />
                  {step.title}
                </h3>
                <p className="text-muted leading-relaxed max-w-lg">
                  {step.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
