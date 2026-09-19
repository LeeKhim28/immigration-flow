import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { server } from "../../test/server";
import { LandingPage } from "./LandingPage";
import { clearDemoSession } from "./session";

const response = {
  applicant_actor_id: "5f73f646-da4c-466d-a842-d59167d508ae",
  officer_actor_id: "71e25d11-7ec4-4120-a018-d611f3b5040b",
  case_id: "87490004-a1bc-45d1-8aa7-0ca1f5147ab4",
  case_number: "IF-DEMO-STUDENT-PASS-001",
};

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter><LandingPage /></MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("LandingPage", () => {
  beforeEach(() => clearDemoSession());

  it("bootstraps the demo and links to both role workspaces", async () => {
    server.use(http.post("/api/v1/demo/session", () => HttpResponse.json(response)));
    renderPage();

    expect(screen.getByRole("status")).toHaveTextContent(/preparing synthetic demo/i);
    expect(await screen.findByRole("link", { name: /explore as applicant/i })).toHaveAttribute(
      "href", `/applicant/cases/${response.case_id}`,
    );
    expect(screen.getByRole("link", { name: /explore as officer/i })).toHaveAttribute(
      "href", "/officer/cases",
    );
    expect(screen.getByText(/synthetic data only/i)).toBeInTheDocument();
  });

  it("shows a retry action when bootstrap is unavailable", async () => {
    server.use(http.post("/api/v1/demo/session", () => HttpResponse.error()));
    renderPage();

    expect(await screen.findByRole("alert")).toHaveTextContent(/temporarily unavailable/i);
    expect(screen.getByRole("button", { name: /try again/i })).toBeEnabled();
  });

  it("requires confirmation before resetting the current scenario", async () => {
    server.use(
      http.post("/api/v1/demo/session", () => HttpResponse.json(response)),
      http.delete("/api/v1/demo/session", () => new HttpResponse(null, { status: 204 })),
    );
    renderPage();
    await screen.findByRole("link", { name: /explore as applicant/i });

    fireEvent.click(screen.getByRole("button", { name: /reset demo/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /confirm reset/i }));

    expect(await screen.findByText(/fresh synthetic case is ready/i)).toBeInTheDocument();
  });
});
