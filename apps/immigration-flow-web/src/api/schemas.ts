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

export type DemoSession = z.infer<typeof demoSessionSchema>;
export type CaseDetail = z.infer<typeof caseDetailSchema>;
