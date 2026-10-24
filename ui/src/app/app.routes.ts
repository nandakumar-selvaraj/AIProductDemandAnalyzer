import { Routes } from '@angular/router';

const placeholder = (data: Record<string, string>) => ({
  data,
  loadComponent: () => import('./shared/placeholder.page').then((m) => m.PlaceholderPage),
});

export const routes: Routes = [
  { path: '', pathMatch: 'full', redirectTo: 'dashboard' },
  { path: 'dashboard', title: 'Dashboard', loadComponent: () => import('./features/dashboard/dashboard.page').then((m) => m.DashboardPage) },
  { path: 'products', title: 'Products', loadComponent: () => import('./features/products/products.page').then((m) => m.ProductsPage) },
  { path: 'demand-analysis', title: 'Demand Analysis', ...placeholder({ title: 'Demand Analysis', description: 'Explore sales history and demand patterns across your catalog.', messageTitle: 'Demand analysis workspace', messageBody: 'Demand analysis views are being prepared. No sample trends or analytics are shown until verified backend data is connected.', status: 'Setup in progress', icon: '⌁' }) },
  { path: 'forecasts', title: 'Forecasts', ...placeholder({ title: 'Forecasts', description: 'Review forecast runs and their projected demand.', messageTitle: 'Forecast workspace', messageBody: 'Forecast creation and evaluation are not yet connected to this UI. The backend supports a 30-day maximum horizon.', status: 'Setup in progress', icon: '↗' }) },
  { path: 'reports', title: 'Reports', ...placeholder({ title: 'Reports', description: 'Prepare clear, shareable views of your demand data.', messageTitle: 'Reports workspace', messageBody: 'Reporting views are not connected yet. This page will use recorded analytics when the reporting flow is implemented.', status: 'Setup in progress', icon: '▤' }) },
  { path: 'ai-assistant', title: 'AI Assistant', ...placeholder({ title: 'AI Assistant', description: 'A future conversational workspace for demand questions.', messageTitle: 'Assistant planned', messageBody: 'The AI assistant is planned for a later phase. No model connection or assistant functionality is active.', status: 'Planned', icon: '✳' }) },
  { path: '**', redirectTo: 'dashboard' },
];