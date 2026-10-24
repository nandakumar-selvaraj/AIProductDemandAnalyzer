import { TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { App } from './app';

describe('App', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({ imports: [App], providers: [provideRouter([])] }).compileComponents();
  });
  it('creates the application shell', () => {
    expect(TestBed.createComponent(App).componentInstance).toBeTruthy();
  });
  it('exposes all workspace sections in the primary navigation', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    const compiled = fixture.nativeElement as HTMLElement;
    const labels = Array.from(compiled.querySelectorAll('nav a')).map((link) => link.textContent?.trim());
    expect(labels).toEqual(['▦Dashboard', '◇Products', '⌁Demand Analysis', '↗Forecasts', '▤Reports', '✳AI Assistant']);
  });
  it('shows the application name', async () => {
    const fixture = TestBed.createComponent(App);
    fixture.detectChanges();
    await fixture.whenStable();
    expect((fixture.nativeElement as HTMLElement).querySelector('.brand')?.getAttribute('aria-label')).toContain('AI Product Demand Analyzer');
  });
});