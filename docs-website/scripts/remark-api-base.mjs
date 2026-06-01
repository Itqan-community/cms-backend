import {visit} from 'unist-util-visit';

function resolveApiBase() {
  const env = process.env.DOCS_ENV;
  if (env === 'staging') return 'https://staging.api.cms.itqan.dev';
  if (env === 'production') return 'https://api.cms.itqan.dev';
  if (env === 'localhost') return 'http://localhost:8000';
  return 'https://api.cms.itqan.dev';
}

export default function remarkApiBase() {
  const base = resolveApiBase();
  return (tree) => {
    visit(tree, (node) => {
      if (node.type === 'text' || node.type === 'inlineCode' || node.type === 'code') {
        if (typeof node.value === 'string') {
          node.value = node.value.replaceAll('{{API_BASE}}', base);
        }
      }
    });
  };
}
