import { useParams } from "react-router-dom";

import { AsyncBoundary } from "../../components/AsyncBoundary";
import styles from "./Applicant.module.css";
import { useChecklist } from "./api";

export function RequirementsPage({ actorId }: { actorId: string }) {
  const { caseId = "" } = useParams();
  const query = useChecklist(caseId, actorId);
  return <AsyncBoundary isPending={query.isPending} error={query.error} retry={() => void query.refetch()} recoverDemoSession>
    {query.data ? <section className={styles.panel}>
      <p className="eyebrow">Rule set {query.data.rule_set_version}</p>
      <h2>Requirements and document readiness</h2>
      <p className={styles.muted}>This portfolio demo stores metadata only—never real passport or document bytes. Each assigned requirement is derived from reviewed official-source records.</p>
      <ul className={styles.requirements}>{query.data.requirements.map((item) => <li key={item.requirement_code}>
        <strong>{item.statement}</strong><br /><span>{item.status} · {item.machine_handling}</span>
        <ul>{item.sources.map((source) => <li key={`${source.canonical_url}-${source.locator}`}>
          <a href={source.canonical_url} target="_blank" rel="noreferrer">{source.title}</a>
          <span> · {source.locator}{source.reviewed_at ? ` · reviewed ${new Date(source.reviewed_at).toLocaleDateString()}` : ""}</span>
        </li>)}</ul>
      </li>)}</ul>
    </section> : null}
  </AsyncBoundary>;
}
