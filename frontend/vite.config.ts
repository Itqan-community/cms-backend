import { defineConfig } from 'vite';
import { angular } from '@analogjs/vite-plugin-angular';

export default defineConfig({
  plugins: [
    angular({
      tsconfig: 'tsconfig.app.json',
      workspaceRoot: __dirname,
      inlineStylesExtension: 'scss'
    })
  ],
  server: {
    port: 4200,
    host: 'localhost',
    open: true
  },
  build: {
    target: 'es2022',
    outDir: 'dist',
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['@angular/core', '@angular/common', '@angular/router'],
          nzorro: ['ng-zorro-antd'],
          auth0: ['@auth0/auth0-spa-js']
        }
      }
    }
  },
  optimizeDeps: {
    include: [
      '@angular/core',
      '@angular/common',
      '@angular/router',
      '@angular/platform-browser',
      'ng-zorro-antd',
      '@auth0/auth0-spa-js'
    ]
  },
  define: {
    'process.env': {}
  }
});
