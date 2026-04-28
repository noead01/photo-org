import { PRIMARY_ROUTE_DEFINITIONS } from "./routeDefinitions";

describe("Shell handoff expectations", () => {
  it("defines loading and error behavior for each primary route", () => {
    for (const route of PRIMARY_ROUTE_DEFINITIONS) {
      expect(route.handoff.loading).not.toHaveLength(0);
      expect(route.handoff.error).not.toHaveLength(0);
      expect(route.handoff.transition).not.toHaveLength(0);
    }
  });
});
