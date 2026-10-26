import { HttpClient, HttpParams } from '@angular/common/http';
import { inject, Injectable } from '@angular/core';
import { environment } from '../../../environments/environment';
import {
  BacktestRequest,
  BacktestResult,
  EvaluationResult,
  ForecastCreated,
  ForecastRequest,
  ForecastRunItem,
  PagedResult,
  PredictionPage,
  RecommendationPage,
  RunStatusFilter,
} from '../models/forecast.models';

@Injectable({ providedIn: 'root' })
export class ForecastApiService {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiBaseUrl;
  private pagination(page: number, pageSize: number): HttpParams {
    return new HttpParams().set('page', page).set('page_size', pageSize);
  }
  getLatestCompleted() {
    return this.http.get<ForecastRunItem | null>(`${this.base}/forecasts/latest`);
  }
  getRuns(page = 1, status: RunStatusFilter = '') {
    let params = this.pagination(page, 10);
    if (status) params = params.set('status', status);
    return this.http.get<PagedResult<ForecastRunItem>>(`${this.base}/forecasts/runs`, { params });
  }
  createForecast(request: ForecastRequest) {
    return this.http.post<ForecastCreated>(`${this.base}/forecasts`, request);
  }
  getPredictions(runId: number, page = 1, pageSize = 50) {
    return this.http.get<PredictionPage>(`${this.base}/forecasts/${runId}/predictions`, {
      params: this.pagination(page, pageSize),
    });
  }
  evaluate(runId: number) {
    return this.http.post<EvaluationResult>(`${this.base}/forecasts/evaluate`, {
      forecast_run_id: runId,
    });
  }
  getRecommendations(runId: number, page = 1, pageSize = 50) {
    return this.http.get<RecommendationPage>(`${this.base}/recommendations`, {
      params: this.pagination(page, pageSize).set('forecast_run_id', runId),
    });
  }
  backtest(request: BacktestRequest) {
    return this.http.post<BacktestResult>(`${this.base}/forecasts/backtest`, request);
  }
}
