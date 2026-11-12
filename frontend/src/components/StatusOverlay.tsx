import type { ReactNode } from "react";

interface StatusOverlayProps {
  kind: "loading" | "error" | "empty";
  title: string;
  children?: ReactNode;
  onRetry?: () => void;
}

const MARKERS: Record<StatusOverlayProps["kind"], string> = {
  loading: "◌",
  error: "!",
  empty: "∅",
};

/** Show a central loading, error or empty-state message with an optional retry. */
export function StatusOverlay({ kind, title, children, onRetry }: StatusOverlayProps) {
  return (
    <div className="pointer-events-none absolute inset-0 flex items-center justify-center p-6">
      <div
        role={kind === "error" ? "alert" : "status"}
        className={`pointer-events-auto max-w-sm rounded-2xl border bg-surface/90 px-5 py-4 text-center text-ink shadow-2xl backdrop-blur-md ${
          kind === "error" ? "border-vigilance-high" : "border-surface-raised"
        }`}
      >
        <div
          aria-hidden="true"
          className={`mx-auto mb-2 flex h-9 w-9 items-center justify-center rounded-full border text-lg ${
            kind === "loading" ? "animate-spin border-trip text-trip" : "border-ink-muted text-ink"
          }`}
        >
          {MARKERS[kind]}
        </div>
        <p className="font-semibold">{title}</p>
        {children && <div className="mt-1 text-sm text-ink-muted">{children}</div>}
        {onRetry && (
          <button
            type="button"
            onClick={onRetry}
            className="mt-3 rounded-full bg-trip px-4 py-1.5 text-sm font-medium text-night hover:bg-selection focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-selection"
          >
            Réessayer
          </button>
        )}
      </div>
    </div>
  );
}
