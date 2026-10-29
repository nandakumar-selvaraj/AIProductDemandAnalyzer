import { HttpEventType, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { signal } from '@angular/core';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { environment } from '../../../environments/environment';
import { apiErrorInterceptor } from '../../core/api-error.interceptor';
import { authInterceptor } from '../../core/auth.interceptor';
import { AuthService, AuthUser } from '../../core/services/auth.service';
import { DataManagementPage } from './data-management.page';

describe('Admin CSV uploads', () => {
  let fixture: ComponentFixture<DataManagementPage>;
  let http: HttpTestingController;
  const user = signal<AuthUser | null>(null);
  const unauthorized = vi.fn(() => user.set(null));
  const base = `${environment.apiBaseUrl}/ingestion`;
  const summary = { records_read: 3, inserted: 1, updated: 1, rejected: 1, skipped: 0,
    validation_only: false, issues: [{ row: 4, reason: 'Invalid date' }] };
  beforeEach(() => {
    user.set({ id: 'synthetic', email: 'admin@example.invalid', role: 'admin' });
    unauthorized.mockClear();
    TestBed.configureTestingModule({
      providers: [provideRouter([]), provideHttpClient(withInterceptors([apiErrorInterceptor, authInterceptor])),
        provideHttpClientTesting(), { provide: AuthService, useValue: {
          enabled: true, user, csrfToken: () => 'synthetic-csrf', unauthorized,
        } }],
    });
    fixture = TestBed.createComponent(DataManagementPage);
    http = TestBed.inject(HttpTestingController);
    http.expectOne(`${base}/config`).flush({ max_upload_bytes: 1024 });
    fixture.detectChanges();
  });
  afterEach(() => http.verify());

  function select(name = 'sales.csv', content = 'date,store,item,sales\n2013-01-01,1,1,10\n') {
    const input = fixture.nativeElement.querySelector('input');
    Object.defineProperty(input, 'files', { value: [new File([content], name)], configurable: true });
    input.dispatchEvent(new Event('change'));
    fixture.detectChanges();
  }
  function submit() {
    fixture.nativeElement.querySelector('form').dispatchEvent(new Event('submit', { cancelable: true }));
    fixture.detectChanges();
  }

  it('selects a CSV and sends FormData with cookie/CSRF, without setting multipart content type', () => {
    select(); submit();
    const req = http.expectOne(`${base}/sales`);
    expect(req.request.body).toBeInstanceOf(FormData);
    expect(req.request.withCredentials).toBe(true);
    expect(req.request.headers.get('X-CSRF-Token')).toBe('synthetic-csrf');
    expect(req.request.headers.has('Content-Type')).toBe(false);
    req.flush(summary); fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Upload completed');
    expect(fixture.nativeElement.textContent).toContain('Row 4: Invalid date');
    expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
  });

  it.each([
    ['sales.txt', 'abc', 'Select a .csv'], ['sales.csv', '', 'empty'],
    ['sales.csv', 'x'.repeat(1025), 'server upload limit'],
  ])('rejects invalid file %s', (name, content, message) => {
    select(name, content); submit();
    expect(fixture.nativeElement.textContent).toContain(message);
    http.expectNone(`${base}/sales`);
  });

  it('shows progress when the transport supports it and guards double submission', () => {
    select(); submit(); submit();
    const req = http.expectOne(`${base}/sales`);
    expect(req.request.reportProgress).toBe(true);
    req.event({ type: HttpEventType.UploadProgress, loaded: 50, total: 100 });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('progress').value).toBe(50);
    expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
    req.flush(summary);
  });

  it('shows indeterminate progress until upload progress is available', () => {
    select(); submit();
    expect(fixture.nativeElement.querySelector('progress').hasAttribute('value')).toBe(false);
    http.expectOne(`${base}/sales`).flush(summary);
  });

  it('shows safe validation errors and permits a deliberate retry', () => {
    select(); submit();
    http.expectOne(`${base}/sales`).flush({ error: { code: 'invalid_csv', message: 'Missing sales column' } },
      { status: 422, statusText: 'Invalid CSV' });
    fixture.detectChanges();
    expect(fixture.nativeElement.textContent).toContain('Missing sales column');
    expect(fixture.nativeElement.querySelector('button').disabled).toBe(false);
  });

  it('redirects on expiry during upload using the existing auth interceptor', () => {
    select(); submit();
    http.expectOne(`${base}/sales`).flush({}, { status: 401, statusText: 'Expired' });
    fixture.detectChanges();
    expect(unauthorized).toHaveBeenCalledOnce();
    expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
  });

  it('cancels the pending request and clears results when logout clears the user', () => {
    select(); submit();
    const req = http.expectOne(`${base}/sales`);
    user.set(null); fixture.detectChanges();
    expect(req.cancelled).toBe(true);
    expect(fixture.nativeElement.querySelector('button').disabled).toBe(true);
  });

  it('cancels waiting when leaving the page', () => {
    select(); submit();
    const req = http.expectOne(`${base}/sales`);
    fixture.destroy();
    expect(req.cancelled).toBe(true);
  });

  it('does not submit for a viewer even if the component is instantiated directly', () => {
    select();
    user.set({ ...user()!, role: 'viewer' }); fixture.detectChanges();
    submit(); http.expectNone(`${base}/sales`);
  });
});
