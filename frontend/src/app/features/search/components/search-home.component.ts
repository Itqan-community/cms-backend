import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzResultModule } from 'ng-zorro-antd/result';

@Component({
  selector: 'app-search-home',
  standalone: true,
  imports: [CommonModule, NzResultModule],
  template: `
    <nz-result
      nzIcon="search"
      nzTitle="Search Interface"
      nzSubTitle="Advanced search functionality will be implemented in upcoming tasks."
    ></nz-result>
  `
})
export class SearchHomeComponent {}
