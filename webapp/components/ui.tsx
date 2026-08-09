"use client";

import { motion } from "framer-motion";
import { ReactNode } from "react";

/* ----------------------------------------------------------------------------
 * Buttons
 * ------------------------------------------------------------------------- */
type BtnVariant = "primary" | "secondary" | "ghost" | "success" | "danger" | "warn";

export function Button({
  children,
  onClick,
  disabled,
  loading = false,
  variant = "primary",
  size = "md",
  className = "",
  title,
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: BtnVariant;
  size?: "sm" | "md" | "lg";
  className?: string;
  title?: string;
  type?: "button" | "submit";
}) {
  const variants: Record<BtnVariant, string> = {
    primary: "bg-primary text-white hover:bg-primary2 shadow-[0_2px_18px_-6px_rgba(124,106,255,0.7)]",
    secondary: "bg-surface2 text-text border border-edge hover:border-edge2 hover:bg-panel",
    ghost: "text-muted hover:text-text hover:bg-surface2 border border-transparent",
    success: "bg-success/90 text-ink hover:bg-success",
    danger: "bg-danger/90 text-white hover:bg-danger",
    warn: "bg-warn/90 text-ink hover:bg-warn",
  };
  const sizes: Record<string, string> = {
    sm: "h-7 px-2.5 text-xs gap-1.5 rounded-md",
    md: "h-9 px-3.5 text-sm gap-2 rounded-lg",
    lg: "h-10 px-5 text-sm gap-2 rounded-lg",
  };
  return (
    <motion.button
      type={type}
      whileTap={{ scale: disabled || loading ? 1 : 0.97 }}
      onClick={onClick}
      disabled={disabled || loading}
      title={title}
      className={`inline-flex items-center justify-center font-medium transition-colors
        disabled:opacity-40 disabled:cursor-not-allowed select-none
        ${variants[variant]} ${sizes[size]} ${className}`}
    >
      {loading && (
        <span className="h-3.5 w-3.5 rounded-full border-2 border-current/30 border-t-current animate-spin" />
      )}
      {children}
    </motion.button>
  );
}

export function IconButton({
  children,
  onClick,
  disabled,
  active,
  title,
  className = "",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  active?: boolean;
  title?: string;
  className?: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      className={`grid place-items-center h-8 w-8 rounded-lg border text-muted transition-colors
        disabled:opacity-40 disabled:cursor-not-allowed
        ${active
          ? "border-primary/60 bg-primary/15 text-primary2"
          : "border-edge bg-surface2 hover:text-text hover:border-edge2"}
        ${className}`}
    >
      {children}
    </button>
  );
}

/* ----------------------------------------------------------------------------
 * Status indicators
 * ------------------------------------------------------------------------- */
export type Tone = "muted" | "primary" | "success" | "warn" | "danger" | "info";

export function Badge({
  children,
  tone = "muted",
  className = "",
}: {
  children: ReactNode;
  tone?: Tone;
  className?: string;
}) {
  const tones: Record<Tone, string> = {
    muted: "bg-surface2 text-muted",
    primary: "bg-primary/15 text-primary2",
    success: "bg-success/15 text-success",
    warn: "bg-warn/15 text-warn",
    danger: "bg-danger/15 text-danger",
    info: "bg-sky-500/15 text-sky-300",
  };
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-md text-2xs font-medium ${tones[tone]} ${className}`}>
      {children}
    </span>
  );
}

export function StatusDot({ tone = "muted", pulse }: { tone?: Tone; pulse?: boolean }) {
  const c: Record<Tone, string> = {
    muted: "bg-faint",
    primary: "bg-primary",
    success: "bg-success",
    warn: "bg-warn",
    danger: "bg-danger",
    info: "bg-sky-400",
  };
  return (
    <span className={`inline-block h-2 w-2 rounded-full ${c[tone]} ${pulse ? "animate-pulse-soft" : ""}`} />
  );
}

/* ----------------------------------------------------------------------------
 * Panels / containers
 * ------------------------------------------------------------------------- */
export function Card({
  children,
  className = "",
  onClick,
}: {
  children: ReactNode;
  className?: string;
  onClick?: () => void;
}) {
  return (
    <div onClick={onClick} className={`panel ${onClick ? "cursor-pointer" : ""} ${className}`}>
      {children}
    </div>
  );
}

export function SectionTitle({
  index,
  title,
  hint,
}: {
  index: number;
  title: string;
  hint?: string;
}) {
  return (
    <div className="flex items-baseline gap-3 mb-3">
      <span className="text-primary2 mono text-sm">{String(index).padStart(2, "0")}</span>
      <h2 className="text-lg font-semibold">{title}</h2>
      {hint && <span className="text-muted text-xs ml-auto">{hint}</span>}
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * Modal
 * ------------------------------------------------------------------------- */
export function Modal({
  open,
  onClose,
  title,
  children,
  width = "max-w-md",
}: {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
  width?: string;
}) {
  if (!open) return null;
  return (
    <div
      className="fixed inset-0 z-50 grid place-items-center bg-black/65 backdrop-blur-sm px-4 animate-fade-in"
      onClick={onClose}
    >
      <motion.div
        initial={{ opacity: 0, scale: 0.97, y: 8 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        transition={{ duration: 0.15 }}
        className={`panel-2 shadow-pop p-5 w-full ${width}`}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-base font-semibold">{title}</h3>
          <button onClick={onClose} className="text-muted hover:text-text text-sm px-1" aria-label="close">
            ✕
          </button>
        </div>
        {children}
      </motion.div>
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * Tabs (used in the scene inspector)
 * ------------------------------------------------------------------------- */
export function Tabs({
  tabs,
  active,
  onChange,
}: {
  tabs: { id: string; label: string }[];
  active: string;
  onChange: (id: string) => void;
}) {
  return (
    <div className="flex gap-1 border-b border-edge">
      {tabs.map((t) => (
        <button
          key={t.id}
          onClick={() => onChange(t.id)}
          className={`relative px-3 py-2 text-xs font-medium transition-colors
            ${active === t.id ? "text-text" : "text-muted hover:text-text"}`}
        >
          {t.label}
          {active === t.id && (
            <motion.span
              layoutId="tab-underline"
              className="absolute left-0 right-0 -bottom-px h-0.5 bg-primary rounded-full"
            />
          )}
        </button>
      ))}
    </div>
  );
}

/* ----------------------------------------------------------------------------
 * Field helper
 * ------------------------------------------------------------------------- */
export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="block">
      <span className="label block mb-1.5">{label}</span>
      {children}
    </label>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return (
    <kbd className="mono text-2xs px-1.5 py-0.5 rounded bg-surface2 border border-edge text-muted">
      {children}
    </kbd>
  );
}

export function Spinner({ label }: { label?: string }) {
  return (
    <span className="inline-flex items-center gap-2 text-muted text-sm">
      <span className="h-4 w-4 rounded-full border-2 border-primary/30 border-t-primary animate-spin" />
      {label}
    </span>
  );
}
