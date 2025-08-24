import { Component } from '@angular/core';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { Router } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-dialog-license-terms',
  imports: [DialogModule, ButtonModule],
  template: `
    <main class="container py-6">
      <p-dialog [(visible)]="visible" [modal]="true" header="License Terms" [style]="{width: '50vw'}">
        <p>Terms and conditions preview for the selected license.</p>
        <ng-template pTemplate="footer">
          <button pButton label="Cancel" (click)="close()"></button>
          <button pButton label="Accept" (click)="confirm()"></button>
        </ng-template>
      </p-dialog>
    </main>
  `
})
export class LicenseTermsDialogPage {
  visible = true;
  constructor(private router: Router) {}
  close() { this.visible = false; this.router.navigate(['/demo']); }
  confirm() { this.router.navigate(['/demo/license-terms-confirm']); }
}


