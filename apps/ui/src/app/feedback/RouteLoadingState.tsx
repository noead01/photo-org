interface RouteLoadingStateProps {
  label: string;
}

export function RouteLoadingState({ label }: RouteLoadingStateProps) {
  return (
    <section className="feedback-panel feedback-panel-loading">
      <p role="status">{label}</p>
    </section>
  );
}
