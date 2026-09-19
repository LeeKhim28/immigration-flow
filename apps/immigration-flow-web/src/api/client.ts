import type { ZodType } from "zod";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly detail: string,
  ) {
    super(detail);
    this.name = "ApiError";
  }
}

export class DataIntegrityError extends Error {
  constructor() {
    super("The service returned data that ImmigrationFlow could not verify.");
    this.name = "DataIntegrityError";
  }
}

export type ApiRequestOptions = RequestInit & { actorId?: string };

export async function apiRequest<T>(
  path: string,
  schema: ZodType<T>,
  options: ApiRequestOptions = {},
): Promise<T> {
  const { actorId, headers: suppliedHeaders, ...requestOptions } = options;
  const headers = new Headers(suppliedHeaders);
  if (actorId) headers.set("X-Actor-Id", actorId);
  if (requestOptions.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const url = new URL(path, window.location.origin);
  const response = await fetch(url, { ...requestOptions, headers });
  if (!response.ok) {
    let detail = "The service could not complete this request.";
    try {
      const payload: unknown = await response.json();
      if (
        typeof payload === "object" &&
        payload !== null &&
        "detail" in payload &&
        typeof payload.detail === "string"
      ) {
        detail = payload.detail;
      }
    } catch {
      // Keep the generic message for non-JSON errors.
    }
    throw new ApiError(response.status, detail);
  }
  if (response.status === 204) return schema.parse(undefined);
  try {
    return schema.parse(await response.json());
  } catch {
    throw new DataIntegrityError();
  }
}
