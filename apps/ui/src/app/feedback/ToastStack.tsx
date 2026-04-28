import { useEffect } from "react";
import type { NotificationEntry } from "./feedbackTypes";

export const DEFAULT_TIMEOUT_MS = 4000;

type ToastStackProps = {
  notifications: NotificationEntry[];
  onDismiss: (id: string) => void;
};

export function ToastStack({ notifications, onDismiss }: ToastStackProps) {
  useEffect(() => {
    const timers = notifications.map((notification) =>
      window.setTimeout(() => {
        onDismiss(notification.id);
      }, notification.timeoutMs ?? DEFAULT_TIMEOUT_MS)
    );

    return () => {
      timers.forEach((timer) => {
        window.clearTimeout(timer);
      });
    };
  }, [notifications, onDismiss]);

  if (notifications.length === 0) {
    return null;
  }

  return (
    <div aria-live="polite" aria-atomic="true">
      {notifications.map((notification) => (
        <article key={notification.id} className={`toast toast-${notification.tone}`}>
          <p>{notification.message}</p>
          <button
            type="button"
            aria-label="Dismiss notification"
            onClick={() => onDismiss(notification.id)}
          >
            Dismiss
          </button>
        </article>
      ))}
    </div>
  );
}
