import { DatePipe, DecimalPipe } from '@angular/common';
import { Component, computed, input } from '@angular/core';
import { SalesPoint } from '../../core/models/analytics.models';
import { sortedObservations, toChartBars } from './demand-analysis.helpers';

@Component({
  selector: 'app-historical-chart',
  imports: [DatePipe, DecimalPipe],
  templateUrl: './historical-chart.component.html',
  styleUrl: './historical-chart.component.scss',
})
export class HistoricalChartComponent {
  readonly points = input.required<readonly SalesPoint[]>();
  readonly granularity = input.required<'daily' | 'monthly'>();
  readonly chartId = input.required<string>();
  protected readonly title = computed(() =>
    this.granularity() === 'daily'
      ? 'Daily historical units sold'
      : 'Monthly historical units sold',
  );
  protected readonly sorted = computed(() => sortedObservations(this.points()));
  protected readonly bars = computed(() => toChartBars(this.points(), this.granularity()));
  protected readonly maximum = computed(() =>
    this.points().reduce((max, point) => Math.max(max, point.units_sold), 0),
  );
}
