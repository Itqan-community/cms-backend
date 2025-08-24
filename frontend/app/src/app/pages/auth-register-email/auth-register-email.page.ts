import { Component } from '@angular/core';
import { InputTextModule } from 'primeng/inputtext';
import { PasswordModule } from 'primeng/password';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';

@Component({
  standalone: true,
  selector: 'app-register-email',
  imports: [InputTextModule, PasswordModule, ButtonModule, CardModule],
  template: `
    <main class="container py-6">
      <p-card header="Register with Email">
        <div class="flex flex-col gap-3">
          <input pInputText placeholder="Email" class="w-full" />
          <p-password [feedback]="true" placeholder="Password" class="w-full"></p-password>
          <button pButton label="Create Account"></button>
        </div>
      </p-card>
    </main>
  `
})
export class RegisterEmailPage {}


