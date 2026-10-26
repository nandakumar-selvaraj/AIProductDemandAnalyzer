/** Decimal fields are serialized as strings by the current Pydantic responses. */
export type ApiDecimal = string | number;
export type RunStatusFilter = '' | 'pending' | 'running' | 'completed' | 'failed';
export interface PagedResult<T> {
  page: number;
  page_size: number;
  total_records: number;
  total_pages: number;
  items: T[];
}
export interface ForecastRunItem {
  id: number;
  model_name: string;
  model_version: string | null;
  training_cutoff: string;
  horizon_days: number;
  status: string;
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  metrics_json: Record<string, unknown> | null;
}
export interface RunContext extends Omit<ForecastRunItem, 'model_name'> {
  model_name: string | null;
}
export interface ForecastRequest {
  horizon_days: number;
  start_date: string | null;
}
export interface ForecastCreated {
  run_id: number;
  status: string;
  forecast_cutoff: string;
  horizon_days: number;
  series_processed: number;
  series_excluded: number;
  predictions_created: number;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
}
export interface ForecastPrediction {
  id: number;
  forecast_run_id: number;
  store_id: number;
  product_id: number;
  forecast_date: string;
  predicted_units: ApiDecimal;
}
export interface PredictionPage extends PagedResult<ForecastPrediction> {
  run_id: number;
}
export interface AccuracyMetrics {
  evaluated_predictions: number;
  unmatched_predictions: number;
  coverage_percent: ApiDecimal;
  total_actual_units: number;
  total_predicted_units: ApiDecimal;
  mae: ApiDecimal | null;
  wape_percent: ApiDecimal | null;
  evaluation_status: string;
  total_predictions?: number;
  evaluated_series?: number;
  total_series?: number;
}
export interface EvaluationResult extends AccuracyMetrics {
  forecast_run_id: number;
  forecast_cutoff: string;
  horizon_days: number;
  total_predictions: number;
}
export type RecommendationLabel = 'increase' | 'maintain' | 'reduce' | 'insufficient_data';
export interface RecommendationItem {
  store_id: number;
  product_id: number;
  recommendation: RecommendationLabel;
  reason: string;
  historical_daily_average: ApiDecimal | null;
  forecast_daily_average: ApiDecimal | null;
  change_percent: ApiDecimal | null;
  forecast_horizon_days: number;
  historical_coverage_days: number;
  historical_window_start: string;
  historical_window_end: string;
}
export interface RecommendationPage extends PagedResult<RecommendationItem> {
  forecast_run_id: number;
  increase_threshold_percent: ApiDecimal;
  reduce_threshold_percent: ApiDecimal;
}
export interface BacktestRequest {
  cutoff_date: string;
  horizon_days: number;
}
export interface BacktestMetrics extends AccuracyMetrics {
  evaluated_series: number;
  total_series: number;
}
export interface BacktestResult {
  cutoff_date: string;
  horizon_days: number;
  holdout_start: string;
  holdout_end: string;
  missing_dates: string[];
  models: Record<string, BacktestMetrics>;
  assumptions: string[];
}
