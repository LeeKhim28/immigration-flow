import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../../test/server";
import { CaseOverview } from "./CaseOverview";
import { EvaluationPage } from "./EvaluationPage";
import { HandoverPage } from "./HandoverPage";
import { RequirementsPage } from "./RequirementsPage";

const actorId = "5f73f646-da4c-466d-a842-d59167d508ae";
const caseId = "87490004-a1bc-45d1-8aa7-0ca1f5147ab4";
const detail = {
  id: caseId, case_number: "IF-DEMO-STUDENT-PASS-001",
  applicant_profile_id: "31bfb11f-847b-442e-8421-bddbb111933b",
  status: "DRAFT", stage: "PRE_SUBMISSION", synthetic: true,
  institution: { id: "7727db80-1bbc-456f-a5dc-b8e696862f35", name: "Northstar University (Synthetic)", code: "DEMO-U" },
  programme: { id: "34299a48-872d-4fc3-8294-8beca961c220", name: "Computer Science (Synthetic)", code: "BSC-CS" },
  nationality_code: "IDN", passport_expires_at: "2031-12-31T00:00:00Z", rule_set_version: null,
};

function renderPage(element: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(
    <QueryClientProvider client={client}><MemoryRouter initialEntries={[`/applicant/cases/${caseId}`]}>
      <Routes><Route path="/applicant/cases/:caseId" element={element} /></Routes>
    </MemoryRouter></QueryClientProvider>,
  );
}

function mockDetail() {
  server.use(http.get(`/api/v1/applicant/cases/${caseId}`, () => HttpResponse.json(detail)));
}

describe("Applicant workspace", () => {
  it("shows synthetic case, institution, programme, and readable status", async () => {
    mockDetail(); renderPage(<CaseOverview actorId={actorId} />);
    expect(await screen.findByText("Northstar University (Synthetic)")).toBeInTheDocument();
    expect(screen.getByText("Computer Science (Synthetic)")).toBeInTheDocument();
    expect(screen.getByText(/draft/i)).toHaveAccessibleName(/status draft/i);
    expect(screen.getByText(/synthetic case/i)).toBeInTheDocument();
  });

  it("shows source-ready checklist copy and metadata-only boundary", async () => {
    server.use(http.get(`/api/v1/applicant/cases/${caseId}/checklist`, () => HttpResponse.json({
      rule_set_version: "1.0.0", requirements: [{ requirement_code: "SP-PASSPORT", statement: "Provide passport biodata.", machine_handling: "Metadata validation", status: "PENDING" }],
    })));
    renderPage(<RequirementsPage actorId={actorId} />);
    expect(await screen.findByText(/rule set 1.0.0/i)).toBeInTheDocument();
    expect(screen.getByText(/metadata only/i)).toBeInTheDocument();
    expect(screen.getByText("Provide passport biodata.")).toBeInTheDocument();
  });

  it("labels deterministic output as readiness rather than approval", async () => {
    server.use(http.get(`/api/v1/applicant/cases/${caseId}/evaluation`, () => HttpResponse.json({ evaluations: [] })));
    renderPage(<EvaluationPage actorId={actorId} />);
    expect(await screen.findByRole("heading", { name: /readiness result/i })).toBeInTheDocument();
    expect(screen.queryByText(/approval prediction/i)).not.toBeInTheDocument();
  });

  it("requires confirmation before handover", async () => {
    mockDetail();
    server.use(http.post(`/api/v1/applicant/cases/${caseId}/submit`, () => HttpResponse.json({
      id: "dda98f90-f502-4603-ac9e-98a25116f3d4", case_id: caseId, status: "SUBMITTED",
      submitted_at: "2026-09-19T07:00:00Z", accepted_at: null,
    }, { status: 201 })));
    renderPage(<HandoverPage actorId={actorId} />);
    await screen.findByText(/immigration submission timestamp/i);
    fireEvent.click(screen.getByRole("button", { name: /submit to immigration/i }));
    expect(screen.getByRole("dialog")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: /confirm handover/i }));
    expect(await screen.findByText(/handover recorded/i)).toBeInTheDocument();
  });
});
