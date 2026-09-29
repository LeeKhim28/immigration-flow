import { useParams } from "react-router-dom";
import { ApiError } from "../../api/client";
import { AsyncBoundary } from "../../components/AsyncBoundary";
import { AuditTimeline } from "./AuditTimeline";
import styles from "./Officer.module.css";
import { useOfficerCase, useStartProcessing } from "./api";

export function OfficerCasePage({ actorId }: { actorId: string }) {
  const { caseId = "" } = useParams();
  const query = useOfficerCase(caseId, actorId);
  const start = useStartProcessing(caseId, actorId);
  return <AsyncBoundary isPending={query.isPending} error={query.error} retry={() => void query.refetch()} recoverDemoSession>{query.data ? <>
    <section className={styles.panel}><p className="eyebrow">Synthetic case · Rule set {query.data.rule_set_version ?? "unassigned"}</p><h2>{query.data.case_number}</h2><p>{query.data.institution.name} · {query.data.programme.name}</p>
      <button type="button" disabled={query.data.status !== "SUBMITTED" || start.isPending} onClick={() => start.mutate()}>Start processing</button>
      {start.isSuccess ? <p role="status">Processing started.</p> : null}
      {start.error ? <p role="alert">{start.error instanceof ApiError && start.error.status === 409 ? "The case state changed. Current evidence was refreshed." : "Processing could not be started."}</p> : null}
    </section>
    <section className={styles.panel}><h2>Checklist and official sources</h2>{!query.data.checklist.requirements.length ? <p>No assigned checklist.</p> : <ul>{query.data.checklist.requirements.map((item) => <li key={item.requirement_code}>
      <strong>{item.statement}</strong> — {item.status}
      <ul>{item.sources.map((source) => <li key={`${source.canonical_url}-${source.locator}`}><a href={source.canonical_url} target="_blank" rel="noreferrer">{source.title}</a> · {source.locator}{source.reviewed_at ? ` · reviewed ${new Date(source.reviewed_at).toLocaleDateString()}` : ""}</li>)}</ul>
    </li>)}</ul>}</section>
    <section className={styles.panel}><h2>Deterministic findings</h2>{!query.data.evaluations.length ? <p>No evaluation recorded.</p> : query.data.evaluations.map((evaluation) => <article key={evaluation.id}><h3>{evaluation.outcome.replaceAll("_", " ")}</h3><p className={styles.muted}>Evaluated {new Date(evaluation.evaluated_at).toLocaleString()} using {evaluation.rule_set_version}</p><ul>{evaluation.findings.map((finding) => <li key={finding.id}><strong>{finding.outcome}</strong> — <span>{finding.message}</span></li>)}</ul></article>)}</section>
    <AuditTimeline events={query.data.events} />
  </> : null}</AsyncBoundary>;
}
