import { Component } from '@angular/core';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';

@Component({
  standalone: true,
  selector: 'app-register-oauth',
  imports: [ButtonModule, CardModule],
  template: `
    <main class="container py-6">
      <p-card header="Register via OAuth">
        <div class="flex flex-col gap-3">
          <button pButton icon="pi pi-github" label="Continue with GitHub"></button>
          <button pButton icon="pi pi-google" label="Continue with Google"></button>
        </div>
      </p-card>
    </main>
  `
})
export class RegisterGithubGooglePage {}


