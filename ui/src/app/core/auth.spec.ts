import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { Component } from '@angular/core';
import { TestBed } from '@angular/core/testing';
import { provideRouter, Router, GuardResult } from '@angular/router';
import { firstValueFrom, Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import { adminGuard, authGuard } from './auth.guard';
import { authInterceptor } from './auth.interceptor';
import { AuthService, BrowserSession } from './services/auth.service';
import { DemoService } from './services/demo.service';
import { LoginPage } from '../features/auth/login.page';

@Component({ template: '<h1>Dashboard</h1>' })
class Dashboard {}

const base = environment.apiBaseUrl;
function session(): BrowserSession {
  return { user: { id: 'synthetic-user', email: 'viewer@example.invalid', role: 'viewer' },
    expires_at: new Date(Date.now() + 1800000).toISOString(), csrf_token: 'synthetic-csrf' };
}

describe('Browser authentication', () => {
  let auth: AuthService;
  let http: HttpTestingController;
  let router: Router;
  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [provideHttpClient(withInterceptors([authInterceptor])), provideHttpClientTesting(),
        provideRouter([{ path: 'login', component: LoginPage },
          { path: 'dashboard', component: Dashboard, canActivate: [authGuard] }])],
    });
    auth = TestBed.inject(AuthService);
    Object.defineProperty(auth, 'enabled', { value: true });
    http = TestBed.inject(HttpTestingController);
    router = TestBed.inject(Router);
  });
  afterEach(() => { http.verify(); vi.useRealTimers(); });

  function login() {
    auth.login('viewer@example.invalid', 'synthetic-password').subscribe();
    const req = http.expectOne(`${base}/auth/login`);
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.headers.get('X-Requested-With')).toBe('AIProductDemandAnalyzer');
    req.flush(session());
  }

  it('keeps only user, CSRF and expiry in memory after login, with no browser storage', () => {
    const local = vi.spyOn(Storage.prototype, 'setItem');
    login();
    expect(auth.user()?.role).toBe('viewer');
    expect(auth.csrfToken()).toBe('synthetic-csrf');
    expect(auth.expiresAt()).toBeTruthy();
    expect(local).not.toHaveBeenCalled();
    local.mockRestore();
  });

  it('restores a valid session from me after browser refresh', async () => {
    const result = firstValueFrom(auth.restore());
    http.expectOne(`${base}/auth/me`).flush(session());
    expect((await result)?.user.role).toBe('viewer');
    expect(auth.user()?.role).toBe('viewer');
  });

  it('redirects unauthenticated protected routes to login', async () => {
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, {} as never));
    const resolved = firstValueFrom(result as Observable<GuardResult>);
    http.expectOne(`${base}/auth/me`).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(String(await resolved)).toBe('/login');
  });

  it('allows protected routes with a restored session', async () => {
    login();
    const result = TestBed.runInInjectionContext(() => authGuard({} as never, {} as never));
    expect(await firstValueFrom(result as Observable<GuardResult>)).toBe(true);
  });

  it('restricts the management route to admins and redirects anonymous users to login', async () => {
    const result = TestBed.runInInjectionContext(() => adminGuard({} as never, {} as never));
    const resolved = firstValueFrom(result as Observable<GuardResult>);
    http.expectOne(`${base}/auth/me`).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(String(await resolved)).toBe('/login');
    login();
    const viewer = TestBed.runInInjectionContext(() => adminGuard({} as never, {} as never));
    expect(String(await firstValueFrom(viewer as Observable<GuardResult>))).toBe('/dashboard');
    auth.user.set({ ...auth.user()!, role: 'admin' });
    const admin = TestBed.runInInjectionContext(() => adminGuard({} as never, {} as never));
    expect(await firstValueFrom(admin as Observable<GuardResult>)).toBe(true);
  });

  it('expires proactively, clears CSRF/timer state and redirects', () => {
    vi.useFakeTimers();
    const navigation = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    login();
    vi.advanceTimersByTime(1800001);
    expect(auth.user()).toBeNull();
    expect(auth.csrfToken()).toBeNull();
    expect(auth.expiresAt()).toBeNull();
    expect(navigation).toHaveBeenCalledWith('/login', { replaceUrl: true });
  });

  it('replaces the old expiration timer when a new session is installed', () => {
    vi.useFakeTimers();
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    login();
    vi.advanceTimersByTime(1000);
    login();
    vi.advanceTimersByTime(1799001);
    expect(auth.user()).not.toBeNull();
    vi.advanceTimersByTime(1000);
    expect(auth.user()).toBeNull();
  });

  it('sends session-bound CSRF on mutations and clears state only after server logout', () => {
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    login();
    auth.logout();
    const req = http.expectOne(`${base}/auth/logout`);
    expect(req.request.headers.get('X-CSRF-Token')).toBe('synthetic-csrf');
    expect(auth.user()).not.toBeNull();
    req.flush(null, { status: 204, statusText: 'No Content' });
    expect(auth.user()).toBeNull();
    expect(auth.csrfToken()).toBeNull();
  });

  it('does not claim successful logout when the server is unreachable', () => {
    login();
    auth.logout();
    http.expectOne(`${base}/auth/logout`).flush({}, { status: 503, statusText: 'Unavailable' });
    expect(auth.user()).not.toBeNull();
    expect(auth.logoutError()).toContain('Could not confirm');
  });

  it('cleans up on protected API 401 but preserves the session on 403', () => {
    vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    login();
    const client = TestBed.inject(HttpClient);
    client.get(`${base}/products`).subscribe({ error: () => undefined });
    http.expectOne(`${base}/products`).flush({}, { status: 403, statusText: 'Forbidden' });
    expect(auth.user()).not.toBeNull();
    client.get(`${base}/products`).subscribe({ error: () => undefined });
    http.expectOne(`${base}/products`).flush({}, { status: 401, statusText: 'Unauthorized' });
    expect(auth.user()).toBeNull();
  });

  it('does not send CSRF or credentials to unrelated origins', () => {
    login();
    TestBed.inject(HttpClient).post('https://unrelated.invalid/api', {}).subscribe();
    const req = http.expectOne('https://unrelated.invalid/api');
    expect(req.request.headers.has('X-CSRF-Token')).toBe(false);
    expect(req.request.withCredentials).toBe(false);
    req.flush({});
  });

  it('allows writes only for admins, while authenticated viewers keep full analytical UI', () => {
    login();
    const demo = TestBed.inject(DemoService);
    expect(demo.canWrite).toBe(false);
    expect(demo.readOnly).toBe(false);
    auth.user.set({ ...auth.user()!, role: 'admin' });
    expect(demo.canWrite).toBe(true);
  });

  it('login form redirects to dashboard on success and clears the password', async () => {
    const navigation = vi.spyOn(router, 'navigateByUrl').mockResolvedValue(true);
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    const inputs = fixture.nativeElement.querySelectorAll('input');
    inputs[0].value = 'viewer@example.invalid'; inputs[0].dispatchEvent(new Event('input'));
    inputs[1].value = 'synthetic-password'; inputs[1].dispatchEvent(new Event('input'));
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    http.expectOne(`${base}/auth/login`).flush(session());
    fixture.detectChanges();
    await fixture.whenStable();
    expect(inputs[1].value).toBe('');
    expect(navigation).toHaveBeenCalledWith('/dashboard', { replaceUrl: true });
  });

  it('shows generic login failure without echoing the password', () => {
    const fixture = TestBed.createComponent(LoginPage);
    fixture.detectChanges();
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit'));
    http.expectOne(`${base}/auth/login`).flush({}, { status: 401, statusText: 'Unauthorized' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('Sign-in failed');
    expect(auth.user()).toBeNull();
  });
});
