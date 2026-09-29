import { beforeEach, describe, expect, it } from "vitest";

import { STORAGE_KEY, clearDemoSession, readDemoSession, writeDemoSession } from "./session";

const demo = {
  applicant_actor_id: "5f73f646-da4c-466d-a842-d59167d508ae",
  officer_actor_id: "71e25d11-7ec4-4120-a018-d611f3b5040b",
  case_id: "87490004-a1bc-45d1-8aa7-0ca1f5147ab4",
  case_number: "IF-DEMO-STUDENT-PASS-001",
};

describe("demo session storage", () => {
  beforeEach(() => localStorage.clear());

  it("stores only the validated synthetic identifiers under one reserved key", () => {
    writeDemoSession(demo);

    expect(Object.keys(localStorage)).toEqual([STORAGE_KEY]);
    expect(readDemoSession()).toEqual(demo);
  });

  it("clears malformed saved data instead of returning it", () => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({ case_id: "not-a-uuid" }));

    expect(readDemoSession()).toBeNull();
    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("clears the reserved session without touching another key", () => {
    writeDemoSession(demo);
    localStorage.setItem("another-app", "keep");

    clearDemoSession();

    expect(localStorage.getItem(STORAGE_KEY)).toBeNull();
    expect(localStorage.getItem("another-app")).toBe("keep");
  });
});
