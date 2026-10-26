import { TestBed } from '@angular/core/testing';
import { HistoricalChartComponent } from './historical-chart.component';

describe('HistoricalChartComponent', () => {
  it('describes the daily chart and plots only actual records, including zero markers', () => {
    const fixture = TestBed.createComponent(HistoricalChartComponent);
    fixture.componentRef.setInput('chartId', 'daily-test');
    fixture.componentRef.setInput('granularity', 'daily');
    fixture.componentRef.setInput('points', [
      { period: '2024-01-01', units_sold: 10 },
      { period: '2024-01-03', units_sold: 0 },
    ]);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('svg')?.getAttribute('aria-describedby')).toBe(
      'daily-test-description',
    );
    expect(root.querySelector('desc')?.textContent).toContain('Missing periods are gaps');
    expect(root.querySelectorAll('rect')).toHaveLength(2);
    expect(root.querySelectorAll('circle')).toHaveLength(1);
    expect(root.querySelector('desc')?.textContent).toContain(
      'Recorded daily observations table below',
    );
    expect(root.querySelector('.chart-scroll')?.getAttribute('tabindex')).toBe('0');
  });
  it('provides a keyboard-operable exact monthly values table', () => {
    const fixture = TestBed.createComponent(HistoricalChartComponent);
    fixture.componentRef.setInput('chartId', 'monthly-test');
    fixture.componentRef.setInput('granularity', 'monthly');
    fixture.componentRef.setInput('points', [{ period: '2024-01-01', units_sold: 1234 }]);
    fixture.detectChanges();
    const root = fixture.nativeElement as HTMLElement;
    expect(root.querySelector('summary')?.textContent?.trim()).toBe('Exact monthly values');
    expect(root.querySelector('table')?.textContent).toContain('1,234');
    expect(root.querySelector('table')?.textContent).toContain('January 2024');
  });
});
