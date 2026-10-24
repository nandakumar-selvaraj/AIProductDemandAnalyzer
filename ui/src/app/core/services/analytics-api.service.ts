import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import { CatalogPage, DashboardSummary } from '../models/analytics.models';

@Injectable({ providedIn: 'root' })
export class AnalyticsApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;
  getDashboardSummary(): Observable<DashboardSummary> { return this.http.get<DashboardSummary>(`${this.baseUrl}/dashboard/summary`); }
  getProducts(page = 1, pageSize = 10, search = ''): Observable<CatalogPage> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (search.trim()) params = params.set('search', search.trim());
    return this.http.get<CatalogPage>(`${this.baseUrl}/products`, { params });
  }
}