import { Link } from "react-router-dom";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";
import {
  PRIMARY_ROUTE_DEFINITIONS,
  type NavigationState
} from "../routes/routeDefinitions";
import type { SessionIdentity } from "../session/sessionIdentity";

interface AppShellProps {
  navigationState: NavigationState;
  sessionIdentity: SessionIdentity | null;
  onSignOut: () => void;
  children: ReactNode;
}

interface AccountMenuProps {
  sessionIdentity: SessionIdentity | null;
  onSignOut: () => void;
}

function AccountMenu({ sessionIdentity, onSignOut }: AccountMenuProps) {
  const [isOpen, setIsOpen] = useState(false);
  const containerRef = useRef<HTMLDivElement | null>(null);
  const menuId = useId();

  useEffect(() => {
    if (!isOpen) {
      return;
    }

    function handleOutsideClick(event: MouseEvent) {
      if (!containerRef.current?.contains(event.target as Node)) {
        setIsOpen(false);
      }
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setIsOpen(false);
      }
    }

    document.addEventListener("mousedown", handleOutsideClick);
    document.addEventListener("keydown", handleEscape);

    return () => {
      document.removeEventListener("mousedown", handleOutsideClick);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [isOpen]);

  if (!sessionIdentity) {
    return (
      <div className="shell-account" data-session-state="missing">
        <p className="shell-account-label">Session</p>
        <p className="shell-account-name">Session unavailable</p>
        <button
          type="button"
          className="shell-account-trigger"
          disabled
          aria-label="Account actions unavailable"
        >
          Account
        </button>
      </div>
    );
  }

  return (
    <div className="shell-account" data-session-state="available" ref={containerRef}>
      <p className="shell-account-label">Signed in</p>
      <p className="shell-account-name">{sessionIdentity.displayName}</p>
      <p className="shell-account-email">{sessionIdentity.email}</p>
      <button
        type="button"
        className="shell-account-trigger"
        aria-haspopup="true"
        aria-expanded={isOpen}
        aria-controls={menuId}
        aria-label="Account actions"
        onClick={() => setIsOpen((open) => !open)}
      >
        Account
      </button>
      {isOpen ? (
        <ul className="shell-account-menu" id={menuId} aria-label="Account actions list">
          <li>
            <button type="button" className="shell-account-action" disabled>
              Account settings (coming soon)
            </button>
          </li>
          <li>
            <button
              type="button"
              className="shell-account-action"
              onClick={() => {
                onSignOut();
                setIsOpen(false);
              }}
            >
              Sign out
            </button>
          </li>
        </ul>
      ) : null}
    </div>
  );
}

export function AppShell({
  navigationState,
  sessionIdentity,
  onSignOut,
  children
}: AppShellProps) {
  return (
    <div className="app-shell" data-shell-route={navigationState.activeRoute.key}>
      <header className="shell-header">
        <div className="shell-title">
          <p className="shell-product">Photo Organizer</p>
          <p className="shell-context">{navigationState.pageContext}</p>
        </div>
        <AccountMenu sessionIdentity={sessionIdentity} onSignOut={onSignOut} />
      </header>

      <nav aria-label="Primary" className="shell-nav">
        <ul>
          {PRIMARY_ROUTE_DEFINITIONS.map((route) => {
            const isActive = route.key === navigationState.activeRoute.key;

            return (
              <li key={route.key}>
                <Link
                  to={route.path}
                  className={isActive ? "active" : undefined}
                  aria-current={isActive ? "page" : undefined}
                >
                  {route.navLabel}
                </Link>
              </li>
            );
          })}
        </ul>
      </nav>

      <main className="shell-content">{children}</main>
    </div>
  );
}
