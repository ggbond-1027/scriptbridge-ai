import type { ReactNode } from "react";

type BadgeTone = "neutral" | "accent" | "success" | "warning" | "error";

const tones: Record<BadgeTone, string> = {
  neutral: "border-[var(--border)] bg-[var(--panel)] text-[var(--muted)]",
  accent: "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--text)]",
  success: "border-[color:var(--success)] bg-[oklch(94%_0.035_150)] text-[var(--text)]",
  warning: "border-[color:var(--warning)] bg-[oklch(94%_0.04_75)] text-[var(--text)]",
  error: "border-[color:var(--error)] bg-[oklch(94%_0.035_28)] text-[var(--text)]",
};

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: BadgeTone }) {
  return (
    <span className={`inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-semibold ${tones[tone]}`}>
      {children}
    </span>
  );
}
