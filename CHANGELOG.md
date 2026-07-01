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
