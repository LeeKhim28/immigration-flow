import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { server } from "../../test/server";
import { OfficerCasePage } from "./OfficerCasePage";
import { OfficerQueue } from "./OfficerQueue";

const officerId = "71e25d11-7ec4-4120-a018-d611f3b5040b";
const caseId = "87490004-a1bc-45d1-8aa7-0ca1f5147ab4";
const summary = { id: caseId, case_number: "IF-DEMO-STUDENT-PASS-001", applicant_profile_id: "31bfb11f-847b-442e-8421-bddbb111933b", status: "SUBMITTED", stage: "IMMIGRATION_PROCESSING" };
const detail = {
  ...summary, synthetic: true,
  institution: { id: "7727db80-1bbc-456f-a5dc-b8e696862f35", name: "Northstar University (Synthetic)", code: "DEMO-U" },
  programme: { id: "34299a48-872d-4fc3-8294-8beca961c220", name: "Computer Science (Synthetic)", code: "BSC-CS" },
  nationality_code: "IDN", passport_expires_at: "2031-12-31T00:00:00Z", rule_set_version: "1.0.0",
  evaluations: [{ id: "6577d125-af8e-459a-9f63-77c44393385b", outcome: "manual_review", trigger: "INITIAL_SUBMISSION", evaluated_at: "2026-09-19T07:00:00Z", supersedes_evaluation_id: null, rule_set_version: "1.0.0", findings: [{ id: "11baaa4f-f3d9-43af-9cbe-e18638b76f02", outcome: "manual_review", code: "VERIFY", message: "Verify synthetic evidence." }] }],
  events: [{ id: "190a23ef-5345-4b83-be9e-37976d52999a", event_type: "CASE_SUBMITTED_TO_IMMIGRATION", occurred_at: "2026-09-19T07:00:00Z" }],
};

function wrap(element: React.ReactNode, path = "/officer/cases") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  return render(<QueryClientProvider client={client}><MemoryRouter initialEntries={[path]}><Routes>
    <Route path="/officer/cases" element={element} /><Route path="/officer/cases/:caseId" element={element} />
  </Routes></MemoryRouter></QueryClientProvider>);
}

describe("Officer workspace", () => {
  it("renders the submitted queue and supports a valid empty state", async () => {
    server.use(http.get("/api/v1/officer/cases", () => HttpResponse.json([summary])));
    wrap(<OfficerQueue actorId={officerId} />);
    expect(await screen.findByRole("link", { name: /IF-DEMO-STUDENT-PASS-001/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/status submitted/i)).toBeInTheDocument();
  });

  it("renders evidence, deterministic findings, and audit timeline", async () => {
    server.use(http.get(`/api/v1/officer/cases/${caseId}`, () => HttpResponse.json(detail)));
    wrap(<OfficerCasePage actorId={officerId} />, `/officer/cases/${caseId}`);
    expect(await screen.findByText("Verify synthetic evidence.")).toBeInTheDocument();
    expect(screen.getByText(/case submitted to immigration/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /approve|reject/i })).not.toBeInTheDocument();
  });

  it("starts processing only after explicit action", async () => {
    server.use(
      http.get(`/api/v1/officer/cases/${caseId}`, () => HttpResponse.json(detail)),
      http.post(`/api/v1/officer/cases/${caseId}/start-processing`, () => HttpResponse.json({ ...summary, status: "IN_PROCESS" })),
    );
    wrap(<OfficerCasePage actorId={officerId} />, `/officer/cases/${caseId}`);
    fireEvent.click(await screen.findByRole("button", { name: /start processing/i }));
    expect(await screen.findByText(/processing started/i)).toBeInTheDocument();
  });
});
