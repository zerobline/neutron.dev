import { Card, CardContent } from "@/components/ui/card";
import { Users, MessageSquare, Radio, Code2, LayoutGrid, Download } from "lucide-react";

const features = [
  {
    icon: Users,
    title: "A CrewAI team",
    description:
      "Five roles divide the work: lead, research, product, architecture, and engineering.",
  },
  {
    icon: MessageSquare,
    title: "Start with a brief",
    description:
      "Write what you are trying to make, the people it is for, and the constraints that matter.",
  },
  {
    icon: Radio,
    title: "Follow the run",
    description:
      "See each phase, generated file, and request for feedback as the project takes shape.",
  },
  {
    icon: Code2,
    title: "A usable starting point",
    description:
      "Preview the generated interface, inspect the code, and keep iterating on the parts that need work.",
  },
  {
    icon: LayoutGrid,
    title: "Templates when useful",
    description:
      "Use a template for common products, or begin with a blank brief when the idea is more specific.",
  },
  {
    icon: Download,
    title: "Take the files with you",
    description:
      "Download a ZIP of the generated project and run or adapt it in your own environment.",
  },
];

export function Features() {
  return (
    <section className="py-24 bg-surface/30">
      <div className="mx-auto max-w-7xl px-6">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            What Neutron helps with
          </h2>
          <p className="text-lg text-muted max-w-2xl mx-auto">
            Neutron is for getting a first version on the screen: something you
            can review, edit, and take further.
          </p>
        </div>

        {/* Feature grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {features.map((feature) => (
            <Card
              key={feature.title}
              className="hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5 group transition-all duration-200"
            >
              <CardContent>
                <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-accent/10 text-accent group-hover:bg-accent/20 transition-colors duration-200">
                  <feature.icon className="h-6 w-6" />
                </div>
                <h3 className="text-lg font-semibold text-foreground mb-2">
                  {feature.title}
                </h3>
                <p className="text-sm text-muted leading-relaxed">
                  {feature.description}
                </p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>
    </section>
  );
}
