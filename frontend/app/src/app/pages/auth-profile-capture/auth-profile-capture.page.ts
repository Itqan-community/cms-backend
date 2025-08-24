import { Component } from '@angular/core';
import { InputTextModule } from 'primeng/inputtext';
import { DropdownModule } from 'primeng/dropdown';
import { ButtonModule } from 'primeng/button';
import { CardModule } from 'primeng/card';

@Component({
  standalone: true,
  selector: 'app-profile-capture',
  imports: [InputTextModule, DropdownModule, ButtonModule, CardModule],
  template: `
    <main class="container py-6">
      <p-card header="Complete your profile">
        <div class="flex flex-col gap-3">
          <input pInputText placeholder="Full Name" class="w-full" />
          <p-dropdown [options]="roles" optionLabel="label" placeholder="Role"></p-dropdown>
          <input pInputText placeholder="Organization" class="w-full" />
          <button pButton label="Save"></button>
        </div>
      </p-card>
    </main>
  `
})
export class ProfileCapturePage {
  roles = [{label:'Developer',value:'dev'},{label:'Publisher',value:'pub'}];
}


