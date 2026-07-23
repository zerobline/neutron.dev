import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import { Analytics } from "@vercel/analytics/next";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "Neutron | CrewAI project builder",
  description: "A public-beta CrewAI workspace for turning product briefs into editable web project prototypes.",
  metadataBase: new URL(process.env.NEXT_PUBLIC_APP_URL || "http://localhost:3000"),
  openGraph: {
    title: "Neutron | CrewAI project builder",
    description: "A public-beta CrewAI workspace for turning product briefs into editable web project prototypes.",
    siteName: "Neutron",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Neutron | CrewAI project builder",
    description: "A public-beta CrewAI workspace for turning product briefs into editable web project prototypes.",
  },
  other: {
    "theme-color": "#0a0a0a",
  },
};

const themeInitScript = `(function(){try{var t=localStorage.getItem("neutron-theme");if(t==="light"){document.documentElement.classList.add("light");}}catch(e){}})();`;

export function isVercelAnalyticsEnabled() {
  return process.env.NEXT_PUBLIC_VERCEL_ANALYTICS === "true";
}

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
      suppressHydrationWarning
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: themeInitScript }} />
      </head>
      <body className="min-h-full flex flex-col" suppressHydrationWarning>
        {children}
        {isVercelAnalyticsEnabled() ? <Analytics /> : null}
      </body>
    </html>
  );
}
