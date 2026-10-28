import { HttpErrorResponse, HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { catchError, throwError } from 'rxjs';
import { environment } from '../../environments/environment';
import { AuthService } from './services/auth.service';

export const authInterceptor: HttpInterceptorFn = (request, next) => {
  const auth = inject(AuthService);
  if (!request.url.startsWith(`${environment.apiBaseUrl}/`)) return next(request);
  let headers = request.headers;
  if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method) && auth.csrfToken()) {
    headers = headers.set('X-CSRF-Token', auth.csrfToken()!);
  }
  return next(request.clone({ headers, withCredentials: true })).pipe(catchError((error: unknown) => {
    if (auth.enabled && error instanceof HttpErrorResponse && error.status === 401
      && !request.url.includes('/auth/')) auth.unauthorized();
    return throwError(() => error);
  }));
};
