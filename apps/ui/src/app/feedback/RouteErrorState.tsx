import type { RouteErrorContent } from "./feedbackTypes";

interface RouteErrorStateProps {
  content: RouteErrorContent;
  onRetry: () => void;
}

export function RouteErrorState({ content, onRetry }: RouteErrorStateProps) {
  return (
    <section className="feedback-panel feedback-panel-error">
      <h2>{content.title}</h2>
      <p>{content.message}</p>
      <button type="button" onClick={onRetry}>
        Retry
      </button>
    </section>
  );
}
