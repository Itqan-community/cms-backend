import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzResultModule } from 'ng-zorro-antd/result';

@Component({
  selector: 'app-admin-overview',
  standalone: true,
  imports: [CommonModule, NzResultModule],
  template: `
    <nz-result
      nzIcon="setting"
      nzTitle="Admin Panel"
      nzSubTitle="Administrative features will be implemented in upcoming tasks."
    ></nz-result>
  `
})
export class AdminOverviewComponent {}
