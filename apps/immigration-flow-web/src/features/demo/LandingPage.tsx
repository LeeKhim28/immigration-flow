import { useState } from "react";
import { Link } from "react-router-dom";

import { AsyncBoundary } from "../../components/AsyncBoundary";
import styles from "./LandingPage.module.css";
import { useDemoSession, useResetDemoSession } from "./session";

export function LandingPage() {
  const session = useDemoSession();
  const reset = useResetDemoSession();
  const [confirming, setConfirming] = useState(false);
  const [resetComplete, setResetComplete] = useState(false);

  async function confirmReset() {
    try {
      await reset.mutateAsync();
      setConfirming(false);
      setResetComplete(true);
    } catch {
      setResetComplete(false);
    }
  }

  return (
    <AsyncBoundary
      isPending={session.isPending}
      error={session.error}
      retry={() => void session.refetch()}
    >
      {session.data ? (
        <div className={styles.layout}>
          <section className={styles.hero} aria-labelledby="demo-title">
            <p className="eyebrow">Student Pass V1 · Synthetic data only</p>
            <h1 id="demo-title">One case. Two perspectives. Every rule traceable.</h1>
            <p>
              Follow a prepared Student Pass case from applicant handover to officer processing,
              backed by versioned official-source research and append-only evidence.
            </p>
          </section>
          <section className={styles.roles} aria-label="Choose a demo workspace">
            <article>
              <p className="eyebrow">Applicant</p>
              <h2>Prepare with clarity</h2>
              <p>Review requirements, readiness findings, and the formal handover boundary.</p>
              <Link to={`/applicant/cases/${session.data.case_id}`}>Explore as Applicant</Link>
            </article>
            <article>
              <p className="eyebrow">Officer</p>
              <h2>Review with evidence</h2>
              <p>See the queue, assigned rule version, findings, and immutable timeline.</p>
              <Link to="/officer/cases">Explore as Officer</Link>
            </article>
          </section>
          <section className={styles.resetPanel}>
            <div>
              <strong>{session.data.case_number}</strong>
              <p>Reset withdraws this synthetic case while preserving its audit history.</p>
            </div>
            <button type="button" onClick={() => setConfirming(true)}>Reset demo</button>
          </section>
          {resetComplete ? <p role="status">A fresh synthetic case is ready.</p> : null}
          {confirming ? (
            <div role="dialog" aria-modal="true" aria-labelledby="reset-title" className={styles.dialog}>
              <h2 id="reset-title">Reset this demo?</h2>
              <p>The current case will be withdrawn and kept in the audit history.</p>
              {reset.error ? <p role="alert">The replacement case could not be prepared. This browser will keep the current demo reference so you can retry.</p> : null}
              <div>
                <button type="button" onClick={() => void confirmReset()} disabled={reset.isPending}>
                  Confirm reset
                </button>
                <button type="button" onClick={() => setConfirming(false)}>Cancel</button>
              </div>
            </div>
          ) : null}
        </div>
      ) : null}
    </AsyncBoundary>
  );
}
