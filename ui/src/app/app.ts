import { DOCUMENT } from '@angular/common';
import { CdkTrapFocus } from '@angular/cdk/a11y';
import {
  afterNextRender,
  Component,
  computed,
  DestroyRef,
  ElementRef,
  inject,
  Injector,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';
import { AuthService } from './core/services/auth.service';
import { DemoService } from './core/services/demo.service';

@Component({
  imports: [CdkTrapFocus, RouterOutlet, RouterLink, RouterLinkActive],
  selector: 'app-root',
  styleUrl: './app.scss',
  templateUrl: './app.html',
})
export class App {
  protected readonly auth = inject(AuthService);
  protected readonly loginPage = computed(() => this.currentUrl() === '/login');
  protected readonly publicDemo = computed(() => this.currentUrl().startsWith('/demo'));
  protected readonly demo = inject(DemoService);
  private readonly router = inject(Router);
  private readonly document = inject(DOCUMENT);
  private readonly destroyRef = inject(DestroyRef);
  private readonly injector = inject(Injector);
  private readonly navigationToggle = viewChild<ElementRef<HTMLButtonElement>>('navigationToggle');
  protected readonly sidebarCollapsed = signal(false);
  protected readonly mobileMenuOpen = signal(false);
  protected readonly isMobile = signal(false);
  protected readonly navigationVisible = computed(() =>
    this.isMobile() ? this.mobileMenuOpen() : !this.sidebarCollapsed(),
  );
  private readonly currentUrl = signal('');
  protected readonly pageTitle = computed(
    () => this.navigation.find((item) => item.path === (this.currentUrl().replace(/^\/demo(?=\/|$)/, '') || '/dashboard'))?.label ?? 'Dashboard',
  );
  protected readonly navigation = [
    { label: 'Dashboard', path: '/dashboard', icon: '▦' },
    { label: 'Products', path: '/products', icon: '◇' },
    { label: 'Demand Analysis', path: '/demand-analysis', icon: '⌁' },
    { label: 'Forecasts', path: '/forecasts', icon: '↗' },
    { label: 'Reports', path: '/reports', icon: '▤' },
    { label: 'AI Assistant', path: '/ai-assistant', icon: '✳' },
  ];

  constructor() {
    const window = this.document.defaultView;
    if (typeof window?.matchMedia === 'function') {
      const media = window.matchMedia('(max-width: 760px)');
      this.isMobile.set(media.matches);
      const update = (event: MediaQueryListEvent) => {
        this.isMobile.set(event.matches);
        if (!event.matches) this.mobileMenuOpen.set(false);
      };
      media.addEventListener('change', update);
      this.destroyRef.onDestroy(() => media.removeEventListener('change', update));
    }
    this.currentUrl.set(this.router.url.split(/[?#]/)[0] || '/dashboard');
    this.router.events
      .pipe(
        filter((event): event is NavigationEnd => event instanceof NavigationEnd),
        takeUntilDestroyed(),
      )
      .subscribe((event) => {
        this.currentUrl.set(event.urlAfterRedirects.split(/[?#]/)[0]);
        this.closeNavigation();
      });
  }

  protected navPath(path: string): string {
    return this.publicDemo() ? (path === '/dashboard' ? '/demo' : '/demo' + path) : path;
  }

  protected toggleSidebar(): void {
    if (this.isMobile()) {
      if (this.mobileMenuOpen()) this.closeNavigation();
      else this.mobileMenuOpen.set(true);
    } else {
      this.sidebarCollapsed.update((collapsed) => !collapsed);
    }
  }

  protected closeNavigation(): void {
    if (!this.mobileMenuOpen()) return;
    this.mobileMenuOpen.set(false);
    afterNextRender(() => this.navigationToggle()?.nativeElement.focus(), {
      injector: this.injector,
    });
  }
}
