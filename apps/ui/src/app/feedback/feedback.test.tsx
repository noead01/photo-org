import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { FeedbackSurface } from "./FeedbackSurface";
import { RouteErrorState } from "./RouteErrorState";
import { RouteLoadingState } from "./RouteLoadingState";
import { ToastStack } from "./ToastStack";
import type { NotificationEntry } from "./feedbackTypes";

describe("feedback primitives", () => {
  afterEach(() => {
    vi.useRealTimers();
  });

  it("renders a route loading status label", () => {
    render(<RouteLoadingState label="Loading photos" />);

    const loadingStatus = screen.getByRole("status");
    const loadingPanel = loadingStatus.closest(".feedback-panel-loading");
    expect(loadingStatus).toHaveTextContent("Loading photos");
    expect(loadingPanel).toBeInTheDocument();
    expect(loadingPanel).toHaveClass("feedback-panel");
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

    const errorHeading = screen.getByRole("heading", { name: "Could not load photos", level: 2 });
    const errorPanel = errorHeading.closest(".feedback-panel-error");
    expect(errorPanel).toBeInTheDocument();
    expect(errorPanel).toHaveClass("feedback-panel");
    expect(errorPanel?.querySelector("h2")).toBe(errorHeading);
    expect(errorHeading).toBeInTheDocument();
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
    expect(screen.getByText("Upload finished.").closest(".toast-success")).toBeInTheDocument();
    expect(screen.getByText("Upload finished.").closest(".toast")?.closest(".toast-stack")).toBeInTheDocument();

    vi.advanceTimersByTime(3999);
    expect(onDismiss).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledWith("upload-success");

  });

  it("keeps the original auto-dismiss schedule across rerenders", () => {
    vi.useFakeTimers();

    const firstOnDismiss = vi.fn();
    const secondOnDismiss = vi.fn();
    const firstNotifications: NotificationEntry[] = [
      {
        id: "upload-success",
        tone: "success",
        message: "Upload finished."
      }
    ];

    const { rerender } = render(
      <ToastStack notifications={firstNotifications} onDismiss={firstOnDismiss} />
    );

    vi.advanceTimersByTime(2000);

    const recreatedNotifications: NotificationEntry[] = [
      {
        id: "upload-success",
        tone: "success",
        message: "Upload finished."
      }
    ];

    rerender(<ToastStack notifications={recreatedNotifications} onDismiss={secondOnDismiss} />);

    vi.advanceTimersByTime(1999);
    expect(firstOnDismiss).not.toHaveBeenCalled();
    expect(secondOnDismiss).not.toHaveBeenCalled();

    vi.advanceTimersByTime(1);
    expect(firstOnDismiss).not.toHaveBeenCalled();
    expect(secondOnDismiss).toHaveBeenCalledTimes(1);
    expect(secondOnDismiss).toHaveBeenCalledWith("upload-success");
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

    expect(screen.getByText("Storage is almost full.").closest(".toast-warning")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Dismiss notification" }));

    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(onDismiss).toHaveBeenCalledWith("quota-warning");
  });

  it("renders ready content without requiring error details", () => {
    render(
      <FeedbackSurface
        viewState="ready"
        loadingLabel="Loading photos"
        error={null}
        onRetry={vi.fn()}
        notifications={[
          {
            id: "ready-toast",
            tone: "success",
            message: "Ready state."
          }
        ]}
        onDismissNotification={vi.fn()}
      >
        <p>Browse content</p>
      </FeedbackSurface>
    );

    expect(screen.getByText("Browse content")).toBeInTheDocument();
    expect(screen.queryByRole("heading", { level: 2 })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Dismiss notification" })).toBeInTheDocument();
  });
});
