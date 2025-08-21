import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzResultModule } from 'ng-zorro-antd/result';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-register',
  standalone: true,
  imports: [CommonModule, NzResultModule, NzButtonModule],
  template: `
    <nz-result
      nzIcon="user-add"
      nzTitle="Register for Itqan CMS"
      nzSubTitle="Create your account to start managing Quranic content"
    >
      <div nz-result-extra>
        <button nz-button nzType="primary" (click)="register()">
          Sign Up with Auth0
        </button>
      </div>
    </nz-result>
  `
})
export class RegisterComponent {
  constructor(private authService: AuthService) {}

  register(): void {
    this.authService.register();
  }
}
