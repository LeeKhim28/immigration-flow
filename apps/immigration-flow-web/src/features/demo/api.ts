import { z } from "zod";

import { apiRequest } from "../../api/client";
import { demoSessionSchema, type DemoSession } from "../../api/schemas";

export function createDemoSession(): Promise<DemoSession> {
  return apiRequest("/api/v1/demo/session", demoSessionSchema, { method: "POST" });
}

export function deleteDemoSession(): Promise<void> {
  return apiRequest("/api/v1/demo/session", z.undefined(), { method: "DELETE" });
}
