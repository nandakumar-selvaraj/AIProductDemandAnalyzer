import { inject } from '@angular/core';
import { CanActivateFn, Router } from '@angular/router';
import { map, of } from 'rxjs';
import { AuthService } from './services/auth.service';

export const authGuard: CanActivateFn = () => {
  const auth = inject(AuthService);
  const router = inject(Router);
  return !auth.enabled ? of(true) : auth.restore().pipe(
    map((session) => session ? true : router.createUrlTree(['/login'])),
  );
};
