import { Link, Outlet } from "react-router-dom";

export function App() {
  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">Skip to main content</a>
      <header className="site-header">
        <Link className="brand" to="/" aria-label="ImmigrationFlow home">
          <span className="brand-mark" aria-hidden="true">IF</span>
          <span>ImmigrationFlow</span>
        </Link>
        <p className="prototype-label">Independent portfolio prototype · Synthetic data only</p>
      </header>
      <main id="main-content" tabIndex={-1}>
        <Outlet />
      </main>
      <footer>
        Not an official Malaysian government service. Verify requirements with official authorities.
      </footer>
    </div>
  );
}

export function HomePage() {
  return (
    <section className="hero" aria-labelledby="hero-title">
      <p className="eyebrow">Student Pass V1</p>
      <h1 id="hero-title">A traceable path through immigration case preparation</h1>
      <p>
        Explore how versioned official sources, deterministic rules, and auditable workflows can
        support applicants and reviewers without pretending to make official decisions.
      </p>
    </section>
  );
}

export function NotFoundPage() {
  return (
    <section className="message-panel">
      <p className="eyebrow">404</p>
      <h1>Page not found</h1>
      <p>The page you requested is not part of this demo.</p>
      <Link to="/">Return to demo</Link>
    </section>
  );
}
