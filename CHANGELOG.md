## v0.20.0 (2026-10-08)

### Feat

- **content**: bilingual version name and summary
- **content**: let reviewers upload a pre-approved version
- **content**: bulk-approve review changes
- **package-manager**: add `itqan init` to create a starter manifest
- **package-manager**: add a catalog of installable packages
- **package-manager**: let the manifest choose the assets folder
- **package-manager**: resolve per language and generate missing files on download
- **audit**: preserve history in bulk operations and bulk updates (ITQ-34) (#432)

### Fix

- **package-manager**: default the CLI to the production registry
- **package-manager**: hide draft assets from the package registry
- **content**: prevent asset access request races (#517)
- stream R2 audio fallback in bounded chunks

### Refactor

- **package-manager**: move the itqan CLI to its own repository
- **package-manager**: remove the Distribution model

## v0.19.0 (2026-10-07)

### Feat

- **content**: number tafsir and translation versions as major.minor
- **audit**: enable history on tracked models (ITQ-33) (#431)
- **content**: review every change, with a filter by version
- **content**: let the source language be hidden; drop unseen assets from the gallery
- **content**: browse any committed version read-only
- **content**: flag the first version of each language in version lists
- **content**: name the editor of each change on the review page
- **content**: publish translations/tafsirs only once every change is approved
- **content**: flag draft entries differing from published versions as "changed"
- **content**: implement comprehensive filters for entries endpoint
- **content**: add CSV export for templates and assets across all categories
- **dependabot**: implement PR updater automation on AssetVersion pub… (#510)

### Fix

- **core**: add missing migration in audit_migrations
- **content**: keep the version number when reversing 0071 without a label
- **audit**: qualify AssetVersion fk reference in AssetLanguage
- **audit**: format migrations and allow audit db in dependabot tests
- **content**: lock a version while publishing it or changing its content
- **content**: only the newest version of a language can be replaced or deleted
- **content**: serve an uploaded version's file generated from its reviewed entries
- **content**: reject uploads whose rows would be dropped unreviewed
- **content**: give no review state to diffs computed on the fly
- **content**: prevent cross-tenant recitation upload mutations (#511)

### Refactor

- **content**: stop auto-deleting idle content drafts

## v0.18.0 (2026-09-28)

### Feat

- **content**: list every unit in content downloads
- **content**: expose review comments on version history
- **content**: add per-category permissions for editing content
- **content**: seed the Madinah and Shamarly mushaf layouts
- expose asset template and mushaf layout on internal assets API
- template-aware export and ayah-only verse sampling
- make the content importer template-aware
- accept and expose asset template on create
- add mushaf layout portal CRUD endpoints
- add mushaf layout permissions, repository and service
- make the review surface template-aware
- make entry writes and diffs template-aware
- enumerate entries from the template unit set
- add UnitSpec template descriptor
- enforce asset template immutability at the model layer
- add unit columns to asset version entries and changes
- add Asset.template and mushaf_layout with ayah backfill
- add MushafLayout model and AssetTemplateChoice
- **package-manager**: add itqan install CLI (ITQ-22) (#503)
- **audit**: configure django-simple-history and audit database router (#430) (#500)
- **content**: implement commit-style history with stored diffs and pruning
- **content**: add version restore functionality and seeded-language support
- **content**: enable language tagging and support for sparse draft translations
- **api**: add ayah-range combined audio endpoint
- **audit-db**: run audit migrations in CI/deploy and configure staging/production
- **audit-db**: add audit database to settings and add database router
- **content**: add verbose export option with surah name and original ayah text
- **content**: implement multi-language support for assets
- **content**: store per-ayah audio reference on RecitationAyahTiming
- **dependabot**: add GitHub installation webhook and docs
- **dependabot**: add GitHub manifest discovery
- **dependabot**: add repository opt-in persistence
- **dependabot**: add GitHub installation token exchange
- **dependabot**: add GitHub App JWT foundation
- remove footnotes from asset version entries and related processing
- **content**: public api to serve single-ayah recitation audio (#414)
- **content**: add package registry resolution API (#417)
- **client-version**: add middleware and logging for client identification via headers

### Fix

- **content**: return absolute file URLs from the portal API
- **content**: name gallery downloads {name}-{language}-{version}
- **quran**: store each word's position within its ayah
- eliminate N+1 on verbose ayah history downloads, add review-flagged tests
- guard mushaf layout name uniqueness and persist renamed physical name column
- generalize review dedup and baseline correlation to all unit templates
- correct authenticate_user idiom throughout the plan
- bound entries pagination and fix patch-response gaps from review
- overlay source_text in the entries plan instead of nulling it
- drop unused select_related and clarify UnitSpec contracts
- prevent RecursionError and stale-snapshot false positive in Asset template guard
- take the template snapshot from the raw row, not the instance
- split constraint validation into its own migration, tighten unit_id
- conform QuranDataMixin shape to downstream task assertions
- guard branch A of mushaf layout constraint against SQL NULL
- close NULL hole in asset_mushaf_layout_consistency and wire up create paths
- close NULL hole in asset_mushaf_layout_consistency constraint
- **recommendations**: reuse cache connection class for Redis pool creation
- **i18n**: refresh Arabic catalog for new range strings
- **api**: reject hidden default folders on the range path
- **api**: defer recitation cache bust until after commit
- **api**: invalidate recitation cache on tenant-restriction flips
- **api**: single-flight ayah-range builds on the range key
- **api**: log non-miss R2 HEAD failures in ayah-range check
- **api**: version ayah-range clip keys by content
- **api**: invalidate recitation cache when is_open_access changes
- **api**: precommit for ayah range
- **api**: ayah-range get silence audio in the end
- **content**: resolve AttributeError in usage analytics and fix task import
- **audit-db**: pass AUDIT_DB_* secrets to staging/production deploy env
- **audit-db**: document AUDIT_DB_* env vars and wait for audit DB readiness in the .sh
- **migrations**: sequence recitation ayah timing migration after 0057
- **content**: defer version notification dispatch
- **tests**: call superclass tearDownClass in base test class
- **tests**: restore Django test transaction cleanup
- **dependabot**: resolve CI validation issues
- **dependabot**: harden webhook reconciliation
- **dependabot**: satisfy CI ruff checks
- **dependabot**: address review feedback
- **migrations**: rename migration files and update dependencies
- **content**: invalidate recitation cache on asset visibility update
- **i18n**: add Arabic translations for single-ayah error messages
- **core**: stop permission_class() from polluting DRF metaclass __repr__
- **package-manager**: enforce asset access before version resolution
- **package-manager**: tighten SemVer validation and remove collision info disclosure
- **content**: address CodeRabbit review findings on #417
- **content**: satisfy mypy type checks for package registry

### Refactor

- **package-manager**: move package registry into dedicated app

## v0.17.1 (2026-09-20)

### Fix

- **recitations**: add id filter support to RecitationFilter schemas (#506)

## v0.17.0 (2026-09-06)

### Feat

- **client-version**: add middleware and logging for client identification via headers (#491)
- **client-version**: add middleware and logging for client identification via headers

## v0.16.0 (2026-09-06)

### Feat

- **api**: implement real sample data endpoints (#464)
- **recitations**: add folder visibility and set-default portal support
- log entry replacement details and return count from entry processing
- enforce draft edit tracking and restrict publishing unedited drafts
- extend version handling with draft rebuilding, export, and file processing
- editing part 1
- add support for file upload with versioning in asset creation APIs
- **content**: add similar-content recommendations (step 1 of #226)
- **recitations**: add ayah slicing storage sizing
- **recitations**: add ayah audio slicing
- **usage-tracking**: track API key prefix as application identity
- introduce folder management for recitations
- **quran**: add surah to ayah to word hierarchy tree api
- ensure Arabic catalog is compiled during tests and runtime
- implement assignable group logic and update translations

### Fix

- **migrations**: rename migration files and update dependencies
- **i18n**: update Arabic translations and remove unused entries
- **publishers**: handle invitations with missing member (#470)
- **migrations**: renumber is_visible migration to 0053 on staging
- **i18n**: remove trailing whitespace from django.po header
- **i18n**: add Arabic translations for folder visibility errors
- **recitations**: soft-unpublish folder timings without deleting JSON file
- **ci**: align migration 0050 with model and pass pre-commit
- **content**: resolve redis test client host from REDIS_URL, not django-redis
- **content**: resolve redis test client host from django-redis instead of hardcoding localhost
- **content**: restore missing closing brace in celery beat schedule
- **content**: correct import ordering in recommendation tests
- **content**: enforce access control and private caching on public recitation tracks
- **recitations**: add Arabic slicing error translations
- **recitations**: satisfy lint and localization checks
- **recitations**: clamp fades for short ayah slices
- **recitations**: address ayah slicing review feedback
- **recitations**: address ayah slicing review feedback
- **recitations**: preserve source audio parameters when slicing
- **recitations**: address audio slicing review feedback
- **core**: prevent race condition and data leak in throttle logging
- **users**: prevent data loss on partial developer profile updates
- **quran**: address hierarchy pr review feedback
- adjust translation and publisher permission labels and hierarchy logic
- refine logging format and update static markup nosec flag

### Perf

- **content**: resolve N+1 queries in internal asset endpoints
- **docker**: optimize Dockerfile.backend and compose setups

## v0.15.0 (2026-09-06)

### Feat

- **client-version**: add middleware and logging for client identification via headers

## v0.14.0 (2026-08-30)

### Feat

- exclude reciter endpoints from Sentry performance tracing

### Refactor

- remove reciter usage tracking to reduce costs

## v0.13.0 (2026-08-17)

### Feat

- introduce folder management for recitations
- **quran**: add surah to ayah to word hierarchy tree api

### Fix

- **quran**: address hierarchy pr review feedback

### Perf

- **docker**: optimize Dockerfile.backend and compose setups

## v0.12.0 (2026-08-10)

### Feat

- ensure Arabic catalog is compiled during tests and runtime
- implement assignable group logic and update translations

### Fix

- adjust translation and publisher permission labels and hierarchy logic

## v0.11.1 (2026-08-09)

### Fix

- update Redis connection logic to use connection pool for better configurability

## v0.11.0 (2026-08-09)

### Feat

- implement translation support for validation messages and exceptions across backend services
- redefine permission hierarchy for CRUD symmetry and implement expanded tests
- improve group management in admin with validation, permission hierarchy application, and related tests
- **usage**: update event name
- **usage**: add env vars (#400)
- add support for file upload with versioning in asset creation APIs (#398)
- **reciters**: make reciters list public and add detail endpoint
- **assets**: add reciter field and reciter_id filter to public assets API
- enhance API description, authentication guidance, and upgrade dependencies
- add reciter slug support in recitations API and update tests accordingly
- **quran**: add Quran module with sura/ayah data models, APIs, and import command

### Fix

- refine logging format and update static markup nosec flag
- correct default type for `AUDIO_USAGE_SYNC_WINDOW_HOURS` config parameter
- correct default type for `AUDIO_USAGE_SYNC_WINDOW_HOURS` config parameter
- health-check staging pushes against staging API, not production (#397)
- cache asset name_ar so recitation detail cache-hit path does not 500
- use Arabic name fields for recitation tracking and publisher metadata and deffrentiate between recitation and recitation_track
- **migrations**: update dependency for asset migration file to correct sequence
- bug when creating new users from admin page
- **emails**: localize site name in account emails and update Arabic translations
- **emails**: update hosted logo URL and remove unused STATICFILES_DIRS
- **emails**: use hosted logo image and fix RTL direction in account emails
- **emails**: use hosted logo image and fix RTL direction in account emails
- **emails**: render allauth account emails as branded HTML

### Refactor

- **auth**: remove legacy authentication endpoints and associated tests covered by ENABLE_ALLAUTH as it fully rolled out (#392)

## v0.10.3 (2026-08-02)

### Fix

- restore Cloudflare Origin CA cert config, fix bind-mount drift

## v0.10.2 (2026-08-02)

### Fix

- forward real client IP (Cf-Connecting-Ip) to Django, not Cloudflare's edge IP

## v0.10.1 (2026-08-02)

### Fix

- switch gunicorn to sync WSGI/gthread workers with bounded concurrency

## v0.10.0 (2026-07-22)

### Feat

- **reciters**: make reciters list public and add detail endpoint
- **assets**: add reciter field and reciter_id filter to public assets API

## v0.9.0 (2026-07-06)

### Feat

- add reciter slug support in recitations API and update tests accordingly

## v0.8.0 (2026-07-02)

### Feat

- increase throttle rates for public API users and anonymous clients

## v0.7.4 (2026-07-01)

### Perf

- move ayah timing sort to DB and scale gunicorn workers (#387)

## v0.7.3 (2026-07-01)

### Perf

- batch Mixpanel tracking via Redis buffer (#386)

## v0.7.2 (2026-07-01)

### Perf

- pre-serialized response cache for /recitations endpoint (#385)

## v0.7.1 (2026-07-01)

### Perf

- skip DB on cache hit in recitation tracks endpoint (#384)

## v0.7.0 (2026-06-30)

### Feat

- add structured logging for throttled requests with user/client context

## v0.6.2 (2026-06-30)

### Fix

- Caddy rewrite for missing trailing slash on /recitations/{id} (#383)

## v0.6.1 (2026-06-30)

### Fix

- cap page_size at 50 on public recitations endpoint (#382)

## v0.6.0 (2026-06-30)

### Feat

- implement global per-client throttling for public API with user and anonymous rate limits

## v0.5.0 (2026-06-29)

### Feat

- allow adding riwayah and qiraah for normal assets, i.e. fonts, mushafs, etc...

## v0.4.0 (2026-06-29)

### Feat

- allow adding riwayah and qiraah for normal assets, i.e. fonts, mushafs, etc...

## v0.3.3 (2026-06-21)

### Fix

- use PgBouncer port 25061 for prod DB in CI env generation
- use PgBouncer port 25061 for prod DB in CI env generation

## v0.3.2 (2026-06-21)

### Fix

- remove DB_POOL_HOST override causing Unix socket fallback

## v0.3.1 (2026-06-21)

### Fix

- set CONN_MAX_AGE=0 for PgBouncer transaction mode
- set CONN_MAX_AGE=0 for PgBouncer transaction mode

## v0.3.0 (2026-06-18)

### Feat

- add readonly fields for created_at and updated_at in admin list display
- Add Service for setting permissions, and for Groups and choosing permissions

### Fix

- **release**: verify gemini ai release notes generation
- **ci**: correct sentry deploys new syntax for v2 cli
- **ci**: register sentry production deployment after release
- **ci**: include commits in fallback release notes when Gemini API unavailable
- **ci**: trigger BE release notification to verify Slack integration
- **ci**: re-trigger version bump after removing branch naming check requirement
- **ci**: trigger version bump pipeline test
- store name when inviting publisher member (#367)
- remove db queries from track_api_task and guard it with no_db_queries context manager to prevent database queries in tasks

## v0.2.5 (2026-06-17)

### Fix

- **release**: verify gemini ai release notes generation

## v0.2.4 (2026-06-17)

### Fix

- **ci**: correct sentry deploys new syntax for v2 cli

## v0.2.3 (2026-06-17)

### Fix

- **ci**: register sentry production deployment after release

## v0.2.2 (2026-06-17)

### Fix

- **ci**: include commits in fallback release notes when Gemini API unavailable

## v0.2.1 (2026-06-17)

### Fix

- **ci**: trigger BE release notification to verify Slack integration

## v0.2.0 (2026-06-17)

### Feat

- near zero downtime by rolling 2 web containers
- generate english slugs even for arabic entries
- filter publishers in portal by x-tenant header and add new api portal/publishers/me/
- unify publisher_q
- filter all portal apis based upon the user's publisher
- allow access to session cookies by setting SESSION_COOKIE_HTTPONLY to False
- change social account email verification to optional
- enable verified email parameter for OAuth configuration
- enable automatic email authentication connection for social accounts
- use session instead of jwt (#327)
- limit recovery code to only once
- Add GitHub OAuth credentials for social login
- Add Google OAuth credentials for social login
- add tracing logs to all apis, services, and background tasks. apply f-string style
- add tracing logs to all apis, services, and background tasks. apply f-string style
- remove black from pyproject.toml because it is used in pre-commit-config
- use django-watchfiles for faster reload and efficient CPU usage
- add ayah_timings_url to recitation detail endpoint
- add ayah timing upload
- calculate file_size and add search for versions
- Add portal tafsir and translation versions and clean tests and APIs
- Add localization check to pipeline
- add ar localization
- raise ItqanError for ProtectedError
- raise ItqanError for ProtectedError
- make qiraah and riwayah optional in Recitation update and create
- add filters for riwayahs and qiraahs
- add filters for riwayahs and qiraahs
- Fix and change portal/reciters
- change license type to LicenseChoice
- add portal/translations api
- add portal/tafsirs api
- add portal/translations api
- add portal/tafsirs api
- add Reciter Creation API with CRUD endpoints
- add default sorting and additional fields to reciters
- add portal list publishers endpoint with filters and search
- add portal create publisher endpoint
- enhance publisher statistics functionality and improve cache handling
- implement publisher statistics endpoint and related tasks
- add retrieve, update, and delete publisher endpoints
- add portal list publishers endpoint with filters and search
- add portal create publisher endpoint
- add user authentication to recitation list tests
- enhance RecitationFilter with qiraah_id and additional search fields
- rebase and ix previous pr issues
- add more fields to publisher model
- **reciters**: search reciters API with pagination + full text
- add portal api and update docs
- address rabbit code comments
- remove the mention of develop branch and add migrate to uv
- use ManifestStaticFilesStorage for static files to avoid overwriting them on every deployment to speed deployment up
- use ManifestStaticFilesStorage for static files to avoid overwriting them on every deployment to speed deployment up
- Add bio Field for Riwayah
- change the riwayah to optional to reflect changes in the database
- add bio fields to qiraah model and update related schemas
- add external URL field to apis
- add external URL field and consistency constraint to resource model
- add external URL field and consistency constraint to resource model
- implement resource and asset service and send email for new versions
- update Qiraah and Riwayah handling, add qiraah field to admin and change categories endpoint
- add ContentIssueReport model and related functionality for issue reporting
- Introduce `is_external` field to the Resource model and integrate it across relevant APIs, tests, and the admin interface.
- Add more categories to support new design
- add qiraah to asset to support recitations that have multiple riwayahs
- add qiraahs in migrations, add qiraah filter
- add qiraahs/ endpoint
- add Qiraah model
- add reciter bio and image_url to admin
- add rewayahs/
- add repo and service layer for recitations
- fix test cases to abide by database constraints
- fix comments
- add saudi center apis
- add EMAIL_PORT default to env vars
- add email_backend to env vars
- disable ENABLE_ALLAUTH in env.example
- Add Templates for Django allauth to work as PoC
- Add ALLAUTH to handle Frontend authentication, forget password, MFA, et...  replaces simple_jwt
- add architecture and authentication documentation
- skip tests based on ENABLE_OAUTH2
- extend Oauth2 flags to hide the auth endpoints and applications endpoints
- add command to import per-ayah timings from JSON files
- implement Cloudflare R2 storage for all deployed environments
- add English names for reciters and riwayahs, and update admin interface for multilingual support
- relied on resource from qul.tarteel for surah info. enhance recitation apis with related and others fixes and enhancements
- implement oauth2
- add Oauth2 authentication
- add Sentry integration and configuration options closes #104
- Implement tests for Publisher middleware and resource domain filtering
- Add Publisher middleware and change the APIs to filter data according to HOST
- implement forced download for asset and resource files with presigned URLs
- add Sentry integration and configuration options closes #104
- add CI/CD workflow for testing and linting with Docker closes #100
- Update black python version and reorder imports (riwayahs_list)
- Add Riwayah listing endpoint (feature/riwayahs_list)
- Update black python version and reorder imports
- Update python version in pre-commit config (recitations-details)
- Add recitations listing endpoint (recitations-details)
- Add reciters listing endpoint (develop)
- remove optional authentication for asset and resource detail endpoints and update validation for resource name
- update asset and resource models to allow optional thumbnail URLs and simplify IP address retrieval
- create usage events for resource views and downloads
- implement usage event creation for asset downloads
- add usage_event when asset_detail is used
- add description and title fields to assetpreview model + return snapshots to asset details api
- **serializers**: add license fields to PublisherSerializer to match with APIs contract
- **config**: add localhost:4200 to CORS_ALLOWED_ORIGINS for local development
- implement GHCR integration for develop environment only
- Add comprehensive schema safety protocol to prevent database mismatches
- implement Django admin cleanup to hide third-party models
- add deployment rules enforcement and pre-push hook
- improve deployment and OAuth configuration
- fix registration role requirement and add Postman collection
- add staging environment configuration

### Fix

- **ci**: re-trigger version bump after removing branch naming check requirement
- **ci**: trigger version bump pipeline test
- create recitation json file after finishing upload
- translations with wrrong keys
- add filter_reciter_names for mixpanel fields
- admin fields
- upload image in the reciter api patch
- RawPostDataException because oauth toolkit is accessing body prematurly
- usage tracking tests
- handle ClientError during multipart upload initiation to R2 (#337) (#338)
- add annotation to AbsoluteUrl
- handle ClientError during multipart upload initiation to R2 (#337)
- fix reutrning mixpanel_board_url
- fix creating users in mixpanel
- fix creating users in mixpanel
- add username to mixpanel mapping
- add headless-spec
- override create identity
- override create identity
- override create identity
- get mixpanel url dynamically
- remove silk and make sure dev deps dont download on staging
- fix SamlProcessor
- check saml entity of mixpanel
- check saml entity of mixpanel
- accepting POST redirection from mixapanel
- parsing certificate and key
- social login emails verified
- Widen session/CSRF cookie domain for staging OAuth callbacks
- Fix null defaults across the project
- Publisher.description should be nullable
- remove DatabaseScheduler and rely on default Celery's PersistentScheduler
- some fields are optional in DB but not optional in API, this commit fixes this
- handle null in translated fields
- multiple fixes for is_external and external_url
- add language to tafsir and translation to be updated
- add missing fields
- Add portal/recitation apis
- Add portal/recitation apis
- add missing thumbnail_url from tafsir api and icon_url to publisher apis
- add qiraah and publisher to select_related in recitation list query
- replace deprecated .dict() with .model_dump() for Pydantic v2
- add max_length validation and 401 response docs
- address remaining CodeRabbit review comments
- align reciter tests with repo naming conventions and type hints
- make name_ar and name_en required for reciter creation
- address CodeRabbit round 2 review comments
- address CodeRabbit review comments on reciter API
- address code review feedback on publisher endpoints
- exclude empty countries from total countries count in publisher stats
- إصلاح ملاحظات CodeRabbit على PR #268
- move authenticate_user from setUp to individual test methods
- address CodeRabbit review feedback
- return recitations with combined riwayahs under one qiraah, but no single riwayah
- correct comment formatting in RecitationsListTest
- add type hint for setUp method in RecitationsListTest
- **reciters**: fix tests and lint issues
- **reciters**: address review comments + tests
- revert back static files changes
- ManifestStaticFilesStorage urls
- pre_populated fields
- fix test cases and pass filters to repo and service
- fix test cases and address code rabbit comments
- fix test cases and address code rabbit comments
- pagination bug
- test suite: resolve S3/storage configuration issues and refactor test structure closes #90
- GHCR authentication and repository access
- correct TARGET_BRANCH for workflow_dispatch and improve container cleanup
- improve pre-push hook validation logic
- update GitHub OAuth configuration for development environment
- remove duplicate OAuth APP configs in development.py
- configure GitHub OAuth for develop environment
- use development settings for develop env and add api.cms.itqan.dev to ALLOWED_HOSTS
- disable Redis and use dummy cache for develop environment
- add develop/staging domains to ALLOWED_HOSTS
- **prod**: wrap Sentry integration in ImportError guard
- entrypoint handles fake-initial migrations for accounts/admin
- **dev**: remove deprecated Sentry auto_enabling flags; log to /app/logs/django.log
- **prod**: remove deprecated Sentry auto_enabling flags; log to /app/logs/django.log
- Update deployment configuration for django-allauth

### Refactor

- move read operation
- standardize permission constants naming convention in permissions.py
- standardize permission constants naming convention in permissions.py
- simplify OAuth2 authentication flow and add end-to-end tests for OAuth2 workflow
- update test method names in RecitationsListTest for clarity
- **developers**: remove unused developer module files
- update user and organization models to use ImageField for avatar and icon URLs
- rename docker-compose.yml to docker-compose.develop.yml for clarity
- **entrypoint**: use migrate --fake-initial for simplicity
