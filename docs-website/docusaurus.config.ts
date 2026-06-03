import {themes as prismThemes} from 'prism-react-renderer';
import type {Config} from '@docusaurus/types';
import type * as Preset from '@docusaurus/preset-classic';
import remarkApiBase from './scripts/remark-api-base.mjs';

const docsEnv = process.env.DOCS_ENV ?? 'production';
const url = docsEnv === 'staging'
  ? 'https://staging.docs.cms.itqan.dev'
  : 'https://docs.cms.itqan.dev';
const assetLibraryUrl = docsEnv === 'staging'
  ? 'https://staging.cms.itqan.dev'
  : 'https://cms.itqan.dev';

const config: Config = {
  title: 'Quranic CMS - Developer Docs',
  customFields: {assetLibraryUrl},
  tagline: 'Build with the Itqan CMS API',
  favicon: 'img/itqan-logo.png',

  future: {
    v4: true,
  },

  url,
  baseUrl: '/',
  trailingSlash: true,

  organizationName: 'Itqan-community',
  projectName: 'cms-backend',

  onBrokenLinks: 'throw',

  markdown: {
    hooks: {
      onBrokenMarkdownLinks: 'throw',
    },
  },

  i18n: {
    defaultLocale: 'en',
    locales: ['en', 'ar'],
    localeConfigs: {
      en: {label: 'English', direction: 'ltr', htmlLang: 'en'},
      ar: {label: 'العربية', direction: 'rtl', htmlLang: 'ar'},
    },
  },

  presets: [
    [
      'classic',
      {
        docs: {
          sidebarPath: './sidebars.ts',
          editUrl:
            'https://github.com/Itqan-community/cms-backend/edit/main/docs-website/',
          // Required by docusaurus-plugin-openapi-docs so it knows which
          // docs plugin instance to attach the generated reference pages to.
          docItemComponent: '@theme/ApiItem',
          remarkPlugins: [remarkApiBase],
        },
        blog: false,
        theme: {
          customCss: ['./src/css/custom.css', './src/css/rtl.css'],
        },
      } satisfies Preset.Options,
    ],
  ],

  // Generates MDX pages for every OpenAPI operation in docs-website/openapi/public.json.
  // The JSON is produced by: manage.py export_public_openapi --out docs-website/openapi/public.json
  // Run `npx docusaurus gen-api-docs public` after exporting to regenerate the reference pages.
  // The generated files land in docs/reference/api/ which is gitignored — CI regenerates them on every build.
  plugins: [
    [
      'docusaurus-plugin-openapi-docs',
      {
        id: 'public-api',
        docsPluginId: 'classic',
        config: {
          public: {
            specPath: 'openapi/public.json',
            outputDir: 'docs/reference/api',
            sidebarOptions: {groupPathsBy: 'tag'},
          },
        },
      },
    ],
  ],

  // Provides the OpenAPI-styled page layout for the generated reference pages.
  themes: ['docusaurus-theme-openapi-docs'],

  themeConfig: {
    image: 'img/itqan-logo.png',
    // Order of the "Request Samples" language tabs in the API Reference.
    // The first entry is the default selected language on a visitor's first
    // visit (before any choice is stored in localStorage) — keep curl first.
    languageTabs: [
      {highlight: 'bash', language: 'curl', logoClass: 'curl'},
      {highlight: 'python', language: 'python', logoClass: 'python'},
      {highlight: 'javascript', language: 'nodejs', logoClass: 'nodejs'},
      {highlight: 'javascript', language: 'javascript', logoClass: 'javascript'},
      {highlight: 'go', language: 'go', logoClass: 'go'},
      {highlight: 'php', language: 'php', logoClass: 'php'},
      {highlight: 'ruby', language: 'ruby', logoClass: 'ruby'},
      {highlight: 'java', language: 'java', logoClass: 'java'},
      {highlight: 'csharp', language: 'csharp', logoClass: 'csharp'},
    ],
    colorMode: {
      defaultMode: 'dark',
      respectPrefersColorScheme: false,
    },
    navbar: {
      title: 'Developer Docs',
      logo: {
        alt: 'Itqan Logo',
        src: 'img/itqan-logo.png',
      },
      items: [
        {
          to: '/docs/getting-started/quickstart',
          label: 'Getting Started',
          position: 'left',
        },
        {
          to: '/docs/reference/api/',
          label: 'API Reference',
          position: 'left',
        },
        {
          type: 'localeDropdown',
          position: 'right',
        },
      ],
    },
    footer: {
      style: 'dark',
      links: [
        {
          html: `<p class="footer-icon-heading"><span class="footer-heading-en">Itqan Community</span><span class="footer-heading-ar">مجتمع إتقان</span></p><div class="footer-icon-bar">
<a class="footer-icon-link" href="https://itqan.dev" target="_blank" rel="noopener noreferrer" aria-label="Itqan Website" title="Itqan Website"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"/><line x1="2" y1="12" x2="22" y2="12"/><path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/></svg></a>
<a class="footer-icon-link" href="https://community.itqan.dev" target="_blank" rel="noopener noreferrer" aria-label="Itqan Community Forum" title="Itqan Community Forum"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 21v-2a4 4 0 0 0-4-4H5a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 0 0-3-3.87"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/></svg></a>
<a class="footer-icon-link" href="mailto:connect@itqan.dev" aria-label="Contact Itqan" title="connect@itqan.dev"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z"/><polyline points="22,6 12,13 2,6"/></svg></a>
<span class="footer-icon-sep" aria-hidden="true"></span>
<a class="footer-icon-link" href="https://x.com/itqan_community" target="_blank" rel="noopener noreferrer" aria-label="Itqan on X" title="@itqan_community on X"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.744l7.73-8.835L1.254 2.25H8.08l4.26 5.632 5.904-5.632zm-1.161 17.52h1.833L7.084 4.126H5.117z"/></svg></a>
<a class="footer-icon-link" href="https://www.linkedin.com/company/itqan-community" target="_blank" rel="noopener noreferrer" aria-label="Itqan on LinkedIn" title="Itqan on LinkedIn"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.447 20.452h-3.554v-5.569c0-1.328-.027-3.037-1.852-3.037-1.853 0-2.136 1.445-2.136 2.939v5.667H9.351V9h3.414v1.561h.046c.477-.9 1.637-1.85 3.37-1.85 3.601 0 4.267 2.37 4.267 5.455v6.286zM5.337 7.433a2.062 2.062 0 0 1-2.063-2.065 2.064 2.064 0 1 1 2.063 2.065zm1.782 13.019H3.555V9h3.564v11.452zM22.225 0H1.771C.792 0 0 .774 0 1.729v20.542C0 23.227.792 24 1.771 24h20.451C23.2 24 24 23.227 24 22.271V1.729C24 .774 23.2 0 22.222 0h.003z"/></svg></a>
<a class="footer-icon-link" href="https://github.com/Itqan-community" target="_blank" rel="noopener noreferrer" aria-label="Itqan on GitHub" title="Itqan on GitHub"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/></svg></a>
</div>`,
        },
      ],
      copyright: `Built with love by Itqan team · © ${new Date().getFullYear()}`,
    },
    prism: {
      theme: prismThemes.github,
      darkTheme: prismThemes.dracula,
      additionalLanguages: ['bash', 'python', 'json'],
    },
  } satisfies Preset.ThemeConfig,

  stylesheets: [
    {
      href: 'https://fonts.googleapis.com/css2?family=Fustat:wght@200..800&family=Rubik:ital,wght@0,300..900;1,300..900&display=swap',
      rel: 'stylesheet',
    },
  ],

  headTags: [
    {tagName: 'link', attributes: {rel: 'preconnect', href: 'https://fonts.googleapis.com'}},
    {tagName: 'link', attributes: {rel: 'preconnect', href: 'https://fonts.gstatic.com', crossorigin: 'anonymous'}},
  ],
};

export default config;
