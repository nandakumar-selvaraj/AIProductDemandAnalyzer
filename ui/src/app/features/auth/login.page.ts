import { Component, inject, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  imports: [FormsModule],
  template: `
    <main class="container py-5" style="max-width: 480px">
      <h1>Sign in</h1>
      <p>AI Product Demand Analyzer</p>
      <form (ngSubmit)="submit()">
        <label for="login-email">Email</label>
        <input id="login-email" name="email" type="email" autocomplete="username"
          class="form-control mb-3" [(ngModel)]="email" required maxlength="254" />
        <label for="login-password">Password</label>
        <input id="login-password" name="password" type="password" autocomplete="current-password"
          class="form-control mb-3" [(ngModel)]="password" required maxlength="1024" />
        <button type="submit" class="btn btn-primary" [disabled]="pending()">Sign in</button>
      </form>
      @if (error()) { <p role="alert">{{ error() }}</p> }
    </main>
  `,
})
export class LoginPage {
  protected email = '';
  protected password = '';
  protected readonly pending = signal(false);
  protected readonly error = signal('');
  private readonly auth = inject(AuthService);
  private readonly router = inject(Router);
  protected submit(): void {
    if (this.pending()) return;
    this.pending.set(true);
    this.error.set('');
    this.auth.login(this.email, this.password).subscribe({
      next: () => {
        this.password = '';
        this.pending.set(false);
        if (this.auth.user()) void this.router.navigateByUrl('/dashboard', { replaceUrl: true });
      },
      error: () => {
        this.password = '';
        this.pending.set(false);
        this.error.set('Sign-in failed. Check your credentials or try again later.');
      },
    });
  }
}
