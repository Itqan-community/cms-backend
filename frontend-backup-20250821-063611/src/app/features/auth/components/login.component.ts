import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzResultModule } from 'ng-zorro-antd/result';
import { NzButtonModule } from 'ng-zorro-antd/button';
import { AuthService } from '../../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, NzResultModule, NzButtonModule],
  template: `
    <nz-result
      nzIcon="user"
      nzTitle="Login to Itqan CMS"
      nzSubTitle="Access your Quranic content management dashboard"
    >
      <div nz-result-extra>
        <button nz-button nzType="primary" (click)="login()">
          Login with Auth0
        </button>
      </div>
    </nz-result>
  `
})
export class LoginComponent {
  constructor(private authService: AuthService) {}

  login(): void {
    this.authService.login();
  }
}
