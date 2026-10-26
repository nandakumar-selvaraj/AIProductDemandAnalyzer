import { Component, signal } from '@angular/core';
import { ForecastReportComponent } from './forecast-report.component';
import { HistoricalSalesReportComponent } from './historical-sales-report.component';
import { ReportType } from './report.models';

@Component({
  selector: 'app-reports-page',
  imports: [ForecastReportComponent, HistoricalSalesReportComponent],
  templateUrl: './reports.page.html',
  styleUrl: './reports.page.scss',
})
export class ReportsPage {
  protected readonly type = signal<ReportType>('historical');
  protected readonly categories: {
    type: ReportType;
    title: string;
    description: string;
    icon: string;
  }[] = [
    {
      type: 'historical',
      title: 'Historical Sales',
      description: 'Recorded demand',
      icon: 'M5 20V12M12 20V5M19 20V9',
    },
    {
      type: 'predictions',
      title: 'Forecast Predictions',
      description: 'Future demand estimates',
      icon: 'M4 16l5-6 5 3 6-9M15 4h5v5M4 4v16h16',
    },
    {
      type: 'evaluation',
      title: 'Forecast Evaluation',
      description: 'Accuracy and coverage',
      icon: 'M12 3a9 9 0 1 0 0 18 9 9 0 0 0 0-18M12 7a5 5 0 1 0 0 10 5 5 0 0 0 0-10M12 10a2 2 0 1 0 0 4 2 2 0 0 0 0-4',
    },
    {
      type: 'recommendations',
      title: 'Recommendations',
      description: 'Demand-trend signals',
      icon: 'M9 5H5v16h14V5h-4M9 3h6v4H9zM8 11h1m3 0h4M8 15h1m3 0h4',
    },
  ];
}
