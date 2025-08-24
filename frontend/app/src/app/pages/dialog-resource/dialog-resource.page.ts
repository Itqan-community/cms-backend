import { Component } from '@angular/core';
import { DialogModule } from 'primeng/dialog';
import { ButtonModule } from 'primeng/button';
import { Router } from '@angular/router';

@Component({
  standalone: true,
  selector: 'app-dialog-resource',
  imports: [DialogModule, ButtonModule],
  template: `
    <main class="container py-6">
      <p-dialog [(visible)]="visible" [modal]="true" header="Resource Details" [style]="{width: '50vw'}" [draggable]="false" [resizable]="false">
        <p>Popup content for resource details and actions.</p>
        <ng-template pTemplate="footer">
          <button pButton label="Close" (click)="close()"></button>
        </ng-template>
      </p-dialog>
    </main>
  `
})
export class ResourceDetailsDialogPage {
  visible = true;
  constructor(private router: Router) {}
  close() { this.visible = false; this.router.navigate(['/demo']); }
}


