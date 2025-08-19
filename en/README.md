# English Wireframes for Itqan CMS

This directory contains English versions of all Itqan CMS wireframes, converted from the original Arabic designs.

## Files Created

### HTML Wireframes
1. **create_english_wireframes.html** - Registration, authentication, and dashboard screens
2. **admin_wireframes.html** - Media library, search config, and content forms
3. **public_and_workflow_wireframes.html** - Workflow management, permissions, and public pages
4. **final_wireframes.html** - API management, email templates, branding, and search functionality

### Conversion Tools
- **convert_to_images.js** - Automated PNG generation script (requires Puppeteer)
- **README.md** - This documentation file

## Screen Mapping

The English wireframes correspond to the following canonical screen IDs:

### Authentication & Registration
- **REG-001** - Registration Page (Create Account form)
- **REG-002** - Email Verification (Check your email confirmation)
- **AUTH-001** - Login Page (GitHub/Google SSO + email/password)
- **AUTH-002** - Token Exchange (Loading state during Auth0→Strapi)

### Dashboard
- **DASH-001** - Empty Dashboard (Welcome screen with profile completion)

### Admin Interface
- **ADMIN-001** - Media Library (File upload and management)
- **ADMIN-002** - Search Configuration (Meilisearch settings)
- **ADMIN-003** - Content Forms (Article creation with EN/AR locale)
- **ADMIN-004** - Workflow Panel (Draft→Review→Publish management)
- **ADMIN-005** - Roles Settings (RBAC permission matrix)
- **ADMIN-006** - API Management (Key generation and rate limiting)
- **ADMIN-007** - Email Templates (Bilingual email editor)
- **ADMIN-008** - Admin Branding (Logo, colors, and customization)

### Public Pages
- **PUB-001** - Article List (Public content listing with filters)
- **PUB-002** - Article Detail (Individual article view with sharing)
- **PUB-003** - Search Integration (Search box embedded in article list)

### Search & Licensing
- **SEARCH-001** - Search Results (Dedicated search page with faceted filters)
- **LIC-001** - License Modal (API access license agreement)

## Key Design Changes from Arabic to English

### Layout Adjustments
- **Text Direction**: Changed from RTL (Right-to-Left) to LTR (Left-to-Right)
- **Navigation**: Moved navigation elements to conventional English positions
- **Form Labels**: Repositioned form labels and inputs for LTR reading pattern

### Content Translation
- **User Interface**: Translated all UI elements, buttons, and navigation
- **Sample Content**: Replaced Arabic content with English equivalents
- **Form Fields**: Updated placeholder text and field labels
- **Error Messages**: Translated validation and system messages

### Brand Consistency
- **Colors**: Maintained Itqan brand colors (#669B80 primary, #22433D secondary)
- **Typography**: Used English font stacks while preserving hierarchy
- **Logo Placement**: Consistent with English reading patterns

### Authentication Flow
- **GitHub SSO Priority**: Maintained GitHub as primary authentication method
- **Auth0 Integration**: Preserved Hosted Universal Login approach
- **Social Providers**: Google OAuth as secondary option

### Content Management
- **Bilingual Support**: Forms include EN/AR language switchers
- **Workflow States**: Translated Draft→Review→Publish status indicators
- **Permission Labels**: English RBAC role and permission names

## Converting to PNG Images

### Automated Method (Recommended)
```bash
cd en/
npm install puppeteer
node convert_to_images.js
```

### Manual Method
1. Open each HTML file in a web browser
2. Use browser developer tools to select individual wireframe sections
3. Take screenshots of each `#SCREEN-ID` element
4. Save as `SCREEN-ID-EN.png`

### Expected Output
After conversion, you should have 18 PNG files:
- REG-001-EN.png, REG-002-EN.png
- AUTH-001-EN.png, AUTH-002-EN.png  
- DASH-001-EN.png
- ADMIN-001-EN.png through ADMIN-008-EN.png
- PUB-001-EN.png, PUB-002-EN.png, PUB-003-EN.png
- SEARCH-001-EN.png, LIC-001-EN.png

## Technical Notes

### Bootstrap Framework
- Uses Bootstrap 5.3.0 for consistent responsive design
- Custom CSS variables for Itqan brand colors
- Component classes match planned implementation

### Responsive Design
- Mobile-first approach with Bootstrap grid system
- Breakpoints: sm (576px), md (768px), lg (992px), xl (1200px)
- Admin panels optimized for desktop (minimum 1024px width)

### Accessibility
- Proper semantic HTML structure
- ARIA labels and descriptions where appropriate
- Color contrast meets WCAG guidelines
- Keyboard navigation support

### Integration Ready
- CSS classes match planned component structure
- Form field names align with API specifications
- Button actions correspond to user stories in tasks/

## Usage in Development

These wireframes serve as:
1. **Design Reference** - Visual guide for frontend implementation
2. **User Story Validation** - Screens match acceptance criteria in task JSON files
3. **Responsive Testing** - Layout behavior across different screen sizes
4. **Accessibility Baseline** - Semantic structure for screen readers

## Next Steps

1. Convert HTML wireframes to PNG images
2. Review with stakeholders for design approval
3. Use as reference during Sprint 1 implementation
4. Update based on user feedback during development

---

*Generated for Itqan CMS MVP Development*  
*Maintains consistency with Arabic originals while optimizing for English users*
