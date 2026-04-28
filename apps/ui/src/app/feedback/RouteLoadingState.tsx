type RouteLoadingStateProps = {
  label: string;
};

export function RouteLoadingState({ label }: RouteLoadingStateProps) {
  return <p role="status">{label}</p>;
}
