import { Component } from '@angular/core';
import { MainLayoutComponent } from './layouts/main-layout.component';

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [MainLayoutComponent],
  template: `
    <app-main-layout></app-main-layout>
  `,
  styles: []
})
export class AppComponent {
  title = 'Itqan CMS';
}