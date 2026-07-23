TEMPLATES = [
    {
        "id": "saas",
        "name": "SaaS Application",
        "description": "A subscription-based SaaS application with user dashboard, pricing page, and feature showcase.",
        "category": "Business",
        "icon": "rocket",
        "prompt": "Build a modern SaaS landing page with a hero section, feature cards, pricing tiers (Free, Pro, Enterprise), testimonials, and a call-to-action. Include a dashboard page with analytics charts and a sidebar navigation.",
    },
    {
        "id": "ecommerce",
        "name": "E-Commerce Store",
        "description": "An online store with product listings, shopping cart, and checkout flow.",
        "category": "Commerce",
        "icon": "shopping-cart",
        "prompt": "Build an e-commerce website with a product grid, product detail pages, shopping cart, and checkout form. Include filtering/sorting, search functionality, and a responsive design.",
    },
    {
        "id": "portfolio",
        "name": "Portfolio Website",
        "description": "A personal portfolio showcasing projects, skills, and contact information.",
        "category": "Personal",
        "icon": "user",
        "prompt": "Build a modern developer portfolio website with a hero section, about me, project showcase grid with hover effects, skills section with progress bars, and a contact form.",
    },
    {
        "id": "dashboard",
        "name": "Admin Dashboard",
        "description": "A data-rich admin dashboard with charts, tables, and management tools.",
        "category": "Business",
        "icon": "bar-chart",
        "prompt": "Build an admin dashboard with a sidebar navigation, top stats cards, line/bar charts for analytics, a data table with search and pagination, and user management section.",
    },
    {
        "id": "blog",
        "name": "Blog Platform",
        "description": "A clean blog with article listings, categories, and reading experience.",
        "category": "Content",
        "icon": "book-open",
        "prompt": "Build a blog platform with a homepage showing featured and recent articles in a card grid, article detail page with beautiful typography, category sidebar, and newsletter signup.",
    },
    {
        "id": "landing",
        "name": "Landing Page",
        "description": "A high-converting landing page with sections for features, testimonials, and CTA.",
        "category": "Marketing",
        "icon": "zap",
        "prompt": "Build a high-converting landing page with animated hero section, feature grid with icons, how-it-works steps, customer testimonials carousel, FAQ accordion, and a prominent CTA section.",
    },
    {
        "id": "task-manager",
        "name": "Task Manager",
        "description": "A kanban-style project board with columns, task cards, and progress tracking.",
        "category": "Productivity",
        "icon": "layout-grid",
        "prompt": "Build a kanban task manager with a project sidebar, board columns (To Do, In Progress, Done), draggable task cards with due dates and labels, a task detail modal, and a top bar with search and filters.",
    },
    {
        "id": "kanban-board",
        "name": "Kanban Board",
        "description": "A focused kanban board with columns, drag-and-drop cards, WIP limits, labels, and board filters.",
        "category": "Productivity",
        "icon": "columns-3",
        "prompt": (
            "Build a browser-native kanban board app for personal or team work. "
            "Include a top bar with board title, search, label filters, assignee filter, and an Add card button. "
            "Render horizontal scrollable columns: Backlog, Ready, In Progress, Review, and Done. "
            "Each column shows a title, card count, optional WIP limit badge, and an Add card footer control. "
            "Task cards should show title, short description, priority badge, colored labels, assignee avatar initials, "
            "due date, and a comments count. Support drag-and-drop between columns and reordering within a column "
            "(pointer/mouse events are fine; no external libraries). "
            "Clicking a card opens a detail drawer/modal with editable title, description, status/column select, "
            "priority, labels, assignee, due date, checklist, activity notes, and delete/archive actions. "
            "Seed the board with realistic mock data (at least 10–15 cards across columns) so the UI is filled on first load. "
            "Persist board state in localStorage. Keep navigation client-side only (tabs/panels if needed), "
            "use relative assets (./styles.css, ./app.js), and make the layout responsive with stacked columns on small screens."
        ),
    },
    {
        "id": "restaurant",
        "name": "Restaurant Website",
        "description": "A restaurant site with menu, gallery, hours, and online reservations.",
        "category": "Hospitality",
        "icon": "utensils",
        "prompt": "Build a restaurant website with a hero section, categorized menu with prices and dietary tags, chef story section, photo gallery, hours and location with map, and an online reservation form.",
    },
    {
        "id": "event",
        "name": "Event Landing Page",
        "description": "A conference or meetup page with schedule, speakers, and ticket tiers.",
        "category": "Events",
        "icon": "calendar",
        "prompt": "Build an event landing page with a countdown timer, day-by-day agenda timeline, speaker profile cards, venue and travel details, ticket pricing tiers, sponsor logos, and an FAQ accordion.",
    },
    {
        "id": "course",
        "name": "Online Course",
        "description": "A course platform with lessons, progress tracking, and enrollment flow.",
        "category": "Education",
        "icon": "graduation-cap",
        "prompt": "Build an online course platform with a course catalog grid, course detail page with curriculum outline, lesson video player, progress sidebar, instructor bio, student reviews, and enrollment CTA.",
    },
    {
        "id": "kpi-dashboard",
        "name": "KPI Executive Dashboard",
        "description": "A metrics-focused dashboard with KPI cards, trend charts, targets, and drill-down views.",
        "category": "Analytics",
        "icon": "gauge",
        "prompt": "Build a KPI executive dashboard for business leadership. Include a sidebar with sections for Overview, Revenue, Operations, and Goals. The overview page should show KPI stat cards (revenue, conversion rate, churn, NPS) with period-over-period deltas, sparklines, and RAG status indicators against targets. Add line and bar charts for monthly trends, a goal progress section with progress bars, a filter bar for date range and business unit, and a sortable KPI table with actual vs target vs forecast columns. Use a clean, data-dense layout with clear typography and responsive grid cards.",
    },
    {
        "id": "fraud-case-docs",
        "name": "Fraud Case Documentation",
        "description": "Structured fraud investigation docs with case timelines, evidence, and disposition tracking.",
        "category": "Finance",
        "icon": "shield-alert",
        "prompt": "Build a fraud case documentation portal for investigators and compliance teams. Include a case list with filters for status, severity, fraud type, and assignee. Each case detail page should have sections for case summary, alert trigger details, transaction timeline, linked accounts and devices, evidence attachments, investigator notes, risk scoring, regulatory flags, and disposition workflow (open, under review, escalated, closed). Add a dashboard showing open cases, average resolution time, fraud loss prevented, and cases by category. Include printable case report layout and audit trail of status changes.",
    },
    {
        "id": "fraud-ops-center",
        "name": "Fraud Operations Center",
        "description": "Real-time fraud monitoring with alert queues, rule hits, and analyst review workflows.",
        "category": "Finance",
        "icon": "scan-search",
        "prompt": "Build a fraud operations center for real-time monitoring. Include an alert queue table with priority badges, rule name, customer ID, amount, risk score, and analyst actions. Add a live metrics row for alerts in last hour, false positive rate, blocked transactions, and queue SLA. Include charts for alert volume over time and top triggering rules. Build an alert detail drawer with transaction payload, device fingerprint, geo map placeholder, linked historical alerts, and approve/block/escalate buttons. Add a rules panel listing active detection rules with hit counts and a case creation shortcut.",
    },
    {
        "id": "compliance-audit",
        "name": "Compliance & Audit Hub",
        "description": "Audit documentation with control checklists, findings, remediation, and evidence logs.",
        "category": "Finance",
        "icon": "clipboard-check",
        "prompt": "Build a compliance and audit documentation hub. Include an audit program overview with upcoming reviews, control library grouped by domain (KYC, AML, data privacy, access control), and a findings register with severity, owner, due date, and remediation status. Each audit workspace should support checklist items, evidence upload references, reviewer comments, sign-off steps, and exportable audit report preview. Add dashboards for open findings, overdue remediations, and control test pass rates. Design for auditors and risk managers with clear status chips and document-style layouts.",
    },
    {
        "id": "helpdesk",
        "name": "Support Helpdesk",
        "description": "A ticket-based support portal with queues, SLAs, knowledge base, and agent views.",
        "category": "Operations",
        "icon": "life-buoy",
        "prompt": "Build a customer support helpdesk with ticket inbox, status filters (new, in progress, waiting, resolved), priority labels, and SLA countdown badges. Include ticket detail view with conversation thread, internal notes, customer profile sidebar, tags, and assignment controls. Add a knowledge base page with searchable articles and categories, plus an agent dashboard showing ticket volume, first response time, and resolution rate charts. Use a practical operations UI with compact tables and clear action buttons.",
    },
    {
        "id": "inventory",
        "name": "Inventory Management",
        "description": "Warehouse inventory tracking with stock levels, reorder alerts, and movement history.",
        "category": "Operations",
        "icon": "package",
        "prompt": "Build an inventory management system with a product catalog table showing SKU, location, on-hand quantity, reserved quantity, reorder point, and stock status badges. Include low-stock alerts panel, inbound/outbound movement log, warehouse location map grid, and supplier reorder suggestions. Add charts for stock turnover and category distribution, plus a product detail page with movement history timeline and adjustment form. Design for warehouse and ops teams with scan-friendly dense tables.",
    },
    {
        "id": "personal-finance",
        "name": "Personal Finance Tracker",
        "description": "Track expenses, budgets, and net worth with interactive charts and transaction management.",
        "category": "Finance",
        "icon": "dollar-sign",
        "prompt": "Build a personal finance tracker with a dashboard showing net worth, monthly income/expense summary cards, a transactions table with add-new form (amount, category, date, note), category pie chart, spending trends line chart, budget vs actual progress bars per category, and a goals section for savings targets. Support filtering transactions and simple CSV export button.",
    },
    {
        "id": "fitness-tracker",
        "name": "Fitness & Workout Tracker",
        "description": "Log workouts, track progress, view streaks and personal records in a clean fitness app.",
        "category": "Health",
        "icon": "dumbbell",
        "prompt": "Build a fitness tracking app with exercise library grid, workout logger form (select exercises, sets/reps/weight), history calendar or list of past workouts, progress charts (strength over time, bodyweight), streak counter, PR badges, and a weekly summary. Include a simple routine builder.",
    },
    {
        "id": "job-board",
        "name": "Job Board Marketplace",
        "description": "Browse and apply to curated job listings with advanced filters and company profiles.",
        "category": "Career",
        "icon": "briefcase",
        "prompt": "Build a job board website featuring a filterable job listing grid (role, location, salary, remote/hybrid, experience level), job detail modal or page with description, requirements, company info, and apply form (with fake submission success). Include saved jobs and a simple application tracker.",
    },
    {
        "id": "real-estate",
        "name": "Real Estate Explorer",
        "description": "Search properties with filters, detailed listings, photo galleries, and mortgage tools.",
        "category": "Marketplace",
        "icon": "home",
        "prompt": "Build a real estate listings site with hero search, property cards grid (image, price, beds/baths/sqft, address), sidebar or top filters for price range, property type, bedrooms. Clicking a card opens a detail view with photo carousel, description, amenities list, map placeholder, and an interactive mortgage affordability calculator. Include a 'contact agent' form.",
    },
    {
        "id": "ai-playground",
        "name": "AI Prompt Playground",
        "description": "Experiment with prompts, compare model responses, save and organize prompt templates.",
        "category": "AI Tools",
        "icon": "bot",
        "prompt": "Build an AI prompt playground interface with a large prompt textarea, model selector (GPT-4o, Claude, etc mock), parameters (temperature, max tokens sliders), a run button that shows simulated streaming response area, history of past runs in a sidebar, a library of example prompt templates you can load, and side-by-side comparison mode.",
    },
    {
        "id": "music-player",
        "name": "Music Streaming Interface",
        "description": "Modern music player with playlists, now-playing view, and rich audio controls simulation.",
        "category": "Entertainment",
        "icon": "music",
        "prompt": "Build a music streaming web app with left sidebar library/playlists, main content with album grids and search, a prominent now-playing bar at bottom with progress scrubber, play/pause/next, volume, queue, and a visualizer canvas or animated bars. Support clicking songs to 'play', favoriting, and viewing lyrics panel.",
    },
    {
        "id": "travel-planner",
        "name": "Travel Itinerary Planner",
        "description": "Plan trips day-by-day, manage bookings, packing lists, and shareable itineraries.",
        "category": "Travel",
        "icon": "plane",
        "prompt": "Build a travel itinerary planner with trip overview, calendar or day timeline for activities, drag-and-drop reordering of itinerary items, flight/hotel/booking cards, a budget summary, packing checklist with checkoffs, and a destination info panel. Include a map placeholder and export to PDF button.",
    },
    {
        "id": "sales-crm",
        "name": "Sales CRM Pipeline",
        "description": "Manage contacts, deals in pipeline stages, activities, and forecast reports.",
        "category": "Business",
        "icon": "trending-up",
        "prompt": "Build a sales CRM with contacts directory table, deals kanban board (stages: Lead → Qualified → Proposal → Negotiation → Closed), deal detail drawer with notes, activities log and next steps. Include a forecasts dashboard with pipeline value, win rate charts, and recent activity feed.",
    },
    # --- Next.js templates (stack="nextjs") — first step for multi-stack builds ---
    {
        "id": "next-saas-dashboard",
        "name": "Next.js SaaS Dashboard",
        "description": "App Router SaaS shell with sidebar, KPI cards, charts, and settings — generated as a real Next.js project.",
        "category": "Next.js",
        "icon": "layers",
        "stack": "nextjs",
        "prompt": (
            "Build a polished Next.js App Router SaaS dashboard for a fictional product analytics company. "
            "Include: app/layout.tsx with sidebar navigation (Overview, Customers, Reports, Settings), "
            "app/page.tsx overview with 4 KPI cards, a simple bar/line chart (CSS or pure SVG — no chart library required), "
            "and a recent activity table with seeded mock data (8–12 rows). "
            "Add app/customers/page.tsx with a searchable customer table, and app/settings/page.tsx with profile form fields. "
            "Use TypeScript, next/link, client components where needed, cohesive design tokens in app/globals.css, "
            "and a complete package.json so `npm install && npm run dev` works. Seed all lists with realistic demo data on first load."
        ),
    },
    {
        "id": "next-marketing-site",
        "name": "Next.js Marketing Site",
        "description": "Multi-page marketing site with hero, features, pricing, and contact — Next.js App Router + TypeScript.",
        "category": "Next.js",
        "icon": "panel-top",
        "stack": "nextjs",
        "prompt": (
            "Build a modern multi-page marketing website with Next.js App Router and TypeScript. "
            "Pages: Home (hero, logo cloud, feature grid, testimonials, CTA), Features detail section, "
            "Pricing with 3 tiers and a highlighted plan, and Contact with a working client-side form "
            "(validate + success state, no real backend). "
            "Shared layout with sticky header + mobile nav, footer with links. "
            "Seed testimonials and pricing features with realistic copy. "
            "Use next/link, accessible components, responsive layout, and app/globals.css design system. "
            "Include package.json, tsconfig.json, next.config.mjs so the project runs with npm install && npm run dev."
        ),
    },
]


def get_templates() -> list[dict]:
    # Ensure every template exposes a stack for the UI and project creation.
    return [{**t, "stack": t.get("stack") or "static"} for t in TEMPLATES]


def get_template(template_id: str) -> dict | None:
    for t in get_templates():
        if t["id"] == template_id:
            return t
    return None
