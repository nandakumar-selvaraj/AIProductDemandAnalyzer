import { HttpClient, HttpParams } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable } from 'rxjs';
import { environment } from '../../../environments/environment';
import {
  CatalogPage,
  DashboardSummary,
  ProductAnalyticsFilters,
  ProductAnalyticsResponse,
  SalesSummary,
  StorePage,
} from '../models/analytics.models';

@Injectable({ providedIn: 'root' })
export class AnalyticsApiService {
  private readonly http = inject(HttpClient);
  private readonly baseUrl = environment.apiBaseUrl;
  getDashboardSummary(): Observable<DashboardSummary> {
    return this.http.get<DashboardSummary>(`${this.baseUrl}/dashboard/summary`);
  }
  getProducts(page = 1, pageSize = 10, search = ''): Observable<CatalogPage> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (search.trim()) params = params.set('search', search.trim());
    return this.http.get<CatalogPage>(`${this.baseUrl}/products`, { params });
  }

  getStores(page = 1, pageSize = 50, search = ''): Observable<StorePage> {
    let params = new HttpParams().set('page', page).set('page_size', pageSize);
    if (search.trim()) params = params.set('search', search.trim());
    return this.http.get<StorePage>(`${this.baseUrl}/stores`, { params });
  }

  getProductAnalytics(
    productId: number,
    filters: ProductAnalyticsFilters = {},
  ): Observable<ProductAnalyticsResponse> {
    let params = new HttpParams();
    if (filters.storeId !== undefined) params = params.set('store_id', filters.storeId);
    if (filters.startDate) params = params.set('start_date', filters.startDate);
    if (filters.endDate) params = params.set('end_date', filters.endDate);
    return this.http.get<ProductAnalyticsResponse>(
      `${this.baseUrl}/products/${productId}/analytics`,
      { params },
    );
  }

  getSalesSummary(): Observable<SalesSummary> {
    return this.http.get<SalesSummary>(`${this.baseUrl}/sales/summary`);
  }
}
