import { Component, computed, signal } from '@angular/core';
import { NavigationEnd, Router, RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs';

@Component({ imports: [RouterOutlet, RouterLink, RouterLinkActive], selector: 'app-root', styleUrl: './app.scss', templateUrl: './app.html' })
export class App {
  protected readonly sidebarCollapsed = signal(false);
  protected readonly mobileMenuOpen = signal(false);
  private readonly currentUrl = signal('');
  protected readonly pageTitle = computed(() => this.navigation.find((item) => item.path === this.currentUrl())?.label ?? 'Dashboard');
  protected readonly navigation = [
    { label: 'Dashboard', path: '/dashboard', icon: '▦' },
    { label: 'Products', path: '/products', icon: '◇' },
    { label: 'Demand Analysis', path: '/demand-analysis', icon: '⌁' },
    { label: 'Forecasts', path: '/forecasts', icon: '↗' },
    { label: 'Reports', path: '/reports', icon: '▤' },
    { label: 'AI Assistant', path: '/ai-assistant', icon: '✳' },
  ];
  constructor(router: Router) {
    this.currentUrl.set(router.url || '/dashboard');
    router.events.pipe(filter((event): event is NavigationEnd => event instanceof NavigationEnd)).subscribe((event) => {
      this.currentUrl.set(event.urlAfterRedirects);
      this.mobileMenuOpen.set(false);
    });
  }
  protected toggleSidebar(): void {
    if (window.matchMedia('(max-width: 760px)').matches) this.mobileMenuOpen.update((open) => !open);
    else this.sidebarCollapsed.update((collapsed) => !collapsed);
  }
}