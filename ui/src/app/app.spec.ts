import { Component } from '@angular/core';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { By } from '@angular/platform-browser';
import { provideRouter, Router } from '@angular/router';
import { App } from './app';
import { AuthService } from './core/services/auth.service';

@Component({ template: '<p>Page content</p>' })
class RoutePage {}

describe('App navigation', () => {
  let fixture: ComponentFixture<App>;
  let root: HTMLElement;
  let media: MediaQueryList;

  function createApp(mobile = false): void {
    Object.defineProperty(media, 'matches', { value: mobile, configurable: true });
    fixture = TestBed.createComponent(App);
    root = fixture.nativeElement as HTMLElement;
    fixture.detectChanges();
  }

  function toggle(): HTMLButtonElement {
    const button = root.querySelector<HTMLButtonElement>('.menu-toggle')!;
    button.focus();
    button.click();
    fixture.detectChanges();
    return button;
  }

  beforeEach(async () => {
    media = {
      matches: false,
      media: '(max-width: 760px)',
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(() => true),
    };
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => media),
    );
    await TestBed.configureTestingModule({
      imports: [App],
      providers: [
        provideRouter([
          { path: 'dashboard', component: RoutePage },
          { path: 'products', component: RoutePage },
        ]),
      ],
    }).compileComponents();
  });
  afterEach(() => {
    fixture?.destroy();
    vi.unstubAllGlobals();
  });

  it('shows Management navigation only for admin users', () => {
    const auth = TestBed.inject(AuthService);
    Object.defineProperty(auth, 'enabled', { value: true });
    auth.user.set({ id: 'synthetic', email: 'viewer@example.invalid', role: 'viewer' });
    createApp();
    expect(root.querySelector('[aria-label="Management"]')).toBeNull();
    auth.user.set({ ...auth.user()!, role: 'admin' }); fixture.detectChanges();
    expect(root.querySelector('[aria-label="Management"]')?.textContent).toContain('Data Management');
    auth.user.set(null); fixture.detectChanges();
    expect(root.querySelector('[aria-label="Management"]')).toBeNull();
  });

  it('shows the application name, skip link, and all workspace sections', () => {
    createApp();
    expect(root.querySelector('.brand')?.getAttribute('aria-label')).toContain(
      'AI Product Demand Analyzer',
    );
    expect(root.querySelector('.skip-link')?.getAttribute('href')).toBe('#main-content');
    expect(
      Array.from(root.querySelectorAll('nav[aria-label="Workspace"] a'), (link) => link.getAttribute('aria-label')),
    ).toEqual(['Dashboard', 'Products', 'Demand Analysis', 'Forecasts', 'Reports', 'AI Assistant']);
  });

  it('announces desktop collapse and removes collapsed navigation from keyboard access', () => {
    createApp();
    expect(root.querySelector('.menu-toggle')?.getAttribute('aria-expanded')).toBe('true');
    toggle();
    expect(root.querySelector('.menu-toggle')?.getAttribute('aria-expanded')).toBe('false');
    expect(root.querySelector<HTMLElement>('.sidebar')?.inert).toBe(true);
    toggle();
    expect(root.querySelector<HTMLElement>('.sidebar')?.inert).toBe(false);
  });

  it('initially hides mobile navigation and reports the correct collapsed state', () => {
    createApp(true);
    expect(root.querySelector('.menu-toggle')?.getAttribute('aria-expanded')).toBe('false');
    expect(root.querySelector<HTMLElement>('.sidebar')?.inert).toBe(true);
    expect(root.querySelector('.sidebar')?.getAttribute('aria-hidden')).toBe('true');
    expect(root.querySelector('.navigation-backdrop')).toBeNull();
  });

  it('opens a focus-trapped mobile dialog and makes background content inert', () => {
    createApp(true);
    toggle();
    expect(root.querySelector('.menu-toggle')?.getAttribute('aria-expanded')).toBe('true');
    expect(root.querySelector('.sidebar')?.getAttribute('role')).toBe('dialog');
    expect(root.querySelector('.sidebar')?.getAttribute('aria-modal')).toBe('true');
    expect(root.querySelector<HTMLElement>('.main-shell')?.inert).toBe(true);
    const trap = fixture.debugElement.query(By.directive(CdkTrapFocus)).injector.get(CdkTrapFocus);
    expect(trap.enabled).toBe(true);
    expect(trap.autoCapture).toBe(true);
  });

  it('closes on Escape and restores focus to the menu toggle', async () => {
    createApp(true);
    const button = toggle();
    await fixture.whenStable();
    root.querySelector<HTMLButtonElement>('.sidebar-close')!.focus();
    root
      .querySelector('.sidebar')!
      .dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', bubbles: true }));
    fixture.detectChanges();
    await fixture.whenStable();
    expect(root.querySelector('.menu-toggle')?.getAttribute('aria-expanded')).toBe('false');
    expect(root.querySelector<HTMLElement>('.main-shell')?.inert).toBe(false);
    expect(document.activeElement).toBe(button);
  });

  it.each(['.sidebar-close', '.navigation-backdrop'])('closes through %s', (selector) => {
    createApp(true);
    toggle();
    root.querySelector<HTMLButtonElement>(selector)!.click();
    fixture.detectChanges();
    expect(root.querySelector('.navigation-backdrop')).toBeNull();
    expect(root.querySelector('.menu-toggle')?.getAttribute('aria-expanded')).toBe('false');
  });

  it('closes after navigation and marks the active route for assistive technology', async () => {
    createApp(true);
    toggle();
    await TestBed.inject(Router).navigateByUrl('/products?search=tea');
    fixture.detectChanges();
    expect(root.querySelector('.navigation-backdrop')).toBeNull();
    expect(root.querySelector('.topbar-context')?.textContent).toContain('Products');
    expect(root.querySelector('a[href="/products"]')?.getAttribute('aria-current')).toBe('page');
  });

  it('responds to viewport changes and removes its media listener on destruction', () => {
    createApp(true);
    toggle();
    const listener = vi.mocked(media.addEventListener).mock.calls[0][1] as (
      event: MediaQueryListEvent,
    ) => void;
    listener({ matches: false } as MediaQueryListEvent);
    fixture.detectChanges();
    expect(root.querySelector('.navigation-backdrop')).toBeNull();
    expect(root.querySelector('.menu-toggle')?.getAttribute('aria-expanded')).toBe('true');
    fixture.destroy();
    expect(media.removeEventListener).toHaveBeenCalledWith('change', listener);
  });
});
