import { NavLink } from "react-router-dom";
import type { ReactNode } from "react";
import {
  PRIMARY_ROUTE_DEFINITIONS,
  type PrimaryRouteDefinition
} from "../routes/routeDefinitions";

interface AppShellProps {
  activeRoute: PrimaryRouteDefinition;
  children: ReactNode;
}

export function AppShell({ activeRoute, children }: AppShellProps) {
  return (
    <div className="app-shell" data-shell-route={activeRoute.key}>
      <header className="shell-header">
        <div>
          <p className="shell-product">Photo Organizer</p>
          <p className="shell-context">{activeRoute.title}</p>
        </div>
      </header>

      <nav aria-label="Primary" className="shell-nav">
        <ul>
          {PRIMARY_ROUTE_DEFINITIONS.map((route) => (
            <li key={route.key}>
              <NavLink
                to={route.path}
                className={({ isActive }) => (isActive ? "active" : undefined)}
                end
              >
                {route.navLabel}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>

      <main className="shell-content">{children}</main>
    </div>
  );
}
