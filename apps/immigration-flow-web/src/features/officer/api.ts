import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../../api/client";
import { caseSummarySchema, officerCaseSchema, officerQueueSchema } from "../../api/schemas";

export function useOfficerQueue(actorId: string, status: "SUBMITTED" | "IN_PROCESS") {
  return useQuery({
    queryKey: ["officer", "cases", status],
    queryFn: () => apiRequest(`/api/v1/officer/cases?status=${status}`, officerQueueSchema, { actorId }),
  });
}

export function useOfficerCase(caseId: string, actorId: string) {
  return useQuery({
    queryKey: ["officer", "case", caseId],
    queryFn: () => apiRequest(`/api/v1/officer/cases/${caseId}`, officerCaseSchema, { actorId }),
  });
}

export function useStartProcessing(caseId: string, actorId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest(`/api/v1/officer/cases/${caseId}/start-processing`, caseSummarySchema, { actorId, method: "POST" }),
    onSettled: async () => {
      await Promise.all([
        client.invalidateQueries({ queryKey: ["officer", "cases"] }),
        client.invalidateQueries({ queryKey: ["officer", "case", caseId] }),
      ]);
    },
  });
}
