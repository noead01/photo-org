import type { ReactNode } from "react";
import { RouteErrorState } from "./RouteErrorState";
import { RouteLoadingState } from "./RouteLoadingState";
import { ToastStack } from "./ToastStack";
import type { FeedbackViewState, NotificationEntry, RouteErrorContent } from "./feedbackTypes";

type FeedbackSurfaceProps = {
  viewState: FeedbackViewState;
  loadingLabel: string;
  errorContent: RouteErrorContent;
  onRetry: () => void;
  notifications: NotificationEntry[];
  onDismissNotification: (id: string) => void;
  children?: ReactNode;
};

export function FeedbackSurface({
  viewState,
  loadingLabel,
  errorContent,
  onRetry,
  notifications,
  onDismissNotification,
  children
}: FeedbackSurfaceProps) {
  let content: ReactNode = children ?? null;

  if (viewState === "loading") {
    content = <RouteLoadingState label={loadingLabel} />;
  } else if (viewState === "error") {
    content = <RouteErrorState content={errorContent} onRetry={onRetry} />;
  }

  return (
    <>
      {content}
      <ToastStack notifications={notifications} onDismiss={onDismissNotification} />
    </>
  );
}
