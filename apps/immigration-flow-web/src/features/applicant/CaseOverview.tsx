import { useParams } from "react-router-dom";

import { AsyncBoundary } from "../../components/AsyncBoundary";
import styles from "./Applicant.module.css";
import { useApplicantCase } from "./api";

export function CaseOverview({ actorId }: { actorId: string }) {
  const { caseId = "" } = useParams();
  const query = useApplicantCase(caseId, actorId);
  return <AsyncBoundary isPending={query.isPending} error={query.error} retry={() => void query.refetch()} recoverDemoSession>
    {query.data ? <section className={styles.panel}>
      <p className="eyebrow">Synthetic case</p>
      <h2>{query.data.case_number}</h2>
      <p className={styles.status} aria-label={`Status ${query.data.status.replaceAll("_", " ")}`}>
        <span aria-hidden="true">●</span>{query.data.status.replaceAll("_", " ")}
      </p>
      <dl className={styles.grid}>
        <div className={styles.fact}><dt>Institution</dt><dd>{query.data.institution.name}</dd></div>
        <div className={styles.fact}><dt>Programme</dt><dd>{query.data.programme.name}</dd></div>
        <div className={styles.fact}><dt>Nationality</dt><dd>{query.data.nationality_code}</dd></div>
        <div className={styles.fact}><dt>Passport expiry</dt><dd>{new Date(query.data.passport_expires_at).toLocaleDateString()}</dd></div>
      </dl>
    </section> : null}
  </AsyncBoundary>;
}
