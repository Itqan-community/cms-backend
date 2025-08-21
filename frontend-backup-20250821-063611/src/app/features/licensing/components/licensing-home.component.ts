import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzResultModule } from 'ng-zorro-antd/result';

@Component({
  selector: 'app-licensing-home',
  standalone: true,
  imports: [CommonModule, NzResultModule],
  template: `
    <nz-result
      nzIcon="safety-certificate"
      nzTitle="Licensing Center"
      nzSubTitle="License management and agreement workflows will be implemented in upcoming tasks."
    ></nz-result>
  `
})
export class LicensingHomeComponent {}
