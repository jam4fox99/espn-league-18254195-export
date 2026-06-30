import { AlertTriangle, CheckCircle2, Info, XCircle } from "lucide-react";
import type { ReactNode } from "react";

type StatusTone = "success" | "warning" | "error" | "info";

type StatusPillProps = {
  readonly tone: StatusTone;
  readonly children: ReactNode;
};

export function StatusPill({ tone, children }: StatusPillProps) {
  const Icon = iconByTone[tone];
  return (
    <span className={`status-pill ${tone}`}>
      <Icon aria-hidden="true" size={14} />
      {children}
    </span>
  );
}

const iconByTone = {
  success: CheckCircle2,
  warning: AlertTriangle,
  error: XCircle,
  info: Info
} satisfies Record<StatusTone, typeof Info>;
