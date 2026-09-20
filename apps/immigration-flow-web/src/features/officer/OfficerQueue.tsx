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
  </div><AsyncBoundary isPending={query.isPending} error={query.error} retry={() => void query.refetch()}>
    {!query.data?.length ? <p>No {status.toLowerCase().replace("_", " ")} cases in the queue.</p> : <table className={styles.queue}><thead><tr><th>Case</th><th>Status</th><th>Stage</th></tr></thead><tbody>{query.data.map((item) => <tr key={item.id}>
      <td data-label="Case"><Link to={`/officer/cases/${item.id}`}>{item.case_number}</Link></td>
      <td data-label="Status"><span className={styles.status} aria-label={`Status ${item.status}`}><span aria-hidden="true">●</span>{item.status}</span></td>
      <td data-label="Stage">{item.stage.replaceAll("_", " ")}</td>
    </tr>)}</tbody></table>}
  </AsyncBoundary></section>;
}
