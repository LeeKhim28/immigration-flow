import { HttpResponse, http } from "msw";
import { describe, expect, it } from "vitest";
import { z } from "zod";

import { ApiError, DataIntegrityError, apiRequest } from "./client";
import { server } from "../test/server";

describe("apiRequest", () => {
  it("rejects a malformed successful response", async () => {
    server.use(http.get("/api/example", () => HttpResponse.json({ id: 12 })));

    await expect(apiRequest("/api/example", z.object({ id: z.string() }))).rejects.toBeInstanceOf(
      DataIntegrityError,
    );
  });

  it("preserves conflict status and safe detail", async () => {
    server.use(
      http.post("/api/example", () =>
        HttpResponse.json({ detail: "Case changed" }, { status: 409 }),
      ),
    );

    await expect(apiRequest("/api/example", z.unknown(), { method: "POST" })).rejects.toMatchObject({
      status: 409,
      detail: "Case changed",
    } satisfies Partial<ApiError>);
  });

  it("sends an actor header only when supplied", async () => {
    let actorHeader: string | null = "unread";
    server.use(
      http.get("/api/example", ({ request }) => {
        actorHeader = request.headers.get("X-Actor-Id");
        return HttpResponse.json({ ok: true });
      }),
    );

    await apiRequest("/api/example", z.object({ ok: z.boolean() }));
    expect(actorHeader).toBeNull();
  });
});
