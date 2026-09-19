import { render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { describe, expect, it } from "vitest";

import { routes } from "./router";

describe("application shell", () => {
  it("labels the product as an independent synthetic prototype", async () => {
    const router = createMemoryRouter(routes, { initialEntries: ["/"] });
    render(<RouterProvider router={router} />);

    expect(await screen.findByRole("banner")).toHaveTextContent(/independent portfolio prototype/i);
    expect(screen.getByRole("main")).toBeInTheDocument();
  });

  it("renders an in-product not-found page", async () => {
    const router = createMemoryRouter(routes, { initialEntries: ["/missing"] });
    render(<RouterProvider router={router} />);

    expect(await screen.findByRole("heading", { name: /page not found/i })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /return to demo/i })).toHaveAttribute("href", "/");
  });
});
