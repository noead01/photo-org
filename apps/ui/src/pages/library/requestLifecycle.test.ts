import { getRequestErrorMessage } from "./requestLifecycle";

describe("request lifecycle primitives", () => {
  it("uses caught error message when available", () => {
    expect(getRequestErrorMessage(new Error("Request failed (503)"), "fallback")).toBe(
      "Request failed (503)"
    );
  });

  it("falls back when caught value is not an Error", () => {
    expect(getRequestErrorMessage("failure", "fallback")).toBe("fallback");
  });

  it("falls back when error message is empty", () => {
    expect(getRequestErrorMessage(new Error("   "), "fallback")).toBe("fallback");
  });
});
