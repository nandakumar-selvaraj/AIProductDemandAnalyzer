import { Routes } from '@angular/router';

const placeholder = (data: Record<string, string>) => ({
  data,
  loadComponent: () => import('./shared/placeholder.page').then((m) => m.PlaceholderPage),
});

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  {
    path: 'dashboard',
    title: 'Dashboard',
    loadComponent: () => import('./features/dashboard/dashboard.page').then((m) => m.DashboardPage),
  },
  {
    path: 'products',
    title: 'Products',
    loadComponent: () => import('./features/products/products.page').then((m) => m.ProductsPage),
  },
  {
    path: 'demand-analysis',
    title: 'Demand Analysis',
    loadComponent: () =>
      import('./features/demand-analysis/demand-analysis.page').then((m) => m.DemandAnalysisPage),
  },
  {
    path: 'forecasts',
    title: 'Forecasts',
    loadComponent: () => import('./features/forecasts/forecasts.page').then((m) => m.ForecastsPage),
  },
  {
    path: 'reports',
    title: 'Reports',
    loadComponent: () => import('./features/reports/reports.page').then((m) => m.ReportsPage),
  },
  {
    path: 'ai-assistant',
    title: 'AI Assistant',
    ...placeholder({
      title: 'AI Assistant',
      description: 'A future conversational workspace for demand questions.',
      messageTitle: 'Assistant planned',
      messageBody:
        'The AI assistant is planned for a later phase. No model connection or assistant functionality is active.',
      status: 'Planned',
      icon: '✳',
    }),
  },
  { path: '**', redirectTo: 'dashboard' },
];
