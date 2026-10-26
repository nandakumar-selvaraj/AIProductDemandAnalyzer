import { inject, Injectable } from '@angular/core';
import { map, Observable } from 'rxjs';
import {
  ForecastPrediction,
  PredictionPage,
  RecommendationItem,
  RecommendationPage,
} from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { collectCompleteReport, EXPORT_PAGE_SIZE } from './complete-export';
import { evaluationTable, predictionTable, recommendationTable } from './report-formatters';
import {
  ForecastReportData,
  ForecastReportType,
  GeneratedForecastReport,
  ReportTable,
} from './report.models';

export type ReportExportEvent =
  | { status: 'progress'; loaded: number; total: number }
  | { status: 'complete'; table: ReportTable; total: number };
@Injectable({ providedIn: 'root' })
export class ReportDataService {
  private readonly api = inject(ForecastApiService);
  generate(kind: ForecastReportType, runId: number, page: number): Observable<ForecastReportData> {
    if (kind === 'predictions')
      return this.api.getPredictions(runId, page).pipe(
        map((data) => {
          if (data.run_id !== runId || data.items.some((item) => item.forecast_run_id !== runId))
            throw new Error('Prediction response does not match the requested run.');
          return { kind, data };
        }),
      );
    if (kind === 'recommendations')
      return this.api.getRecommendations(runId, page).pipe(
        map((data) => {
          if (data.forecast_run_id !== runId)
            throw new Error('Recommendation response does not match the requested run.');
          return { kind, data };
        }),
      );
    return this.api.evaluate(runId).pipe(
      map((data) => {
        if (data.forecast_run_id !== runId)
          throw new Error('Evaluation response does not match the requested run.');
        return { kind: 'evaluation', data };
      }),
    );
  }
  table(report: ForecastReportData): ReportTable {
    switch (report.kind) {
      case 'predictions':
        return predictionTable(report.data.items);
      case 'recommendations':
        return recommendationTable(report.data.items);
      case 'evaluation':
        return evaluationTable(report.data);
    }
  }
  completeExport(snapshot: GeneratedForecastReport): Observable<ReportExportEvent> {
    const report = snapshot.report;
    const id = snapshot.context.run.id;
    if (report.kind === 'predictions') {
      return collectCompleteReport<ForecastPrediction, PredictionPage>(
        (page) => this.api.getPredictions(id, page, EXPORT_PAGE_SIZE),
        report.data.total_records,
        (page) => page.run_id === id && page.items.every((item) => item.forecast_run_id === id),
        (row) => String(row.id),
      ).pipe(
        map((event) =>
          event.status === 'complete'
            ? { status: 'complete', table: predictionTable(event.items), total: event.total }
            : event,
        ),
      );
    }
    if (report.kind === 'recommendations') {
      return collectCompleteReport<RecommendationItem, RecommendationPage>(
        (page) => this.api.getRecommendations(id, page, EXPORT_PAGE_SIZE),
        report.data.total_records,
        (page) =>
          page.forecast_run_id === id &&
          String(page.increase_threshold_percent) ===
            String(report.data.increase_threshold_percent) &&
          String(page.reduce_threshold_percent) === String(report.data.reduce_threshold_percent),
        (row) => `${row.store_id}:${row.product_id}`,
      ).pipe(
        map((event) =>
          event.status === 'complete'
            ? { status: 'complete', table: recommendationTable(event.items), total: event.total }
            : event,
        ),
      );
    }
    throw new Error('Evaluation is a single result; use Export Evaluation CSV.');
  }
}
