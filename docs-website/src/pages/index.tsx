import {type ReactNode, useState, useEffect} from 'react';
import Link from '@docusaurus/Link';
import Translate from '@docusaurus/Translate';
import useBaseUrl from '@docusaurus/useBaseUrl';
import useDocusaurusContext from '@docusaurus/useDocusaurusContext';
import Layout from '@theme/Layout';
import Heading from '@theme/Heading';
import styles from './index.module.css';

const IcAudio = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M9 18V5l12-2v13" />
    <circle cx="6" cy="18" r="3" />
    <circle cx="18" cy="16" r="3" />
  </svg>
);

const IcBook = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z" />
    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z" />
  </svg>
);

const IcSearch = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="11" cy="11" r="8" />
    <path d="m21 21-4.35-4.35" />
  </svg>
);

const IcCode = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="16 18 22 12 16 6" />
    <polyline points="8 6 2 12 8 18" />
  </svg>
);

const IcFlask = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M9 3h6" />
    <path d="M10 3v6l-4.35 7.5A2 2 0 0 0 7.41 19.5h9.18a2 2 0 0 0 1.76-2.96L14 9V3" />
    <path d="M6.53 15h10.94" />
  </svg>
);

const IcHeart = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z" />
  </svg>
);

const IcBranch = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <line x1="6" y1="3" x2="6" y2="15" />
    <circle cx="18" cy="6" r="3" />
    <circle cx="6" cy="18" r="3" />
    <path d="M18 9a9 9 0 0 1-9 9" />
  </svg>
);

const IcShield = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    <polyline points="9 12 11 14 15 10" />
  </svg>
);

const IcCheck = () => (
  <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <polyline points="2 8 6 12 14 4" />
  </svg>
);

const IcGithub = () => (
  <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
    <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.019 10.019 0 0 0 22 12.017C22 6.484 17.522 2 12 2z" />
  </svg>
);

const IcGlobe = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <circle cx="12" cy="12" r="10" />
    <line x1="2" y1="12" x2="22" y2="12" />
    <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
  </svg>
);

function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReduced(mq.matches);
    const handler = (e: MediaQueryListEvent) => setReduced(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);
  return reduced;
}

const ROTATING_WORDS: {id: string; word: string}[] = [
  {id: 'homepage.hero.title.word.trusted', word: 'Trusted'},
  {id: 'homepage.hero.title.word.verified', word: 'Verified'},
  {id: 'homepage.hero.title.word.licensed', word: 'Licensed'},
  {id: 'homepage.hero.title.word.unique', word: 'Unique'},
];

function RotatingWord(): ReactNode {
  const [index, setIndex] = useState(0);
  const reduced = usePrefersReducedMotion();

  useEffect(() => {
    if (reduced) return;
    const id = setInterval(() => setIndex(i => (i + 1) % ROTATING_WORDS.length), 2400);
    return () => clearInterval(id);
  }, [reduced]);

  const {id, word} = ROTATING_WORDS[index];
  return (
    <span className={styles.heroRotator} aria-live="polite" aria-atomic="true">
      <span key={index} className={reduced ? undefined : styles.heroRotatorWord}>
        <Translate id={id}>{word}</Translate>
      </span>
    </span>
  );
}

function Hero(): ReactNode {
  const logoUrl = useBaseUrl('/img/itqan-logo.png');
  const {i18n: {currentLocale}} = useDocusaurusContext();
  const isArabic = currentLocale === 'ar';
  return (
    <section className={styles.hero}>
      <div className={styles.heroBackdrop} aria-hidden="true" />
      <div className={styles.heroInner}>
        <img src={logoUrl} alt="Itqan" className={styles.heroLogo} />
        <Heading as="h1" className={styles.heroTitle}>
          {isArabic && (
            <><Translate id="homepage.hero.title.prefix">بيانات قرآنية</Translate>{' '}</>
          )}
          <RotatingWord />{' '}
          <Translate id="homepage.hero.title.rest">
            Quranic Data via APIs and Direct Downloads
          </Translate>
        </Heading>
        <p className={styles.heroSubtitle}>
          <Translate id="homepage.hero.subtitle">
            Access authentic Quranic resources from verified publishers through clean APIs, structured downloads, and transparent licensing.
          </Translate>
        </p>
        <div className={styles.heroCtas}>
          <Link
            className={`button button--primary button--lg ${styles.ctaPrimary}`}
            to="/docs/getting-started/quickstart">
            <Translate id="homepage.hero.cta.start">Getting Started</Translate>
          </Link>
          <Link
            className={`button button--secondary button--lg ${styles.ctaSecondary}`}
            to="/docs/reference/api/">
            <Translate id="homepage.hero.cta.reference">API Reference</Translate>
          </Link>
        </div>
      </div>
    </section>
  );
}

const BUILD_ITEMS: {
  icon: ReactNode;
  titleId: string;
  title: string;
  points: { id: string; text: string }[];
  highlight?: boolean;
}[] = [
  {
    icon: <IcAudio />,
    titleId: 'homepage.build.recitation.title',
    title: 'Recitation Apps',
    points: [
      { id: 'homepage.build.recitation.point1', text: 'Stream audio across multiple Qira\'at and Riwayat.' },
      { id: 'homepage.build.recitation.point2', text: 'Ayah-level timing for synced playback and highlighting.' },
      { id: 'homepage.build.recitation.point3', text: 'Verified reciters with structured audio metadata.' },
    ],
  },
  {
    icon: <IcGlobe />,
    titleId: 'homepage.build.education.title',
    title: 'Quranic Platforms',
    points: [
      { id: 'homepage.build.education.point1', text: 'Tafsir apps and multilingual translations.' },
      { id: 'homepage.build.education.point2', text: 'Morphological and semantic metadata per word.' },
      { id: 'homepage.build.education.point3', text: 'Memorization and study tools built on structured scholarly sources.' },
    ],
  },
  {
    icon: <IcSearch />,
    titleId: 'homepage.build.general.title',
    title: 'Any Quranic Experience',
    highlight: true,
    points: [
      { id: 'homepage.build.general.point1', text: 'Authentic text, audio, and metadata from verified publishers.' },
      { id: 'homepage.build.general.point2', text: 'Transparent licensing and clear attribution for every asset.' },
      { id: 'homepage.build.general.point3', text: 'One trusted foundation for any Quranic product or tool.' },
    ],
  },
];

function WhatYouCanBuild(): ReactNode {
  return (
    <section className={`${styles.section} ${styles.sectionAlt}`}>
      <div className={styles.container}>
        <Heading as="h2" className={styles.sectionTitle}>
          <Translate id="homepage.build.title">What You Can Build</Translate>
        </Heading>
        <p className={styles.sectionLede}>
          <Translate id="homepage.build.lede">
            A starting point for the apps and tools the Quranic ecosystem still needs.
          </Translate>
        </p>
        <div className={styles.buildGrid}>
          {BUILD_ITEMS.map(item => (
            <article key={item.title} className={`${styles.buildCard}${item.highlight ? ` ${styles.buildCardHighlight}` : ''}`}>
              <div className={styles.buildCardHeader}>
                <div className={styles.buildIcon}>{item.icon}</div>
                <Heading as="h3" className={styles.buildTitle}>
                  <Translate id={item.titleId}>{item.title}</Translate>
                </Heading>
              </div>
              <ul className={styles.buildPoints}>
                {item.points.map(point => (
                  <li key={point.id} className={styles.buildPoint}>
                    <span className={styles.buildCheck}><IcCheck /></span>
                    <Translate id={point.id}>{point.text}</Translate>
                  </li>
                ))}
              </ul>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

const ECOSYSTEM_ITEMS: {
  icon: ReactNode;
  titleId: string;
  title: string;
  descId: string;
  desc: string;
  highlight?: boolean;
}[] = [
  {
    icon: <IcCode />,
    titleId: 'homepage.audience.developers.title',
    title: 'For Developers',
    descId: 'homepage.audience.developers.desc',
    desc: 'Documented REST APIs, versioned endpoints, and ready-to-run examples — production-ready out of the box.',
  },
  {
    icon: <IcFlask />,
    titleId: 'homepage.audience.researchers.title',
    title: 'For Researchers',
    descId: 'homepage.audience.researchers.desc',
    desc: 'Verified sources, citable resource IDs, and licensing history for reproducible academic work.',
  },
  {
    icon: <IcGlobe />,
    titleId: 'homepage.audience.everyone.title',
    title: 'For Everyone',
    descId: 'homepage.audience.everyone.desc',
    desc: 'Individuals, startups, and institutions alike — any project that needs authentic, licensed Quranic data has a foundation here.',
    highlight: true,
  },
];

function BuiltForEcosystem(): ReactNode {
  return (
    <section className={styles.section}>
      <div className={styles.container}>
        <Heading as="h2" className={styles.sectionTitle}>
          <Translate id="homepage.audience.title">Built for the Quranic Ecosystem</Translate>
        </Heading>
        <p className={styles.sectionLede}>
          <Translate id="homepage.audience.lede">
            Whether you ship apps, write papers, or build curricula — Itqan gives you the same trusted foundation.
          </Translate>
        </p>
        <div className={styles.buildGrid}>
          {ECOSYSTEM_ITEMS.map(item => (
            <article key={item.title} className={`${styles.buildCard}${item.highlight ? ` ${styles.buildCardHighlight}` : ''}`}>
              <div className={styles.buildCardHeader}>
                <div className={styles.buildIcon}>{item.icon}</div>
                <Heading as="h3" className={styles.buildTitle}>
                  <Translate id={item.titleId}>{item.title}</Translate>
                </Heading>
              </div>
              <p className={styles.buildDesc}>
                <Translate id={item.descId}>{item.desc}</Translate>
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

const WHY_ITEMS: {
  icon: ReactNode;
  labelId: string;
  label: string;
  descId: string;
  desc: string;
}[] = [
  {
    icon: <IcHeart />,
    labelId: 'homepage.why.nonprofit.label',
    label: 'Non-profit',
    descId: 'homepage.why.nonprofit.desc',
    desc: 'Built by the community, for the community, with no VC pressure or hidden agenda.',
  },
  {
    icon: <IcBranch />,
    labelId: 'homepage.why.opensource.label',
    label: 'Open source',
    descId: 'homepage.why.opensource.desc',
    desc: 'Inspect the code, contribute, or self-host the platform when needed.',
  },
  {
    icon: <IcShield />,
    labelId: 'homepage.why.authentic.label',
    label: 'Authentic',
    descId: 'homepage.why.authentic.desc',
    desc: 'Content is sourced from verified publishers and maintained with scholarly care.',
  },
  {
    icon: <IcGlobe />,
    labelId: 'homepage.why.multilingual.label',
    label: 'Multilingual',
    descId: 'homepage.why.multilingual.desc',
    desc: 'Designed to support Arabic and English experiences through language-aware APIs.',
  },
];

function WhyItqan(): ReactNode {
  return (
    <section className={styles.section}>
      <div className={styles.container}>
        <Heading as="h2" className={styles.sectionTitle}>
          <Translate id="homepage.why.title">Why Itqan</Translate>
        </Heading>
        <p className={styles.sectionLede}>
          <Translate id="homepage.why.lede">
            An infrastructure built on trust, openness, and scholarly integrity.
          </Translate>
        </p>
        <div className={styles.whyGrid}>
          {WHY_ITEMS.map(item => (
            <div key={item.label} className={styles.whyItem}>
              <span className={styles.whyItemIcon} aria-hidden="true">{item.icon}</span>
              <span className={styles.whyLabel}>
                <Translate id={item.labelId}>{item.label}</Translate>
              </span>
              <span className={styles.whyDesc}>
                <Translate id={item.descId}>{item.desc}</Translate>
              </span>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function BuildItqanCMS(): ReactNode {
  return (
    <section className={`${styles.section} ${styles.sectionAlt}`}>
      <div className={styles.container}>
        <Heading as="h2" className={styles.sectionTitle}>
          <Translate id="homepage.cta.title">Help Connect Quranic Publishers and Builders</Translate>
        </Heading>
        <p className={styles.sectionLede}>
          <Translate id="homepage.cta.lede">
            Itqan CMS is open source and community-driven. Every contribution helps trusted Quranic data reach builders worldwide — earning you reward beyond the codebase.
          </Translate>
        </p>
        <div className={styles.ctaButtons}>
          <Link
            className={`button button--secondary ${styles.ctaSecondary} ${styles.ctaGithub}`}
            href="https://github.com/Itqan-community/cms-backend">
            <IcGithub />
            <Translate id="homepage.cta.backend">CMS Backend</Translate>
          </Link>
          <Link
            className={`button button--secondary ${styles.ctaSecondary} ${styles.ctaGithub}`}
            href="https://github.com/Itqan-community/cms-frontend">
            <IcGithub />
            <Translate id="homepage.cta.frontend">CMS Frontend</Translate>
          </Link>
        </div>
      </div>
    </section>
  );
}

export default function Home(): ReactNode {
  return (
    <Layout
      title="Quranic CMS - Developer Docs"
      description="Trusted Quranic data via APIs and direct downloads — verified publishers, transparent licensing.">
      <Hero />
      <main>
        <BuiltForEcosystem />
        <WhatYouCanBuild />
        <WhyItqan />
        <BuildItqanCMS />
      </main>
    </Layout>
  );
}
