import type { ReactNode } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { ApiError } from "../api/client";
import { clearDemoSession, demoSessionQueryKey } from "../features/demo/session";

type AsyncBoundaryProps = {
  isPending: boolean;
  error: Error | null;
  retry: () => void;
  children: ReactNode;
  recoverDemoSession?: boolean;
};

function DemoSessionRecovery() {
  const queryClient = useQueryClient();
  clearDemoSession();
  queryClient.removeQueries({ queryKey: demoSessionQueryKey, exact: true });
  return <section role="alert" className="message-panel">
    <h1>Demo session refreshed</h1>
    <p>The saved case or workspace access was no longer valid.</p>
    <Link to="/" replace>Return to demo</Link>
  </section>;
}

export function AsyncBoundary({ isPending, error, retry, children, recoverDemoSession = false }: AsyncBoundaryProps) {
  if (isPending) return <p role="status">Preparing synthetic demo…</p>;
  if (recoverDemoSession && error instanceof ApiError && (error.status === 403 || error.status === 404)) {
    return <DemoSessionRecovery />;
  }
  if (error) {
    return (
      <section role="alert" className="message-panel">
        <h1>Demo temporarily unavailable</h1>
        <p>The local service could not prepare the synthetic case.</p>
        <button type="button" onClick={retry}>Try again</button>
      </section>
    );
  }
  return children;
}
