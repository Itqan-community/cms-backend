import { Component } from '@angular/core';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';
import { RouterLink } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-login',
  imports: [InputTextModule, PasswordModule, ButtonModule, CardModule, RouterLink],
  template: `
    <main class="container py-6">
      <p-card header="Login">
        <div class="flex flex-col gap-3">
          <input pInputText placeholder="Email" class="w-full" />
          <p-password [feedback]="false" placeholder="Password" class="w-full"></p-password>
          <button pButton label="Login"></button>
          <a routerLink="/auth/register-oauth" class="mt-4" pButton label="Login with GitHub/Google"></a>
        </div>
      </p-card>
    </main>
  `
})
export class LoginPage {}


