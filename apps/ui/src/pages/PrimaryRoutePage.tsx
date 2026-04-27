import type { PrimaryRouteDefinition } from "../routes/routeDefinitions";

interface PrimaryRoutePageProps {
  route: PrimaryRouteDefinition;
}

export function PrimaryRoutePage({ route }: PrimaryRoutePageProps) {
  return (
    <section aria-labelledby="page-title" className="page">
      <h1 id="page-title">{route.title}</h1>
      <p>{route.description}</p>
    </section>
  );
}
