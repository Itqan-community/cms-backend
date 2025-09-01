#!/usr/bin/env node
import fs from 'node:fs/promises';
import path from 'node:path';
import puppeteer from 'puppeteer';

const root = path.resolve(process.cwd(), '../../');
const screensDir = path.join(root, 'docs/screens/en');
const outDir = screensDir; // export PNGs next to HTML

const pages = [
  { id: 'ADMIN-001', title: 'Media Library', blocks: ['Upload', 'Grid', 'Filters'] },
  { id: 'ADMIN-002', title: 'Search Configuration', blocks: ['Index Settings', 'Synonyms', 'Relevancy'] },
  { id: 'ADMIN-003', title: 'Content Creation', blocks: ['EN/AR Toggle', 'Rich Text', 'Metadata'] },
  { id: 'ADMIN-004', title: 'Workflow', blocks: ['Status Timeline', 'Actions', 'Notes'] },
  { id: 'ADMIN-005', title: 'Role Management', blocks: ['Matrix', 'Role Detail', 'Permissions'] },
  { id: 'ADMIN-006', title: 'API Keys', blocks: ['Generate', 'Usage', 'Rate Limits'] },
  { id: 'ADMIN-007', title: 'Email Templates', blocks: ['Templates', 'Preview', 'Send Test'] },
  { id: 'ADMIN-008', title: 'Admin Theme', blocks: ['Login', 'Dashboard', 'RTL'] },
  { id: 'REG-001', title: 'Register', blocks: ['Form', 'Validation', 'Policy'] },
  { id: 'REG-002', title: 'Email Verification', blocks: ['Verify', 'Resend', 'Help'] },
  { id: 'AUTH-001', title: 'Login', blocks: ['Social', 'Email/Password', 'Forgot Password'] },
  { id: 'AUTH-002', title: 'Token Exchange', blocks: ['Loading', 'Status', 'Continue'] },
  { id: 'DASH-001', title: 'Dashboard', blocks: ['Welcome', 'Checklist', 'Stats'] },
  { id: 'PUB-001', title: 'Public Articles', blocks: ['List', 'Filters', 'SEO'] },
  { id: 'PUB-002', title: 'Article Detail', blocks: ['Hero', 'Body', 'Share'] },
  { id: 'PUB-003', title: 'Embedded Search', blocks: ['Input', 'Suggestions', 'Results'] },
  { id: 'SEARCH-001', title: 'Search', blocks: ['Facets', 'Results', 'Pagination'] },
  { id: 'LIC-001', title: 'License Modal', blocks: ['Terms', 'Accept', 'Decline'] }
];

const baseTemplate = async (id, title, blocks) => `<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <title>${id} – ${title}</title>
  <link rel="stylesheet" href="_style.css" />
  <style>
    .hero {background: linear-gradient(135deg,#669B80,#22433D); color: #fff; padding: 28px 20px;border-radius:12px}
    .hero h1 {margin: 0 0 6px 0; font-size: 26px}
    .columns {display:grid; grid-template-columns: 1fr 2fr; gap: 16px}
    .modal {max-width:680px; margin:0 auto}
  </style>
</head>
<body>
  <div class="header">
    <div class="brand">Itqan CMS</div>
    <nav class="nav"><span>Home</span><span>Docs</span><span>Standards</span><span>About</span></nav>
    <div><button class="btn">Log in</button> <button class="btn primary">Sign up</button></div>
  </div>

  <div class="container">
    <div class="hero"><h1>${title} (${id})</h1><div>English UI mock aligned to cms.mdc</div></div>

    <div class="card">
      <div class="columns">
        <div>
          <div class="label">Primary actions</div>
          <div class="grid cols-1">
            <button class="btn primary">Create</button>
            <button class="btn">Manage</button>
          </div>
          <div style="margin-top:12px">
            <div class="label">Filters</div>
            <div class="grid cols-1">
              <input class="input" placeholder="Search..." />
              <select class="input"><option>All languages</option><option>English</option><option>Arabic</option></select>
              <select class="input"><option>Status: All</option><option>Active</option><option>Draft</option></select>
            </div>
          </div>
        </div>
        <div>
          <div class="label">${title} content</div>
          <div class="grid cols-2">
            ${blocks.map(b=>`<div class="card"><div class="label">${b}</div><div style="height:80px;background:#fbfdff;border:1px dashed #dbe3ea;border-radius:6px"></div></div>`).join('')}
          </div>
          <div class="card" style="margin-top:16px">
            <table class="table">
              <thead><tr><th>Title</th><th>Type</th><th>Language</th><th>Updated</th><th></th></tr></thead>
              <tbody>
                <tr><td>Sample item</td><td>Resource</td><td>English</td><td>2025-08-21</td><td><button class="btn">Edit</button></td></tr>
                <tr><td>Another item</td><td>License</td><td>Arabic</td><td>2025-08-20</td><td><button class="btn">View</button></td></tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>

    ${id==='LIC-001' ? `<div class="modal card"><div class="label">License Terms</div><p>By proceeding, you agree to the Islamic licensing and attribution terms.</p><div style="display:flex;gap:12px;justify-content:flex-end"><button class="btn">Decline</button><button class="btn primary">Accept</button></div></div>` : ''}
  </div>

  <div class="footer">© Itqan CMS – English screen ${id}</div>
</body>
</html>`;

(async() => {
  await fs.mkdir(screensDir, { recursive: true });

  // Write tailored HTML files per screen
  for (const { id, title, blocks } of pages) {
    const html = await baseTemplate(id, title, blocks);
    await fs.writeFile(path.join(screensDir, `${id}.html`), html, 'utf8');
  }

  // Launch headless browser and export PNGs
  const browser = await puppeteer.launch({ headless: 'new' });
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 2 });

  for (const { id } of pages) {
    const file = path.join(screensDir, `${id}.html`);
    await page.goto(`file://${file}`, { waitUntil: 'networkidle0' });
    const out = path.join(outDir, `${id}.en.png`);
    await page.screenshot({ path: out, fullPage: true });
    console.log('Exported', out);
  }

  await browser.close();
})();
