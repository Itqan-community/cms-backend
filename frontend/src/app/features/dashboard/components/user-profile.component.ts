import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { NzResultModule } from 'ng-zorro-antd/result';

@Component({
  selector: 'app-user-profile',
  standalone: true,
  imports: [CommonModule, NzResultModule],
  template: `
    <nz-result
      nzIcon="user"
      nzTitle="User Profile"
      nzSubTitle="Profile management will be implemented in upcoming tasks."
    ></nz-result>
  `
})
export class UserProfileComponent {}
