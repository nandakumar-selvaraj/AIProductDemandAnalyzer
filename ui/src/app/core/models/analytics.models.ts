export interface DashboardForecast {
  forecast_run_id: number;
  training_cutoff: string;
  horizon_days: number;
  forecast_demand_total: number;
  recommendation_counts: Record<string, number>;
}
export interface DashboardSummary {
  product_count: number;
  store_count: number;
  historical_start_date: string | null;
  historical_end_date: string | null;
  total_units_sold: number;
  monthly_sales: [string, number][];
  latest_forecast: DashboardForecast | null;
}
export interface ProductListItem {
  id: number;
  item_code: string;
  name: string;
}
export interface CatalogPage {
  page: number;
  page_size: number;
  total_records: number;
  total_pages: number;
  items: ProductListItem[];
}

export interface StoreListItem {
  id: number;
  store_code: string;
  name: string;
}
export interface StorePage extends Omit<CatalogPage, 'items'> {
  items: StoreListItem[];
}
export interface SalesPoint {
  period: string;
  units_sold: number;
}
export interface ProductAnalyticsResponse {
  product_id: number;
  store_id: number | null;
  start_date: string | null;
  end_date: string | null;
  total_units_sold: number;
  observed_dates: number;
  daily_sales: SalesPoint[];
  monthly_sales: SalesPoint[];
}
export interface ProductAnalyticsFilters {
  storeId?: number;
  startDate?: string;
  endDate?: string;
}
export interface SalesSummary {
  start_date: string | null;
  end_date: string | null;
  total_sales: number;
  store_count: number;
  product_count: number;
  daily_sales: { sale_date: string; total_sales: number }[];
}
