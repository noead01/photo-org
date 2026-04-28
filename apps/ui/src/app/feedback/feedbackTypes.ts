export type FeedbackViewState = "loading" | "error" | "ready";

export type RouteErrorContent = {
  title: string;
  message: string;
};

export type NotificationEntry = {
  id: string;
  tone: "success" | "warning";
  message: string;
  timeoutMs?: number;
};
