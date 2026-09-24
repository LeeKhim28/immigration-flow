import type { ReactNode } from "react";

import { AsyncBoundary } from "../../components/AsyncBoundary";
import { useDemoSession } from "../demo/session";
import { CaseOverview } from "./CaseOverview";
import { EvaluationPage } from "./EvaluationPage";
import { HandoverPage } from "./HandoverPage";
import { RequirementsPage } from "./RequirementsPage";

function ApplicantSessionRoute({ children }: { children: (actorId: string) => ReactNode }) {
  const session = useDemoSession();
  return <AsyncBoundary isPending={session.isPending} error={session.error} retry={() => void session.refetch()}>
    {session.data ? children(session.data.applicant_actor_id) : null}
  </AsyncBoundary>;
}

export function OverviewRoute() { return <ApplicantSessionRoute>{(actorId) => <CaseOverview actorId={actorId} />}</ApplicantSessionRoute>; }
export function RequirementsRoute() { return <ApplicantSessionRoute>{(actorId) => <RequirementsPage actorId={actorId} />}</ApplicantSessionRoute>; }
export function EvaluationRoute() { return <ApplicantSessionRoute>{(actorId) => <EvaluationPage actorId={actorId} />}</ApplicantSessionRoute>; }
export function HandoverRoute() { return <ApplicantSessionRoute>{(actorId) => <HandoverPage actorId={actorId} />}</ApplicantSessionRoute>; }
