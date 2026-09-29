import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiRequest } from "../../api/client";
import {
  caseDetailSchema,
  checklistSchema,
  evaluationHistorySchema,
  submissionSchema,
} from "../../api/schemas";

export const applicantKeys = {
  detail: (caseId: string) => ["applicant", "case", caseId] as const,
  checklist: (caseId: string) => ["applicant", "case", caseId, "checklist"] as const,
  evaluation: (caseId: string) => ["applicant", "case", caseId, "evaluation"] as const,
};

export function useApplicantCase(caseId: string, actorId: string) {
  return useQuery({
    queryKey: applicantKeys.detail(caseId),
    queryFn: () => apiRequest(`/api/v1/applicant/cases/${caseId}`, caseDetailSchema, { actorId }),
  });
}

export function useChecklist(caseId: string, actorId: string) {
  return useQuery({
    queryKey: applicantKeys.checklist(caseId),
    queryFn: () => apiRequest(`/api/v1/applicant/cases/${caseId}/checklist`, checklistSchema, { actorId }),
  });
}

export function useEvaluations(caseId: string, actorId: string) {
  return useQuery({
    queryKey: applicantKeys.evaluation(caseId),
    queryFn: () => apiRequest(`/api/v1/applicant/cases/${caseId}/evaluation`, evaluationHistorySchema, { actorId }),
  });
}

export function useSubmitCase(caseId: string, actorId: string) {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => apiRequest(`/api/v1/applicant/cases/${caseId}/submit`, submissionSchema, {
      actorId, method: "POST", body: JSON.stringify({ channel: "ONLINE_PORTAL" }),
    }),
    onSettled: async () => {
      await client.invalidateQueries({ queryKey: ["applicant", "case", caseId] });
    },
  });
}
