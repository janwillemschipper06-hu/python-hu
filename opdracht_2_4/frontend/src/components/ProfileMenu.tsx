import { useEffect, useRef, useState } from "react";

interface ProfileMenuProps {
  displayName: string | null;
  email: string;
  // Portal roles as the API sees them (Admin / PM / User); empty = none.
  roles: string[];
  photoUrl: string | null;
  onSignOut: () => void;
}

const ROLE_LABELS: Record<string, string> = {
  Admin: "Administrator",
  PM: "Project manager",
  User: "Customer",
};

function initialsOf(name: string): string {
  const parts = name
    .replace(/@.*$/, "")
    .split(/[\s._-]+/)
    .filter(Boolean);
  const letters =
    parts.length > 1
      ? parts[0][0] + parts[parts.length - 1][0]
      : (parts[0] ?? "?").slice(0, 2);
  return letters.toUpperCase();
}

function Avatar({
  name,
  photoUrl,
  size,
}: {
  name: string;
  photoUrl: string | null;
  size: "sm" | "lg";
}): JSX.Element {
  const dimensions = size === "lg" ? "h-12 w-12 text-base" : "h-9 w-9 text-sm";
  if (photoUrl) {
    return (
      <img
        src={photoUrl}
        alt=""
        className={`${dimensions} rounded-full object-cover border border-brand-border`}
      />
    );
  }
  return (
    <span
      aria-hidden="true"
      className={`${dimensions} rounded-full bg-brand-primary text-white font-semibold flex items-center justify-center select-none`}
    >
      {initialsOf(name)}
    </span>
  );
}

export function ProfileMenu({
  displayName,
  email,
  roles,
  photoUrl,
  onSignOut,
}: ProfileMenuProps): JSX.Element {
  const [open, setOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const name = displayName || email;
  const roleLabels = roles.length
    ? roles.map((role) => ROLE_LABELS[role] ?? role)
    : [];

  // Close on outside click or Escape.
  useEffect(() => {
    if (!open) return;
    function onPointerDown(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") setOpen(false);
    }
    document.addEventListener("mousedown", onPointerDown);
    document.addEventListener("keydown", onKeyDown);
    return () => {
      document.removeEventListener("mousedown", onPointerDown);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  return (
    <div className="relative" ref={containerRef}>
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-label="Account menu"
        className="flex items-center gap-2 rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-brand-primary"
      >
        <span className="hidden sm:block text-right leading-tight">
          <span className="block text-sm font-medium text-brand-dark">
            {name}
          </span>
          {roleLabels.length > 0 && (
            <span className="block text-xs text-brand-muted">
              {roleLabels.join(", ")}
            </span>
          )}
        </span>
        <Avatar name={name} photoUrl={photoUrl} size="sm" />
      </button>

      {open && (
        <div
          role="menu"
          className="absolute right-0 mt-2 w-72 bg-white border border-brand-border rounded shadow-lg z-20"
        >
          <div className="p-4 flex items-center gap-3 border-b border-brand-border">
            <Avatar name={name} photoUrl={photoUrl} size="lg" />
            <div className="min-w-0">
              <p className="text-sm font-semibold text-brand-dark truncate">
                {name}
              </p>
              <p className="text-xs text-brand-muted truncate">{email}</p>
              {roleLabels.length > 0 && (
                <div className="mt-1.5 flex flex-wrap gap-1">
                  {roleLabels.map((label) => (
                    <span
                      key={label}
                      className="text-xs font-medium px-2 py-0.5 rounded border text-brand-primary border-brand-primary bg-brand-surface"
                    >
                      {label}
                    </span>
                  ))}
                </div>
              )}
            </div>
          </div>
          <button
            type="button"
            role="menuitem"
            onClick={onSignOut}
            className="w-full text-left px-4 py-3 text-sm font-medium text-brand-primary hover:bg-brand-surface transition-colors"
          >
            Sign out
          </button>
        </div>
      )}
    </div>
  );
}
