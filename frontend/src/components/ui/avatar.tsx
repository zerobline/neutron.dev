import { cn } from "@/lib/utils";

interface AvatarProps {
  name: string;
  color: string;
  size?: "sm" | "md" | "lg";
  className?: string;
  status?: "idle" | "thinking" | "working" | "complete" | "error";
}

export function Avatar({ name, color, size = "md", className, status }: AvatarProps) {
  const initial = name.charAt(0).toUpperCase();
  return (
    <div
      className={cn(
        "relative inline-flex items-center justify-center rounded-full font-semibold",
        {
          "w-8 h-8 text-xs": size === "sm",
          "w-10 h-10 text-sm": size === "md",
          "w-14 h-14 text-lg": size === "lg",
        },
        className
      )}
      style={{ backgroundColor: `color-mix(in srgb, ${color} 20%, transparent)`, color }}
    >
      {initial}
      {status && status !== "idle" && (
        <span
          className={cn(
            "absolute -bottom-0.5 -right-0.5 w-3 h-3 rounded-full border-2 border-background",
            {
              "bg-yellow-400 animate-pulse-dot": status === "thinking",
              "bg-green-400 animate-pulse-dot": status === "working",
              "bg-green-500": status === "complete",
              "bg-red-500": status === "error",
            }
          )}
        />
      )}
    </div>
  );
}
