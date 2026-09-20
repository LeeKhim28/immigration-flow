import { z } from "zod";

export const caseStatusSchema = z.enum([
  "DRAFT",
  "SUBMITTED",
  "IN_PROCESS",
  "ACTION_REQUIRED",
  "COMPLETED",
  "WITHDRAWN",
]);

export const demoSessionSchema = z.object({
  applicant_actor_id: z.string().uuid(),
  officer_actor_id: z.string().uuid(),
  case_id: z.string().uuid(),
  case_number: z.string().min(1),
});

export const namedReferenceSchema = z.object({
  id: z.string().uuid(),
  name: z.string().min(1),
  code: z.string().min(1),
});

export const caseDetailSchema = z.object({
  id: z.string().uuid(),
  case_number: z.string().min(1),
  applicant_profile_id: z.string().uuid(),
  status: caseStatusSchema,
  stage: z.string().min(1),
  synthetic: z.boolean(),
  institution: namedReferenceSchema,
  programme: namedReferenceSchema,
  nationality_code: z.string().min(2).max(3),
  passport_expires_at: z.iso.datetime(),
  rule_set_version: z.string().nullable(),
});

export const checklistSchema = z.object({
  rule_set_version: z.string(),
  requirements: z.array(z.object({
    requirement_code: z.string(),
    statement: z.string(),
    machine_handling: z.string(),
    status: z.string(),
  })),
});

export const evaluationHistorySchema = z.object({
  evaluations: z.array(z.object({
    id: z.string().uuid(),
    outcome: z.string(),
    trigger: z.string(),
    evaluated_at: z.iso.datetime(),
    supersedes_evaluation_id: z.string().uuid().nullable(),
    rule_set_version: z.string(),
    findings: z.array(z.object({
      id: z.string().uuid(), outcome: z.string(), code: z.string(), message: z.string(),
    })),
  })),
});

export const submissionSchema = z.object({
  id: z.string().uuid(), case_id: z.string().uuid(), status: caseStatusSchema,
  submitted_at: z.iso.datetime(), accepted_at: z.iso.datetime().nullable(),
});

export const caseSummarySchema = z.object({
  id: z.string().uuid(), case_number: z.string(), applicant_profile_id: z.string().uuid(),
  status: caseStatusSchema, stage: z.string(),
});
export const officerQueueSchema = z.array(caseSummarySchema);
export const timelineEventSchema = z.object({
  id: z.string().uuid(), event_type: z.string(), occurred_at: z.iso.datetime(),
});
export const officerCaseSchema = caseDetailSchema.extend({
  evaluations: evaluationHistorySchema.shape.evaluations,
  events: z.array(timelineEventSchema),
});

export type DemoSession = z.infer<typeof demoSessionSchema>;
export type CaseDetail = z.infer<typeof caseDetailSchema>;
