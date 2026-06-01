// Rewrites openapi/public.json servers[0] based on DOCS_ENV.
// Production builds contain zero references to staging.* domains.
import fs from 'node:fs';

const env = process.env.DOCS_ENV ?? 'production';
const url = env === 'staging'
  ? 'https://staging.api.cms.itqan.dev'
  : env === 'localhost'
  ? 'http://localhost:8000'
  : 'https://api.cms.itqan.dev';

const specPath = 'openapi/public.json';
const spec = JSON.parse(fs.readFileSync(specPath, 'utf8'));
const description = env === 'staging' ? 'Staging' : env === 'localhost' ? 'Local' : 'Production';
spec.servers = [{ url, description }];
fs.writeFileSync(specPath, JSON.stringify(spec, null, 2));

console.log(`[set-api-base-url] DOCS_ENV=${env} → ${url}`);
