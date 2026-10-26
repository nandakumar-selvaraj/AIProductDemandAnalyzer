import { DatePipe } from '@angular/common';
import { Component, computed, inject, signal } from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { FormsModule } from '@angular/forms';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { exhaustMap, Subject } from 'rxjs';
import { BacktestRequest, BacktestResult } from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { AccuracyMetricsComponent } from './accuracy-metrics.component';
import { LoadState, requestState, validateForecast } from './forecast.helpers';

@Component({
  selector: 'app-backtesting',
  imports: [DatePipe, FormsModule, AlertComponent, SpinnerComponent, AccuracyMetricsComponent],
  templateUrl: './backtesting.component.html',
  styleUrl: './forecast-panel.scss',
})
export class BacktestingComponent {
  private readonly api = inject(ForecastApiService);
  private readonly submissions = new Subject<BacktestRequest>();
  protected readonly horizon = signal<number | null>(30);
  protected readonly cutoff = signal('');
  protected readonly errors = signal<string[]>([]);
  protected readonly state = signal<LoadState<BacktestResult>>({ status: 'idle' });
  protected readonly pending = computed(() => this.state().status === 'loading');
  protected readonly models = computed(() => {
    const state = this.state();
    return state.status === 'success' ? Object.entries(state.data.models) : [];
  });
  constructor() {
    this.submissions
      .pipe(
        exhaustMap((request) => requestState(this.api.backtest(request))),
        takeUntilDestroyed(),
      )
      .subscribe((state) => this.state.set(state));
  }
  protected submit(): void {
    if (this.pending()) return;
    const horizon = this.horizon();
    this.errors.set(validateForecast(horizon, this.cutoff(), true));
    if (this.errors().length || horizon === null) return;
    this.submissions.next({ cutoff_date: this.cutoff(), horizon_days: horizon });
  }
}
