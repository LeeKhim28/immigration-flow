import { useState } from "react";
import { Link } from "react-router-dom";
import { AsyncBoundary } from "../../components/AsyncBoundary";
import styles from "./Officer.module.css";
import { useOfficerQueue } from "./api";

export function OfficerQueue({ actorId }: { actorId: string }) {
  const [status, setStatus] = useState<"SUBMITTED" | "IN_PROCESS">("SUBMITTED");
  const query = useOfficerQueue(actorId, status);
  return <section className={styles.panel}><div className={styles.filters} aria-label="Queue status">
    <button type="button" onClick={() => setStatus("SUBMITTED")}>Submitted</button><button type="button" onClick={() => setStatus("IN_PROCESS")}>In process</button>
  </div><AsyncBoundary isPending={query.isPending} error={query.error} retry={() => void query.refetch()} recoverDemoSession>
    {!query.data?.length ? <p>No {status.toLowerCase().replace("_", " ")} cases in the queue.</p> : <table className={styles.queue}><thead><tr><th>Case</th><th>Submitted</th><th>Institution</th><th>Readiness</th><th>Status</th></tr></thead><tbody>{query.data.map((item) => <tr key={item.id}>
      <td data-label="Case"><Link to={`/officer/cases/${item.id}`}>{item.case_number}</Link></td>
      <td data-label="Submitted">{new Date(item.submitted_at).toLocaleString()}</td>
      <td data-label="Institution">{item.institution.name}</td>
      <td data-label="Readiness">{item.readiness.outcome.replaceAll("_", " ")} · {item.readiness.finding_count} {item.readiness.finding_count === 1 ? "finding" : "findings"}</td>
      <td data-label="Status"><span className={styles.status} aria-label={`Status ${item.status}`}><span aria-hidden="true">●</span>{item.status}</span></td>
    </tr>)}</tbody></table>}
  </AsyncBoundary></section>;
}
