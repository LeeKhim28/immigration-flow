import { useParams } from "react-router-dom";

import { AsyncBoundary } from "../../components/AsyncBoundary";
import styles from "./Applicant.module.css";
import { useChecklist } from "./api";

export function RequirementsPage({ actorId }: { actorId: string }) {
  const { caseId = "" } = useParams();
  const query = useChecklist(caseId, actorId);
  return <AsyncBoundary isPending={query.isPending} error={query.error} retry={() => void query.refetch()}>
    {query.data ? <section className={styles.panel}>
      <p className="eyebrow">Rule set {query.data.rule_set_version}</p>
      <h2>Requirements and document readiness</h2>
      <p className={styles.muted}>This portfolio demo stores metadata only—never real passport or document bytes. Each assigned requirement is derived from reviewed official-source records.</p>
      <ul className={styles.requirements}>{query.data.requirements.map((item) => <li key={item.requirement_code}>
        <strong>{item.statement}</strong><br /><span>{item.status} · {item.machine_handling}</span>
      </li>)}</ul>
    </section> : null}
  </AsyncBoundary>;
}
