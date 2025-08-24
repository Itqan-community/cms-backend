import { Component } from '@angular/core';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { Router } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-dialog-license-confirm',
  imports: [DialogModule, ButtonModule],
  template: `
    <main class="container py-6">
      <p-dialog [(visible)]="visible" [modal]="true" header="Confirm Acceptance" [style]="{width: '35vw'}">
        <p>You are about to accept the license and start download.</p>
        <ng-template pTemplate="footer">
          <button pButton label="Back" (click)="back()"></button>
          <button pButton label="Confirm" (click)="confirm()"></button>
        </ng-template>
      </p-dialog>
    </main>
  `
})
export class LicenseTermsConfirmDialogPage {
  visible = true;
  constructor(private router: Router) {}
  back() { this.visible = false; this.router.navigate(['/demo/license-terms-dialog']); }
  confirm() { this.visible = false; this.router.navigate(['/demo']); }
}


