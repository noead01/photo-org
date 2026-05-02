import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useNavigate,
  useLocation
} from "react-router-dom";
import { useState } from "react";
import { AppShell } from "./AppShell";
import {
  PRIMARY_ROUTE_DEFINITIONS,
  resolveNavigationState,
  type PrimaryRouteDefinition
} from "../routes/routeDefinitions";
import { PrimaryRoutePage } from "../pages/PrimaryRoutePage";
import { LibraryRoutePage } from "../pages/LibraryRoutePage";
import { PhotoDetailRoutePage } from "../pages/PhotoDetailRoutePage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PeopleManagementRoutePage } from "../pages/PeopleManagementRoutePage";
import {
  resolveInitialSessionIdentity,
  type SessionIdentity
} from "../session/sessionIdentity";

interface AppShellLayoutProps {
  sessionIdentity: SessionIdentity | null;
  onSignOut: () => void;
}

function AppShellLayout({ sessionIdentity, onSignOut }: AppShellLayoutProps) {
  const location = useLocation();
  const navigate = useNavigate();
  const navigationState = resolveNavigationState(location.pathname);

  function handleSignOut() {
    onSignOut();
    navigate("/library", { replace: true });
  }

  return (
    <AppShell
      navigationState={navigationState}
      sessionIdentity={sessionIdentity}
      onSignOut={handleSignOut}
    >
      <Outlet />
    </AppShell>
  );
}

function routePath(route: PrimaryRouteDefinition): string {
  return route.path.replace(/^\//, "");
}

interface AppRouteTreeProps {
  initialSessionIdentity?: SessionIdentity | null;
}

export function AppRouteTree({ initialSessionIdentity }: AppRouteTreeProps = {}) {
  const [sessionIdentity, setSessionIdentity] = useState<SessionIdentity | null>(() => {
    if (initialSessionIdentity !== undefined) {
      return initialSessionIdentity;
    }

    return resolveInitialSessionIdentity();
  });

  return (
    <Routes>
      <Route
        element={
          <AppShellLayout
            sessionIdentity={sessionIdentity}
            onSignOut={() => setSessionIdentity(null)}
          />
        }
      >
        <Route path="/" element={<Navigate to="/library" replace />} />
        <Route path="library/:photoId" element={<PhotoDetailRoutePage />} />
        {PRIMARY_ROUTE_DEFINITIONS.map((route) => (
          <Route
            key={route.key}
            path={routePath(route)}
            element={
              route.key === "library" ? (
                <LibraryRoutePage />
              ) : route.key === "labeling" ? (
                <PeopleManagementRoutePage />
              ) : (
                <PrimaryRoutePage route={route} />
              )
            }
          />
        ))}
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}

export function AppRouter() {
  return (
    <BrowserRouter
      future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
    >
      <AppRouteTree />
    </BrowserRouter>
  );
}
