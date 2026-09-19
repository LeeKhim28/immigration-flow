import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { HttpResponse, http } from "msw";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { routes } from "./router";
import { server } from "../test/server";

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
});
