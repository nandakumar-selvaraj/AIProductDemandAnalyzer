import { HttpClient, HttpHeaders, HttpErrorResponse } from '@angular/common/http';
import { DestroyRef, inject, Injectable, signal } from '@angular/core';
import { Router } from '@angular/router';
import { catchError, finalize, Observable, of, shareReplay, tap } from 'rxjs';
import { environment } from '../../../environments/environment';

export interface AuthUser { id: string; email: string; role: 'admin' | 'viewer'; }
export interface BrowserSession { user: AuthUser; expires_at: string; csrf_token: string; }

@Injectable({ providedIn: 'root' })
export class AuthService {
  readonly enabled = environment.authEnabled;
  readonly user = signal<AuthUser | null>(null);
  readonly expiresAt = signal<string | null>(null);
  readonly logoutError = signal('');
  private readonly http = inject(HttpClient, { optional: true });
  private readonly router = inject(Router, { optional: true });
  private csrf: string | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private restoring: Observable<BrowserSession | null> | null = null;
  private readonly channel = typeof BroadcastChannel !== 'undefined'
    ? new BroadcastChannel('demand-session') : null;

  constructor() {
    const pagehide = () => { if (this.enabled) this.clear(); };
    const pageshow = (event: PageTransitionEvent) => {
      if (this.enabled && event.persisted) this.restore(true).subscribe((session) => {
        if (!session) this.unauthorized();
      });
    };
    if (typeof window !== 'undefined') {
      window.addEventListener('pagehide', pagehide);
      window.addEventListener('pageshow', pageshow);
    }
    if (this.channel) this.channel.onmessage = (event) => {
      if (event.data === 'logout') this.unauthorized();
    };
    inject(DestroyRef).onDestroy(() => {
      this.clear();
      this.channel?.close();
      if (typeof window !== 'undefined') {
        window.removeEventListener('pagehide', pagehide);
        window.removeEventListener('pageshow', pageshow);
      }
    });
  }

  csrfToken(): string | null { return this.csrf; }
  private save(session: BrowserSession): void {
    this.clear();
    const delay = Date.parse(session.expires_at) - Date.now();
    if (!Number.isFinite(delay) || delay <= 0) { this.unauthorized(); return; }
    this.csrf = session.csrf_token;
    this.user.set(session.user);
    this.expiresAt.set(session.expires_at);
    this.timer = setTimeout(() => this.unauthorized(), delay);
  }
  private clear(): void {
    if (this.timer !== null) clearTimeout(this.timer);
    this.timer = null;
    this.csrf = null;
    this.user.set(null);
    this.expiresAt.set(null);
  }
  restore(force = false): Observable<BrowserSession | null> {
    if (this.user() && Date.parse(this.expiresAt() ?? '') <= Date.now()) this.clear();
    if (!force && this.user()) return of({
      user: this.user()!, expires_at: this.expiresAt()!, csrf_token: this.csrf!,
    });
    if (!this.http) return of(null);
    if (!this.restoring) this.restoring = this.http.get<BrowserSession>(
      `${environment.apiBaseUrl}/auth/me`, { withCredentials: true },
    ).pipe(
      tap((session) => this.save(session)),
      catchError(() => { this.clear(); return of(null); }),
      finalize(() => { this.restoring = null; }),
      shareReplay({ bufferSize: 1, refCount: true }),
    );
    return this.restoring;
  }
  login(email: string, password: string): Observable<BrowserSession> {
    return this.http!.post<BrowserSession>(`${environment.apiBaseUrl}/auth/login`,
      { email, password }, { withCredentials: true,
        headers: new HttpHeaders({ 'X-Requested-With': 'AIProductDemandAnalyzer' }) },
    ).pipe(tap((session) => { this.save(session); this.logoutError.set(''); }));
  }
  logout(): void {
    this.logoutError.set('');
    this.http!.post<void>(`${environment.apiBaseUrl}/auth/logout`, {}, {
      withCredentials: true, headers: new HttpHeaders({ 'X-CSRF-Token': this.csrf ?? '' }),
    }).subscribe({
      next: () => { this.channel?.postMessage('logout'); this.unauthorized(); },
      error: (error: unknown) => {
        if (error instanceof HttpErrorResponse && error.status === 401) this.unauthorized();
        else if (typeof error === 'object' && error !== null && 'status' in error && error.status === 401)
          this.unauthorized();
        else this.logoutError.set('Could not confirm server logout. Please try again.');
      },
    });
  }
  unauthorized(): void {
    this.clear();
    void this.router?.navigateByUrl('/login', { replaceUrl: true });
  }
}
