import styles from "./Officer.module.css";

export function AuditTimeline({ events }: { events: Array<{ id: string; event_type: string; occurred_at: string }> }) {
  return <section className={styles.panel}><h2>Audit timeline</h2><ol className={styles.timeline}>{events.map((event) => <li key={event.id}><strong>{event.event_type.replaceAll("_", " ")}</strong><br /><time dateTime={event.occurred_at}>{new Date(event.occurred_at).toLocaleString()}</time></li>)}</ol></section>;
}
