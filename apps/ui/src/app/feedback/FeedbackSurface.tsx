import type { ReactNode } from "react";
import { RouteErrorState } from "./RouteErrorState";
import { RouteLoadingState } from "./RouteLoadingState";
import { ToastStack } from "./ToastStack";
import type { FeedbackViewState, NotificationEntry, RouteErrorContent } from "./feedbackTypes";

interface FeedbackSurfaceProps {
  viewState: FeedbackViewState;
  loadingLabel: string;
  error: RouteErrorContent | null;
  onRetry: () => void;
  notifications: NotificationEntry[];
  onDismissNotification: (id: string) => void;
  children?: ReactNode;
}

export function FeedbackSurface({
  viewState,
  loadingLabel,
  error,
  onRetry,
  notifications,
  onDismissNotification,
  children
}: FeedbackSurfaceProps) {
  let content: ReactNode = children ?? null;

  if (viewState === "loading") {
    content = <RouteLoadingState label={loadingLabel} />;
  } else if (viewState === "error" && error !== null) {
    content = <RouteErrorState content={error} onRetry={onRetry} />;
  }

  return (
    <>
      {content}
      <ToastStack notifications={notifications} onDismiss={onDismissNotification} />
    </>
  );
}
