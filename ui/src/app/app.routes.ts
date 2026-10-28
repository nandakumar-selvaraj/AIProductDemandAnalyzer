import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';

export const routes: Routes = [
  { path: 'login', loadComponent: () => import('./features/auth/login.page').then((m) => m.LoginPage) },
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    canActivate: [authGuard],
    title: 'Dashboard',
    loadComponent: () => import('./features/dashboard/dashboard.page').then((m) => m.DashboardPage),
  },
  {
    path: 'products',
    canActivate: [authGuard],
    title: 'Products',
    loadComponent: () => import('./features/products/products.page').then((m) => m.ProductsPage),
  },
  {
    path: 'demand-analysis',
    canActivate: [authGuard],
    title: 'Demand Analysis',
    loadComponent: () =>
      import('./features/demand-analysis/demand-analysis.page').then((m) => m.DemandAnalysisPage),
  },
  {
    path: 'forecasts',
    canActivate: [authGuard],
    title: 'Forecasts',
    loadComponent: () => import('./features/forecasts/forecasts.page').then((m) => m.ForecastsPage),
  },
  {
    path: 'reports',
    canActivate: [authGuard],
    title: 'Reports',
    loadComponent: () => import('./features/reports/reports.page').then((m) => m.ReportsPage),
  },
  {
    path: 'ai-assistant',
    canActivate: [authGuard],
    title: 'AI Assistant',
    loadComponent: () => import('./features/assistant/assistant.page').then((m) => m.AssistantPage),
  },
  { path: 'demo', loadComponent: () => import('./features/dashboard/dashboard.page').then((m) => m.DashboardPage) },
  { path: 'demo/products', loadComponent: () => import('./features/products/products.page').then((m) => m.ProductsPage) },
  { path: 'demo/demand-analysis', loadComponent: () => import('./features/demand-analysis/demand-analysis.page').then((m) => m.DemandAnalysisPage) },
  { path: 'demo/reports', loadComponent: () => import('./features/reports/reports.page').then((m) => m.ReportsPage) },
  { path: 'demo/forecasts', loadComponent: () => import('./features/forecasts/forecasts.page').then((m) => m.ForecastsPage) },
  { path: 'demo/ai-assistant', loadComponent: () => import('./features/assistant/assistant.page').then((m) => m.AssistantPage) },
  { path: '**', redirectTo: 'dashboard' },
];
