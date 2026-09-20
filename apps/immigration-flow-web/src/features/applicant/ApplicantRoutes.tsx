import { readDemoSession } from "../demo/session";
import { CaseOverview } from "./CaseOverview";
import { EvaluationPage } from "./EvaluationPage";
import { HandoverPage } from "./HandoverPage";
import { RequirementsPage } from "./RequirementsPage";

function applicantActorId() {
  return readDemoSession()?.applicant_actor_id ?? "";
}

export function OverviewRoute() { return <CaseOverview actorId={applicantActorId()} />; }
export function RequirementsRoute() { return <RequirementsPage actorId={applicantActorId()} />; }
export function EvaluationRoute() { return <EvaluationPage actorId={applicantActorId()} />; }
export function HandoverRoute() { return <HandoverPage actorId={applicantActorId()} />; }
