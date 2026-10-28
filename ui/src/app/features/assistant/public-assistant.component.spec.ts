import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { DemoConfig, DemoService } from '../../core/services/demo.service';
import { environment } from '../../../environments/environment';
import { PublicAssistantComponent } from './public-assistant.component';

const config: DemoConfig = {
  enabled: true, label: 'Historical synthetic demo data', assistant_enabled: true,
  questions: [{ id: 'forecast', label: 'Explain the latest forecast.' }],
};

describe('Public assistant', () => {
  function setup(enabled = true) {
    TestBed.configureTestingModule({
      imports: [PublicAssistantComponent],
      providers: [provideHttpClient(), provideHttpClientTesting(), {
        provide: DemoService,
        useValue: { readOnly: true, config: signal({ ...config, assistant_enabled: enabled }) },
      }],
    });
    const fixture = TestBed.createComponent(PublicAssistantComponent);
    fixture.detectChanges();
    return { fixture, http: TestBed.inject(HttpTestingController) };
  }

  it('sends only an allowlisted question id without credentials or arbitrary text', () => {
    const { fixture, http } = setup();
    expect(fixture.nativeElement.querySelector('textarea')).toBeNull();
    fixture.nativeElement.querySelector('button').click();
    const request = http.expectOne(`${environment.apiBaseUrl}/demo/assistant`);
    expect(request.request.body).toEqual({ question_id: 'forecast' });
    expect(request.request.headers.has('Authorization')).toBe(false);
    request.flush({}, { status: 429, statusText: 'Too Many Requests' });
    fixture.detectChanges();
    expect(fixture.nativeElement.querySelector('[role="alert"]').textContent).toContain('allowance');
    http.verify();
  });

  it('does not offer questions while AI is disabled', () => {
    const { fixture, http } = setup(false);
    expect(fixture.nativeElement.textContent).toContain('currently disabled');
    expect(fixture.nativeElement.querySelector('button')).toBeNull();
    http.expectNone(`${environment.apiBaseUrl}/demo/assistant`);
    http.verify();
  });
});
