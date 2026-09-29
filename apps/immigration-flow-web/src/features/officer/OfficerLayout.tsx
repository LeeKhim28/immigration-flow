import { Link, Outlet } from "react-router-dom";
import styles from "./Officer.module.css";

export function OfficerLayout() {
  return <div className={styles.workspace}><header className={styles.header}><div><p className="eyebrow">Officer workspace</p><h1>Evidence-led case review</h1></div><Link to="/">Switch workspace</Link></header><Outlet /></div>;
}
