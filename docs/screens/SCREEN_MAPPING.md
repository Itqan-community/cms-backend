# Itqan CMS - Screen Mapping & Requirements

## Canonical Screen Names

| Screen ID | Screen Name | Description | Related Tasks |
|-----------|-------------|-------------|---------------|
| **REG-001** | Registration Page | Redirect to Auth0 Hosted Universal Login with GitHub SSO priority | Task 1 |
| **REG-002** | Email Verification | "Check your email" confirmation with resend option | Task 2 |
| **AUTH-001** | Login Page | Redirect to Auth0 Hosted Universal Login with social providers | Task 3 |
| **AUTH-002** | Token Exchange | Loading/redirect state during Auth0→Strapi token exchange | Task 4 |
| **DASH-001** | Empty Dashboard | First-time user dashboard with profile completion checklist | Task 5 |
| **ADMIN-001** | Media Library | Strapi admin media upload interface with MinIO integration | Task 7 |
| **ADMIN-002** | Search Config | Meilisearch configuration panel in Strapi admin | Task 8 |
| **ADMIN-003** | Content Forms | Article/Page creation forms with EN/AR locale switcher | Task 9 |
| **ADMIN-004** | Workflow Panel | Draft→Review→Publish status buttons and timeline | Task 10 |
| **ADMIN-005** | Roles Settings | RBAC role matrix with permissions toggles | Task 11 |
| **ADMIN-006** | API Management | Developer API key generation and rate limit settings | Task 12 |
| **ADMIN-007** | Email Templates | Email template editor with EN/AR bilingual support | Task 16 |
| **ADMIN-008** | Admin Branding | Customized Strapi login and dashboard with Itqan theme | Task 17 |
| **PUB-001** | Article List | Public article listing with pagination and category filters | Task 13 |
| **PUB-002** | Article Detail | Individual article page with SEO and social sharing | Task 13 |
| **PUB-003** | Search Integration | Search box embedded in article list page | Task 14 |
| **SEARCH-001** | Search Results | Dedicated /search page with faceted filters and instant results | Task 14 |
| **LIC-001** | License Modal | Modal blocking API access until developer accepts license terms | Task 15 |

## Design System

### Color Scheme (from logo.svg)
- **Primary Green**: `#669B80` (rgb(102,155,128))
- **Dark Green**: `#22433D` (rgb(34,67,61))
- **Text**: Dark green on light backgrounds
- **Accent**: Primary green for buttons and links

### Typography
- Headers: Bold, dark green
- Body: Standard weight, good contrast
- RTL Support: Proper Arabic font stack

### Authentication Approach
- **Auth0 Hosted Universal Login** (Option A selected)
- Users redirect to Auth0 domain for authentication
- No embedded login widgets on Itqan domain

### Authentication Priority
1. **GitHub SSO** (primary)
2. Google OAuth (secondary)
3. Email/password (fallback)

## Screen Requirements by Feature

### Registration & Authentication (REG-*, AUTH-*)
- Auth0 Universal Login hosted pages
- GitHub SSO prominently displayed
- Consistent branding with Itqan colors
- Mobile-responsive design
- Arabic/English language support

### Dashboard (DASH-*)
- Bootstrap responsive layout
- Sidebar navigation with Itqan branding
- Profile completion checklist
- Empty state with clear next actions
- RTL layout support for Arabic users

### Admin Interface (ADMIN-*)
- Strapi admin customization with Itqan theme
- Dark green header with logo
- Bilingual EN/AR support
- Workflow status indicators
- Mobile-friendly admin panels

### Public Pages (PUB-*)
- Bootstrap responsive design
- SEO-optimized meta tags
- Social sharing buttons
- Article cards with featured images
- Pagination and category filtering
- Search integration

### Search (SEARCH-*)
- InstantSearch.js integration
- Real-time search results
- Faceted filtering (category, tags, date)
- Bilingual search support
- Mobile-optimized interface

### Licensing (LIC-*)
- Modal overlay blocking interaction
- Clear license terms display
- Accept/Decline buttons
- Legal compliance features
- Progress tracking for multiple licenses
