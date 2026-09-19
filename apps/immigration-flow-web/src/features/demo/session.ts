import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { demoSessionSchema, type DemoSession } from "../../api/schemas";
import { createDemoSession, deleteDemoSession } from "./api";

export const STORAGE_KEY = "immigration-flow.demo.v1";
export const demoSessionQueryKey = ["demo-session"] as const;

export function readDemoSession(): DemoSession | null {
  const saved = localStorage.getItem(STORAGE_KEY);
  if (!saved) return null;
  try {
    const parsed = demoSessionSchema.safeParse(JSON.parse(saved));
    if (parsed.success) return parsed.data;
  } catch {
    // Invalid browser state is cleared below.
  }
  clearDemoSession();
  return null;
}

export function writeDemoSession(session: DemoSession): void {
  const safeSession = demoSessionSchema.parse(session);
  localStorage.setItem(STORAGE_KEY, JSON.stringify(safeSession));
}

export function clearDemoSession(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function useDemoSession() {
  const saved = readDemoSession();
  return useQuery({
    queryKey: demoSessionQueryKey,
    queryFn: async () => {
      const session = await createDemoSession();
      writeDemoSession(session);
      return session;
    },
    initialData: saved ?? undefined,
  });
}

export function useResetDemoSession() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: async () => {
      await deleteDemoSession();
      clearDemoSession();
      return createDemoSession();
    },
    onSuccess: (session) => {
      writeDemoSession(session);
      queryClient.setQueryData(demoSessionQueryKey, session);
    },
  });
}
