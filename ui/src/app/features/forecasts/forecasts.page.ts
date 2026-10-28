import {
  afterNextRender,
  Component,
  computed,
  ElementRef,
  inject,
  Injector,
  signal,
  viewChild,
} from '@angular/core';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { AlertComponent, SpinnerComponent } from '@coreui/angular';
import { startWith, Subject, switchMap } from 'rxjs';
import { ForecastCreated, ForecastRunItem, RunContext } from '../../core/models/forecast.models';
import { ForecastApiService } from '../../core/services/forecast-api.service';
import { DemoService } from '../../core/services/demo.service';
import { BacktestingComponent } from './backtesting.component';
import { CreateForecastComponent } from './create-forecast.component';
import { EvaluationComponent } from './evaluation.component';
import { createdContext, LoadState, requestState } from './forecast.helpers';
import { PredictionsComponent } from './predictions.component';
import { RecommendationsComponent } from './recommendations.component';
import { RunHistoryComponent } from './run-history.component';
import { RunOverviewComponent } from './run-overview.component';

@Component({
  selector: 'app-forecasts-page',
  imports: [
    AlertComponent,
    SpinnerComponent,
    BacktestingComponent,
    CreateForecastComponent,
    EvaluationComponent,
    PredictionsComponent,
    RecommendationsComponent,
    RunHistoryComponent,
    RunOverviewComponent,
  ],
  templateUrl: './forecasts.page.html',
  styleUrl: './forecast-panel.scss',
})
export class ForecastsPage {
  protected readonly demo = inject(DemoService);
  private readonly api = inject(ForecastApiService);
  private readonly injector = inject(Injector);
  private readonly latestRequests = new Subject<void>();
  private readonly history = viewChild(RunHistoryComponent);
  private readonly selectedHeading = viewChild<ElementRef<HTMLElement>>('selectedHeading');
  protected readonly selected = signal<RunContext | null>(null);
  protected readonly latestState = signal<LoadState<ForecastRunItem | null>>({ status: 'loading' });
  protected readonly latest = computed(() => {
    const state = this.latestState();
    return state.status === 'success' ? state.data : null;
  });
  constructor() {
    this.latestRequests
      .pipe(
        startWith(undefined),
        switchMap(() => requestState(this.api.getLatestCompleted())),
        takeUntilDestroyed(),
      )
      .subscribe((state) => {
        this.latestState.set(state);
        if (
          state.status === 'success' &&
          state.data &&
          (!this.selected() || this.selected()?.id === state.data.id)
        )
          this.selected.set(state.data);
      });
  }
  protected refreshLatest(): void {
    this.latestRequests.next();
  }
  protected selectRun(run: ForecastRunItem): void {
    this.selected.set(run);
    afterNextRender(() => this.selectedHeading()?.nativeElement.focus(), {
      injector: this.injector,
    });
  }
  protected onCreated(run: ForecastCreated): void {
    this.selected.set(createdContext(run));
    this.history()?.refresh(true);
    this.refreshLatest();
  }
  protected focusHistory(): void {
    this.history()?.focusHeading();
  }
}
