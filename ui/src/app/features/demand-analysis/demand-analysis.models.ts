import { ProductAnalyticsResponse } from '../../core/models/analytics.models';

export interface CatalogChoice {
  id: number;
  name: string;
  code: string;
}
export interface AppliedFilters {
  product: CatalogChoice;
  store: CatalogChoice | null;
  startDate: string;
  endDate: string;
}
export type AnalysisState =
  | { status: 'idle' }
  | { status: 'loading'; filters: AppliedFilters }
  | { status: 'error'; filters: AppliedFilters; message: string }
  | { status: 'success'; filters: AppliedFilters; data: ProductAnalyticsResponse };

export interface ChartBar {
  period: string;
  units: number;
  x: number;
  y: number;
  width: number;
  height: number;
}
