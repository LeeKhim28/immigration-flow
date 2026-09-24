import { apiRequest } from "../../api/client";
import { demoSessionSchema, type DemoSession } from "../../api/schemas";

export function createDemoSession(): Promise<DemoSession> {
  return apiRequest("/api/v1/demo/session", demoSessionSchema, { method: "POST" });
}

export function deleteDemoSession(): Promise<DemoSession> {
  return apiRequest("/api/v1/demo/session", demoSessionSchema, { method: "DELETE" });
}
