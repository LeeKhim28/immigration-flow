import { useParams } from "react-router-dom";

import { AsyncBoundary } from "../../components/AsyncBoundary";
import styles from "./Applicant.module.css";
import { useEvaluations } from "./api";

export function EvaluationPage({ actorId }: { actorId: string }) {
  const { caseId = "" } = useParams();
  const query = useEvaluations(caseId, actorId);
  return <AsyncBoundary isPending={query.isPending} error={query.error} retry={() => void query.refetch()} recoverDemoSession>
    <section className={styles.panel}>
      <p className="eyebrow">Deterministic checks · Not an official decision</p>
      <h2>Readiness result</h2>
      {!query.data?.evaluations.length ? <p>No readiness evaluation has been recorded yet. It runs when the case is formally handed over.</p> :
        query.data.evaluations.map((evaluation) => <article key={evaluation.id}>
          <h3>{evaluation.outcome.replaceAll("_", " ")}</h3>
          <p>Rule set {evaluation.rule_set_version} · {new Date(evaluation.evaluated_at).toLocaleString()}</p>
          <ul>{evaluation.findings.map((finding) => <li key={finding.id}><strong>{finding.outcome}</strong> — {finding.message}</li>)}</ul>
        </article>)}
    </section>
  </AsyncBoundary>;
}
