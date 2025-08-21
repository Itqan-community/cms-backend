import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzResultModule } from 'ng-zorro-antd/result';

@Component({
  selector: 'app-public-home',
  standalone: true,
  imports: [CommonModule, NzResultModule],
  template: `
    <nz-result
      nzIcon="global"
      nzTitle="Public Portal"
      nzSubTitle="Public content browsing will be implemented in upcoming tasks."
    ></nz-result>
  `
})
export class PublicHomeComponent {}
