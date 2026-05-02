import { useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { FeedbackSurface } from "../app/feedback/FeedbackSurface";
import type {
  FeedbackViewState,
  NotificationEntry,
  RouteErrorContent
} from "../app/feedback/feedbackTypes";
import type { PrimaryRouteDefinition } from "../routes/routeDefinitions";

interface PrimaryRoutePageProps {
  route: PrimaryRouteDefinition;
}

export const PRIMARY_ROUTE_LOADING_LABELS: Record<PrimaryRouteDefinition["key"], string> = {
  library: "Loading library workflow.",
  labeling: "Loading labeling workflow.",
  suggestions: "Loading suggestions workflow.",
  operations: "Loading operations workflow."
};

function resolveDemoViewState(search: string): FeedbackViewState {
  const demoState = new URLSearchParams(search).get("demoState");

  if (demoState === "loading" || demoState === "error" || demoState === "ready") {
    return demoState;
  }

  return "ready";
}

export function PrimaryRoutePage({ route }: PrimaryRoutePageProps) {
  const location = useLocation();
  const demoViewState = resolveDemoViewState(location.search);
  const [viewState, setViewState] = useState<FeedbackViewState>(() =>
    demoViewState
  );
  const [notifications, setNotifications] = useState<NotificationEntry[]>([]);

  useEffect(() => {
    setViewState(demoViewState);
    setNotifications([]);
  }, [demoViewState, route.key]);

  const error: RouteErrorContent = {
    title: `Could not load ${route.title}`,
    message: "Please retry to continue."
  };

  function handleRetry() {
    setViewState("ready");
    setNotifications([
      {
        id: `${route.key}-ready`,
        tone: "success",
        message: `${route.title} is ready.`
      }
    ]);
  }

  function handleDismissNotification(id: string) {
    setNotifications((current) => current.filter((notification) => notification.id !== id));
  }

  return (
    <FeedbackSurface
      viewState={viewState}
      loadingLabel={PRIMARY_ROUTE_LOADING_LABELS[route.key]}
      error={error}
      onRetry={handleRetry}
      notifications={notifications}
      onDismissNotification={handleDismissNotification}
    >
      <section aria-labelledby="page-title" className="page">
        <h1 id="page-title">{route.title}</h1>
        <p>{route.description}</p>
      </section>
    </FeedbackSurface>
  );
}
