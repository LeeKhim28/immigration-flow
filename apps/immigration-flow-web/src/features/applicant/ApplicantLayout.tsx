import { NavLink, Outlet, useParams } from "react-router-dom";

import styles from "./Applicant.module.css";

export function ApplicantLayout() {
  const { caseId } = useParams();
  const base = `/applicant/cases/${caseId}`;
  return <div className={styles.workspace}>
    <header className={styles.workspaceHeader}><div><p className="eyebrow">Applicant workspace</p><h1>Student Pass preparation</h1></div><NavLink to="/">Switch workspace</NavLink></header>
    <nav className={styles.nav} aria-label="Applicant case"><NavLink end to={base}>Overview</NavLink><NavLink to={`${base}/requirements`}>Requirements</NavLink><NavLink to={`${base}/evaluation`}>Readiness</NavLink><NavLink to={`${base}/handover`}>Handover</NavLink></nav>
    <Outlet />
  </div>;
}
