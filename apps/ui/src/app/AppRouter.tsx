import {
  BrowserRouter,
  Navigate,
  Outlet,
  Route,
  Routes,
  useNavigate,
  useLocation
} from "react-router-dom";
import { startTransition, useEffect, useState } from "react";
import { NuqsAdapter } from "nuqs/adapters/react-router/v6";
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
import { SuggestionsRoutePage } from "../pages/SuggestionsRoutePage";
import { AlbumsRoutePage } from "../pages/AlbumsRoutePage";
import { OperationsRoutePage } from "../pages/OperationsRoutePage";
import {
  fetchCurrentSessionIdentity,
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
    if (typeof window !== "undefined" && window.__PHOTO_ORG_SESSION__ === undefined) {
      return null;
    }
    return resolveInitialSessionIdentity();
  });

  useEffect(() => {
    if (initialSessionIdentity !== undefined) {
      return;
    }

    const controller = new AbortController();

    fetchCurrentSessionIdentity(controller.signal)
      .then((resolvedIdentity) => {
        startTransition(() => {
          setSessionIdentity(resolvedIdentity);
        });
      })
      .catch(() => {
        if (controller.signal.aborted) {
          return;
        }
      });

    return () => {
      controller.abort();
    };
  }, [initialSessionIdentity]);

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
              ) : route.key === "albums" ? (
                <AlbumsRoutePage />
              ) : route.key === "labeling" ? (
                <PeopleManagementRoutePage />
              ) : route.key === "suggestions" ? (
                <SuggestionsRoutePage />
              ) : route.key === "operations" ? (
                <OperationsRoutePage sessionIdentity={sessionIdentity} />
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
    <NuqsAdapter>
      <BrowserRouter
        future={{ v7_startTransition: true, v7_relativeSplatPath: true }}
      >
        <AppRouteTree />
      </BrowserRouter>
    </NuqsAdapter>
  );
}
