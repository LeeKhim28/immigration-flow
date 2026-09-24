import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { beforeEach, describe, expect, it } from "vitest";

import { routes } from "./router";
import { server } from "../test/server";
import { clearDemoSession, STORAGE_KEY, writeDemoSession } from "../features/demo/session";

const demo = {
  applicant_actor_id: "5f73f646-da4c-466d-a842-d59167d508ae",
  officer_actor_id: "71e25d11-7ec4-4120-a018-d611f3b5040b",
  case_id: "87490004-a1bc-45d1-8aa7-0ca1f5147ab4",
  case_number: "IF-DEMO-STUDENT-PASS-001",
};

function renderRouter(initialEntry: string) {
  const router = createMemoryRouter(routes, { initialEntries: [initialEntry] });
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <RouterProvider router={router} />
    </QueryClientProvider>,
  );
}

describe("application shell", () => {
  beforeEach(() => clearDemoSession());

  it("labels the product as an independent synthetic prototype", async () => {
    server.use(http.post("/api/v1/demo/session", () => HttpResponse.json(demo)));
    renderRouter("/");

    expect(await screen.findByRole("banner")).toHaveTextContent(/independent portfolio prototype/i);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("renders an in-product not-found page", async () => {
    renderRouter("/missing");

    expect(await screen.findByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /return to demo/i })).toHaveAttribute("href", "/");
  });

  it("bootstraps a missing session before loading a direct applicant route", async () => {
    let actorHeader: string | null = null;
    server.use(
      http.post("/api/v1/demo/session", () => HttpResponse.json(demo)),
      http.get(`/api/v1/applicant/cases/${demo.case_id}`, ({ request }) => {
        actorHeader = request.headers.get("X-Actor-Id");
        return HttpResponse.json({
          id: demo.case_id, case_number: demo.case_number,
          applicant_profile_id: "31bfb11f-847b-442e-8421-bddbb111933b",
          status: "DRAFT", stage: "PRE_SUBMISSION", synthetic: true,
          institution: { id: "7727db80-1bbc-456f-a5dc-b8e696862f35", name: "Northstar University (Synthetic)", code: "DEMO-U" },
          programme: { id: "34299a48-872d-4fc3-8294-8beca961c220", name: "Computer Science (Synthetic)", code: "BSC-CS" },
          nationality_code: "IDN", passport_expires_at: "2031-12-31T00:00:00Z", rule_set_version: null,
        });
      }),
    );

    renderRouter(`/applicant/cases/${demo.case_id}`);

    expect(await screen.findByText("Northstar University (Synthetic)")).toBeInTheDocument();
    expect(actorHeader).toBe(demo.applicant_actor_id);
  });

  it("clears a stale session and returns to the landing page after a case 404", async () => {
    const stale = { ...demo, case_id: "eb13f995-0349-4e83-b1df-eed7d68ed002" };
    writeDemoSession(stale);
    server.use(
      http.get(`/api/v1/applicant/cases/${stale.case_id}`, () => HttpResponse.json({ detail: "Not found" }, { status: 404 })),
      http.post("/api/v1/demo/session", () => HttpResponse.json(demo)),
    );

    renderRouter(`/applicant/cases/${stale.case_id}`);

    expect(await screen.findByRole("link", { name: /return to demo/i })).toHaveAttribute(
      "href", "/",
    );
    expect(localStorage.getItem(STORAGE_KEY)).toContain(demo.case_id);
  });

  it("clears a wrong-role session and returns to the landing page after a 403", async () => {
    writeDemoSession(demo);
    server.use(
      http.get("/api/v1/officer/cases", () => HttpResponse.json({ detail: "Forbidden" }, { status: 403 })),
      http.post("/api/v1/demo/session", () => HttpResponse.json(demo)),
    );

    renderRouter("/officer/cases");

    expect(await screen.findByRole("link", { name: /return to demo/i })).toHaveAttribute(
      "href", "/",
    );
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });
});
