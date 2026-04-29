import { useEffect, useRef } from "react";
import type { NotificationEntry } from "./feedbackTypes";

export const DEFAULT_TIMEOUT_MS = 4000;

interface ToastStackProps {
  notifications: NotificationEntry[];
  onDismiss: (id: string) => void;
}

export function ToastStack({ notifications, onDismiss }: ToastStackProps) {
  const onDismissRef = useRef(onDismiss);
  const timersByIdRef = useRef<Map<string, number>>(new Map());
  const deadlinesByIdRef = useRef<Map<string, number>>(new Map());

  useEffect(() => {
    onDismissRef.current = onDismiss;
  }, [onDismiss]);

  useEffect(() => {
    const nextIds = new Set<string>();
    const now = Date.now();

    for (const notification of notifications) {
      nextIds.add(notification.id);

      if (timersByIdRef.current.has(notification.id)) {
        continue;
      }

      const deadline =
        deadlinesByIdRef.current.get(notification.id) ??
        now + (notification.timeoutMs ?? DEFAULT_TIMEOUT_MS);
      const remainingMs = Math.max(0, deadline - now);

      deadlinesByIdRef.current.set(notification.id, deadline);

      const timer = window.setTimeout(() => {
        timersByIdRef.current.delete(notification.id);
        deadlinesByIdRef.current.delete(notification.id);
        onDismissRef.current(notification.id);
      }, remainingMs);

      timersByIdRef.current.set(notification.id, timer);
    }

    for (const [id, timer] of timersByIdRef.current) {
      if (!nextIds.has(id)) {
        window.clearTimeout(timer);
        timersByIdRef.current.delete(id);
        deadlinesByIdRef.current.delete(id);
      }
    }
  }, [notifications]);

  useEffect(() => {
    return () => {
      for (const timer of timersByIdRef.current.values()) {
        window.clearTimeout(timer);
      }
      timersByIdRef.current.clear();
      deadlinesByIdRef.current.clear();
    };
  }, []);

  if (notifications.length === 0) {
    return null;
  }

  return (
    <div className="toast-stack" aria-live="polite" aria-atomic="true">
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
