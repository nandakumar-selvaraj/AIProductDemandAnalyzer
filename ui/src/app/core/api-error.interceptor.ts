import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';
interface ApiErrorPayload { code?: string; message?: string; }
export class ApiRequestError extends Error {
  constructor(message: string, readonly status: number, readonly code: string) { super(message); this.name = 'ApiRequestError'; }
}
export const apiErrorInterceptor: HttpInterceptorFn = (request, next) => next(request).pipe(catchError((error: unknown) => {
  if (!(error instanceof HttpErrorResponse)) return throwError(() => error);
  const payload = error.error as { error?: ApiErrorPayload } | null;
  const apiError = payload?.error;
  const message = apiError?.message ?? (error.status === 0 ? 'The API could not be reached. Check that the backend is running and the API URL is correct.' : `The request failed with status ${error.status}.`);
  return throwError(() => new ApiRequestError(message, error.status, apiError?.code ?? 'request_failed'));
}));