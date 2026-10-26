import {
  EvaluationResult,
  ForecastRunItem,
  PredictionPage,
  RecommendationPage,
} from '../../core/models/forecast.models';

export type ReportType = 'historical' | 'predictions' | 'evaluation' | 'recommendations';
export type ForecastReportType = Exclude<ReportType, 'historical'>;
export const REPORT_LABELS: Record<ReportType, string> = {
  historical: 'Historical Sales Report',
  predictions: 'Forecast Predictions Report',
  evaluation: 'Forecast Evaluation Report',
  recommendations: 'Demand Recommendations Report',
};
export interface RunReportContext {
  run: ForecastRunItem;
  generatedAt: string;
}
export type ForecastReportData =
  | { kind: 'predictions'; data: PredictionPage }
  | { kind: 'evaluation'; data: EvaluationResult }
  | { kind: 'recommendations'; data: RecommendationPage };
export interface GeneratedForecastReport {
  context: RunReportContext;
  report: ForecastReportData;
}
export type CsvCell = string | number | null;
export interface ReportTable {
  headers: string[];
  rows: CsvCell[][];
}
