import type { ReactNode } from "react";

type AsyncBoundaryProps = {
  isPending: boolean;
  error: Error | null;
  retry: () => void;
  children: ReactNode;
};

export function AsyncBoundary({ isPending, error, retry, children }: AsyncBoundaryProps) {
  if (isPending) return <p role="status">Preparing synthetic demo…</p>;
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
