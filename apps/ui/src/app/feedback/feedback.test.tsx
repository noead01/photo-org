import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouteErrorState } from "./RouteErrorState";
import { RouteLoadingState } from "./RouteLoadingState";
import { ToastStack } from "./ToastStack";
import type { NotificationEntry } from "./feedbackTypes";

describe("feedback primitives", () => {
  it("renders a route loading status label", () => {
    render(<RouteLoadingState label="Loading photos" />);

    expect(screen.getByRole("status")).toHaveTextContent("Loading photos");
  });

  it("renders route error content and retries once", async () => {
    const user = userEvent.setup();
    const onRetry = vi.fn();

    render(
      <RouteErrorState
        content={{
          title: "Could not load photos",
          message: "Please try again."
        }}
        onRetry={onRetry}
      />
    );

    expect(screen.getByRole("heading", { name: "Could not load photos", level: 2 })).toBeInTheDocument();
    expect(screen.getByText("Please try again.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Retry" }));

    expect(onRetry).toHaveBeenCalledTimes(1);
  });

  it("auto-dismisses notifications after the default timeout", () => {
    vi.useFakeTimers();

    const onDismiss = vi.fn();
    const notifications: NotificationEntry[] = [
      {
        id: "upload-success",
        tone: "success",
        message: "Upload finished."
      }
    ];

    render(<ToastStack notifications={notifications} onDismiss={onDismiss} />);

    vi.advanceTimersByTime(3999);
    expect(onDismiss).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledWith("upload-success");

    vi.useRealTimers();
  });

  it("allows manual notification dismissal", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    const notifications: NotificationEntry[] = [
      {
        id: "quota-warning",
        tone: "warning",
        message: "Storage is almost full."
      }
    ];

    render(<ToastStack notifications={notifications} onDismiss={onDismiss} />);

    await user.click(screen.getByRole("button", { name: "Dismiss notification" }));

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledWith("quota-warning");
  });
});
