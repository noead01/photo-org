import { useCallback, useState } from "react";

export function getRequestErrorMessage(caughtError: unknown, fallbackMessage: string): string {
  if (caughtError instanceof Error && caughtError.message.trim()) {
    return caughtError.message;
  }
  return fallbackMessage;
}

export function useRouteRequestState() {
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [reloadToken, setReloadToken] = useState(0);

  const beginRequest = useCallback(() => {
    setIsLoading(true);
    setError(null);
  }, []);

  const completeRequest = useCallback(() => {
    setIsLoading(false);
  }, []);

  const failRequest = useCallback((caughtError: unknown, fallbackMessage: string) => {
    setError(getRequestErrorMessage(caughtError, fallbackMessage));
    setIsLoading(false);
  }, []);

  const clearRequestState = useCallback(() => {
    setIsLoading(false);
    setError(null);
  }, []);

  const requestRetry = useCallback(() => {
    setReloadToken((current) => current + 1);
  }, []);

  return {
    isLoading,
    error,
    reloadToken,
    beginRequest,
    completeRequest,
    failRequest,
    clearRequestState,
    requestRetry
  };
}
