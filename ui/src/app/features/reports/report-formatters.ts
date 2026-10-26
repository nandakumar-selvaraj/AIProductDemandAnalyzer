import {
  EvaluationResult,
  ForecastPrediction,
  RecommendationItem,
} from '../../core/models/forecast.models';
import { CsvCell, ReportTable, RunReportContext } from './report.models';

export function runContext(context: RunReportContext, scope: string): Record<string, CsvCell> {
  return {
    export_scope: scope,
    generated_at: context.generatedAt,
    forecast_run_id: context.run.id,
    model_name: context.run.model_name,
    model_version: context.run.model_version,
    training_cutoff: context.run.training_cutoff,
    horizon_days: context.run.horizon_days,
  };
}
export function predictionTable(items: readonly ForecastPrediction[]): ReportTable {
  return {
    headers: ['prediction_id', 'forecast_date', 'product_id', 'store_id', 'predicted_units'],
    rows: items.map((item) => [
      item.id,
      item.forecast_date,
      item.product_id,
      item.store_id,
      item.predicted_units,
    ]),
  };
}
export function recommendationTable(items: readonly RecommendationItem[]): ReportTable {
  return {
    headers: [
      'product_id',
      'store_id',
      'recommendation',
      'historical_daily_average',
      'forecast_daily_average',
      'change_percent',
      'historical_coverage_days',
      'historical_window_start',
      'historical_window_end',
      'forecast_horizon_days',
      'reason',
    ],
    rows: items.map((item) => [
      item.product_id,
      item.store_id,
      item.recommendation,
      item.historical_daily_average,
      item.forecast_daily_average,
      item.change_percent,
      item.historical_coverage_days,
      item.historical_window_start,
      item.historical_window_end,
      item.forecast_horizon_days,
      item.reason,
    ]),
  };
}
export function evaluationTable(item: EvaluationResult): ReportTable {
  return {
    headers: [
      'evaluation_status',
      'total_predictions',
      'evaluated_predictions',
      'unmatched_predictions',
      'coverage_percent',
      'mae',
      'wape_percent',
      'total_actual_units',
      'total_predicted_units',
    ],
    rows: [
      [
        item.evaluation_status,
        item.total_predictions,
        item.evaluated_predictions,
        item.unmatched_predictions,
        item.coverage_percent,
        item.mae,
        item.wape_percent,
        item.total_actual_units,
        item.total_predicted_units,
      ],
    ],
  };
}
export function runFilename(type: string, context: RunReportContext, scope: string): string {
  return `${type}-run-${context.run.id}-cutoff-${context.run.training_cutoff}-horizon-${context.run.horizon_days}-${scope}.csv`;
}
export function displayCell(value: CsvCell): string {
  if (value === null) return 'N/A';
  const labels: Record<string, string> = {
    increase: 'Increase',
    maintain: 'Maintain',
    reduce: 'Reduce',
    insufficient_data: 'Insufficient Data',
  };
  return labels[String(value)] ?? String(value);
}
