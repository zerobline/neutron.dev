"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Header } from "@/components/layout/header";
import { Footer } from "@/components/layout/footer";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { Template } from "@/types";
import { Rocket, ShoppingCart, User, BarChart3, BookOpen, Zap, LayoutGrid, Columns3, Utensils, Calendar, GraduationCap, Gauge, ShieldAlert, ScanSearch, ClipboardCheck, LifeBuoy, Package, ArrowRight, DollarSign, Dumbbell, Briefcase, Home, Bot, Music, Plane, TrendingUp, Layers, PanelTop, type LucideIcon } from "lucide-react";

const iconMap: Record<string, LucideIcon> = {
  "rocket": Rocket,
  "shopping-cart": ShoppingCart,
  "user": User,
  "bar-chart": BarChart3,
  "book-open": BookOpen,
  "zap": Zap,
  "layout-grid": LayoutGrid,
  "columns-3": Columns3,
  "utensils": Utensils,
  "calendar": Calendar,
  "graduation-cap": GraduationCap,
  "gauge": Gauge,
  "shield-alert": ShieldAlert,
  "scan-search": ScanSearch,
  "clipboard-check": ClipboardCheck,
  "life-buoy": LifeBuoy,
  "package": Package,
  "dollar-sign": DollarSign,
  "dumbbell": Dumbbell,
  "briefcase": Briefcase,
  "home": Home,
  "bot": Bot,
  "music": Music,
  "plane": Plane,
  "trending-up": TrendingUp,
  "layers": Layers,
  "panel-top": PanelTop,
};

export default function TemplatesPage() {
  const [templates, setTemplates] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState(false);

  useEffect(() => {
    api.listTemplates()
      .then((t) => setTemplates(t as Template[]))
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false));
  }, []);

  return (
    <>
      <Header />
      <main className="flex-1">
        <div className="mx-auto max-w-7xl px-6 py-10">
          <div className="text-center mb-12">
            <h1 className="text-3xl font-bold text-foreground mb-3">Template Gallery</h1>
            <p className="text-lg text-muted max-w-2xl mx-auto">
              Choose a template to get started quickly. Each template comes with a pre-written prompt optimized for great results.
            </p>
          </div>

          {loading ? (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {Array.from({ length: 6 }).map((_, i) => (
                <Skeleton key={i} className="h-64 rounded-xl" />
              ))}
            </div>
          ) : loadError ? (
            <p className="text-center text-sm text-red-400">Unable to load templates. Please try again later.</p>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {templates.map((t) => {
                const Icon = iconMap[t.icon] ?? Rocket;
                return (
                  <Card key={t.id} className="hover:border-accent/30 hover:shadow-lg hover:shadow-accent/5 group flex flex-col">
                    <CardContent className="flex flex-col flex-1">
                      <div className="flex items-start justify-between mb-4">
                        <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-accent/10 text-accent group-hover:bg-accent/20 transition-colors">
                          <Icon className="h-7 w-7" />
                        </div>
                        <div className="flex flex-col items-end gap-1">
                          <Badge variant="info">{t.category}</Badge>
                          {t.stack === "nextjs" ? (
                            <span className="rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-semibold text-sky-300">
                              Next.js
                            </span>
                          ) : null}
                        </div>
                      </div>
                      <h3 className="text-lg font-semibold text-foreground mb-2">{t.name}</h3>
                      <p className="text-sm text-muted leading-relaxed mb-6 flex-1">{t.description}</p>
                      <Link href={`/dashboard?template=${t.id}`}>
                        <Button variant="secondary" className="w-full group-hover:border-accent/30">
                          Use Template
                          <ArrowRight className="ml-2 h-4 w-4" />
                        </Button>
                      </Link>
                    </CardContent>
                  </Card>
                );
              })}
            </div>
          )}
        </div>
      </main>
      <Footer />
    </>
  );
}
