import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { catchError, throwError } from 'rxjs';

export class ApiRequestError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly code: string,
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

function record(value: unknown): Record<string, unknown> | undefined {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : undefined;
}

function text(value: unknown): string | undefined {
  return typeof value === 'string' && value.trim() ? value.trim() : undefined;
}

function validationMessage(value: unknown): string | undefined {
  if (!Array.isArray(value)) return undefined;
  const messages = value.flatMap((issue: unknown) => {
    const details = record(issue);
    const message = text(details?.['msg']) ?? text(details?.['message']) ?? text(issue);
    if (!message) return [];
    const location = details?.['loc'];
    const field = Array.isArray(location)
      ? location
          .filter((part: unknown) => typeof part === 'string' || typeof part === 'number')
          .join('.')
      : '';
    return [field ? `${field}: ${message}` : message];
  });
  return messages.length ? [...new Set(messages)].join('; ') : undefined;
}

function messageFrom(value: unknown): string | undefined {
  const details = record(value);
  const message = text(value) ?? text(details?.['message']) ?? text(details?.['msg']);
  const validation = validationMessage(value) ?? validationMessage(details?.['details']);
  return message && validation ? `${message}: ${validation}` : (message ?? validation);
}

export const apiErrorInterceptor: HttpInterceptorFn = (request, next) =>
  next(request).pipe(
    catchError((error: unknown) => {
      // Preserve non-HTTP failures rather than hiding programming errors behind an API message.
      if (!(error instanceof HttpErrorResponse)) return throwError(() => error);
      if (error.status === 0) {
        return throwError(
          () =>
            new ApiRequestError(
              'The API could not be reached. Check that the backend is running and the API URL is correct.',
              0,
              'network_error',
            ),
        );
      }
      if (error.status >= 200 && error.status < 300) {
        return throwError(
          () =>
            new ApiRequestError(
              'The API returned an unreadable response. Please try again.',
              error.status,
              'invalid_response',
            ),
        );
      }

      const payload = record(error.error);
      const customError = payload?.['error'];
      const detail = payload?.['detail'];
      const message =
        messageFrom(customError) ??
        messageFrom(detail) ??
        text(payload?.['message']) ??
        `The request failed with status ${error.status}.`;
      const code =
        text(record(customError)?.['code']) ??
        text(record(detail)?.['code']) ??
        (error.status === 422 ? 'validation_error' : 'request_failed');
      return throwError(() => new ApiRequestError(message, error.status, code));
    }),
  );
