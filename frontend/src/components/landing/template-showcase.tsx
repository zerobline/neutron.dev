import Link from "next/link";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Rocket, ShoppingCart, User, BarChart3, BookOpen, Zap, LayoutGrid, Columns3, Utensils, Calendar, GraduationCap, Gauge, ShieldAlert, ScanSearch, ClipboardCheck, LifeBuoy, Package, DollarSign, Dumbbell, Briefcase, Home, Bot, Music, Plane, TrendingUp, Layers, PanelTop } from "lucide-react";
import type { LucideIcon } from "lucide-react";

interface Template {
  id: string;
  name: string;
  category: string;
  icon: LucideIcon;
}

const templates: Template[] = [
  { id: "saas", name: "SaaS Application", category: "Business", icon: Rocket },
  { id: "ecommerce", name: "E-Commerce Store", category: "Commerce", icon: ShoppingCart },
  { id: "portfolio", name: "Portfolio Website", category: "Personal", icon: User },
  { id: "dashboard", name: "Admin Dashboard", category: "Business", icon: BarChart3 },
  { id: "blog", name: "Blog Platform", category: "Content", icon: BookOpen },
  { id: "landing", name: "Landing Page", category: "Marketing", icon: Zap },
  { id: "task-manager", name: "Task Manager", category: "Productivity", icon: LayoutGrid },
  { id: "kanban-board", name: "Kanban Board", category: "Productivity", icon: Columns3 },
  { id: "next-saas-dashboard", name: "Next.js SaaS Dashboard", category: "Next.js", icon: Layers },
  { id: "next-marketing-site", name: "Next.js Marketing Site", category: "Next.js", icon: PanelTop },
  { id: "restaurant", name: "Restaurant Website", category: "Hospitality", icon: Utensils },
  { id: "event", name: "Event Landing Page", category: "Events", icon: Calendar },
  { id: "course", name: "Online Course", category: "Education", icon: GraduationCap },
  { id: "kpi-dashboard", name: "KPI Executive Dashboard", category: "Analytics", icon: Gauge },
  { id: "fraud-case-docs", name: "Fraud Case Documentation", category: "Finance", icon: ShieldAlert },
  { id: "fraud-ops-center", name: "Fraud Operations Center", category: "Finance", icon: ScanSearch },
  { id: "compliance-audit", name: "Compliance & Audit Hub", category: "Finance", icon: ClipboardCheck },
  { id: "helpdesk", name: "Support Helpdesk", category: "Operations", icon: LifeBuoy },
  { id: "inventory", name: "Inventory Management", category: "Operations", icon: Package },
  { id: "personal-finance", name: "Personal Finance Tracker", category: "Finance", icon: DollarSign },
  { id: "fitness-tracker", name: "Fitness & Workout Tracker", category: "Health", icon: Dumbbell },
  { id: "job-board", name: "Job Board Marketplace", category: "Career", icon: Briefcase },
  { id: "real-estate", name: "Real Estate Explorer", category: "Marketplace", icon: Home },
  { id: "ai-playground", name: "AI Prompt Playground", category: "AI Tools", icon: Bot },
  { id: "music-player", name: "Music Streaming Interface", category: "Entertainment", icon: Music },
  { id: "travel-planner", name: "Travel Itinerary Planner", category: "Travel", icon: Plane },
  { id: "sales-crm", name: "Sales CRM Pipeline", category: "Business", icon: TrendingUp },
];

export function TemplateShowcase() {
  return (
    <section className="py-24 bg-surface/30">
      <div className="mx-auto max-w-7xl px-6">
        {/* Section header */}
        <div className="text-center mb-16">
          <h2 className="text-3xl md:text-4xl font-bold text-foreground mb-4">
            Start from a Template
          </h2>
          <p className="text-lg text-muted max-w-2xl mx-auto">
            Choose a template to get a head start, or describe your own project
            from scratch.
          </p>
        </div>

        {/* Template grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-6">
          {templates.map((t) => (
            <Link key={t.id} href={`/dashboard?template=${t.id}`}>
              <Card className="h-full hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5 cursor-pointer group transition-all duration-200">
                <CardContent className="flex flex-col items-center text-center pt-2">
                  <div className="mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-accent/10 text-accent group-hover:bg-accent/20 transition-colors duration-200">
                    <t.icon className="h-8 w-8" />
                  </div>
                  <h3 className="text-lg font-semibold text-foreground mb-3">
                    {t.name}
                  </h3>
                  <Badge variant="info">{t.category}</Badge>
                </CardContent>
              </Card>
            </Link>
          ))}
        </div>

        {/* Custom project nudge */}
        <p className="text-center text-sm text-muted mt-10">
          Don&apos;t see what you need?{" "}
          <Link
            href="/dashboard"
            className="text-accent hover:underline font-medium"
          >
            Describe your own project
          </Link>
        </p>
      </div>
    </section>
  );
}
