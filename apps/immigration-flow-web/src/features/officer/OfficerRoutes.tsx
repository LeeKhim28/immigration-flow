import type { ReactNode } from "react";

import { AsyncBoundary } from "../../components/AsyncBoundary";
import { useDemoSession } from "../demo/session";
import { OfficerCasePage } from "./OfficerCasePage";
import { OfficerQueue } from "./OfficerQueue";

function OfficerSessionRoute({ children }: { children: (actorId: string) => ReactNode }) {
  const session = useDemoSession();
  return <AsyncBoundary isPending={session.isPending} error={session.error} retry={() => void session.refetch()}>
    {session.data ? children(session.data.officer_actor_id) : null}
  </AsyncBoundary>;
}

export function QueueRoute() { return <OfficerSessionRoute>{(actorId) => <OfficerQueue actorId={actorId} />}</OfficerSessionRoute>; }
export function CaseRoute() { return <OfficerSessionRoute>{(actorId) => <OfficerCasePage actorId={actorId} />}</OfficerSessionRoute>; }
