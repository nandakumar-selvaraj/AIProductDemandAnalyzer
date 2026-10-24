import { Component, inject } from '@angular/core';
import { ActivatedRoute } from '@angular/router';

@Component({
  selector: 'app-placeholder-page',
  template: `
    <section class="page-heading"><div><div class="eyebrow">WORKSPACE</div><h1>{{ title }}<span class="heading-dot">.</span></h1><p class="page-subtitle">{{ description }}</p></div></section>
    <section class="placeholder-card"><div class="placeholder-icon" aria-hidden="true">{{ icon }}</div><div class="status-label">{{ status }}</div><h2>{{ messageTitle }}</h2><p>{{ messageBody }}</p></section>
  `,
  styles: [`
    :host { display: block; }.page-heading { margin-bottom: 1.6rem; }.eyebrow { color: #74809a; font-size: 0.85rem; font-weight: 750; letter-spacing: .13em; margin-bottom: .5rem; }h1 { color: #18233b; font-size: clamp(1.8rem, 3vw, 2.15rem); font-weight: 730; letter-spacing: -.055em; margin: 0; }.heading-dot { color: #5966e9; }.page-subtitle { color: #8590a6; font-size: 1.13rem; margin: .42rem 0 0; }.placeholder-card { align-items: center; background: #fff; border: 1px solid #e9edf4; border-radius: 13px; box-shadow: 0 3px 12px #19254106; display: flex; flex-direction: column; min-height: 310px; justify-content: center; padding: 2rem; text-align: center; }.placeholder-icon { align-items: center; background: #f0efff; border-radius: 15px; color: #7164d8; display: flex; font-size: 1.6rem; height: 54px; justify-content: center; width: 54px; }.status-label { background: #f3f4f8; border-radius: 18px; color: #818ca0; font-size: 0.85rem; font-weight: 700; letter-spacing: .08em; margin-top: 1rem; padding: .35rem .6rem; text-transform: uppercase; }h2 { color: #25314a; font-size: 1.1rem; font-weight: 680; margin: .9rem 0 .4rem; }.placeholder-card p { color: #909bad; font-size: 1rem; line-height: 1.6; margin: 0; max-width: 430px; }
  `],
})
export class PlaceholderPage {
  private readonly route = inject(ActivatedRoute);
  protected readonly title = this.route.snapshot.data['title'] as string;
  protected readonly description = this.route.snapshot.data['description'] as string;
  protected readonly messageTitle = this.route.snapshot.data['messageTitle'] as string;
  protected readonly messageBody = this.route.snapshot.data['messageBody'] as string;
  protected readonly status = this.route.snapshot.data['status'] as string;
  protected readonly icon = this.route.snapshot.data['icon'] as string;
}