import { readDemoSession } from "../demo/session";
import { OfficerCasePage } from "./OfficerCasePage";
import { OfficerQueue } from "./OfficerQueue";

function officerActorId() { return readDemoSession()?.officer_actor_id ?? ""; }
export function QueueRoute() { return <OfficerQueue actorId={officerActorId()} />; }
export function CaseRoute() { return <OfficerCasePage actorId={officerActorId()} />; }
