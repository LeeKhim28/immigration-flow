import { useState } from "react";
import { useParams } from "react-router-dom";

import { ApiError } from "../../api/client";
import { AsyncBoundary } from "../../components/AsyncBoundary";
import styles from "./Applicant.module.css";
import { useApplicantCase, useSubmitCase } from "./api";

export function HandoverPage({ actorId }: { actorId: string }) {
  const { caseId = "" } = useParams();
  const detail = useApplicantCase(caseId, actorId);
  const submit = useSubmitCase(caseId, actorId);
  const [confirming, setConfirming] = useState(false);
  return <AsyncBoundary isPending={detail.isPending} error={detail.error} retry={() => void detail.refetch()}>
    <section className={styles.panel}>
      <p className="eyebrow">Formal handover</p><h2>Submit prepared case to Immigration</h2>
      <p>The server-created Immigration submission timestamp determines which official rule version applies. Officer processing happens afterward and does not change that boundary.</p>
      <button type="button" disabled={detail.data?.status !== "DRAFT"} onClick={() => setConfirming(true)}>Submit to Immigration</button>
      {submit.isSuccess ? <p role="status">Handover recorded at {new Date(submit.data.submitted_at).toLocaleString()}.</p> : null}
      {submit.error ? <p role="alert">{submit.error instanceof ApiError && submit.error.status === 409 ? "The case state changed. Current details were refreshed." : "Handover could not be recorded."}</p> : null}
      {confirming ? <div role="dialog" aria-modal="true" aria-labelledby="handover-title" className={styles.dialog}>
        <h3 id="handover-title">Confirm formal handover</h3><p>This records that the applicant has completed their submission task. It is not an approval.</p>
        <div className={styles.actions}><button type="button" onClick={() => { setConfirming(false); submit.mutate(); }}>Confirm handover</button><button type="button" onClick={() => setConfirming(false)}>Cancel</button></div>
      </div> : null}
    </section>
  </AsyncBoundary>;
}
