# Itqan CMS - C4 Architecture Diagrams

This directory contains the complete C4 model architecture diagrams for the Itqan Quranic Content Management System.

## Technology Stack Overview
- **Frontend**: Angular 19 (CSR) with NG-ZORRO (Ant Design for Angular)
- **Backend**: Django 4.2 LTS + Wagtail CMS + Django REST Framework
- **Database**: PostgreSQL 16 with UUID primary keys
- **Search**: MeiliSearch v1.6 for Arabic-optimized full-text search
- **Cache/Queue**: Redis for caching and Celery task queue
- **Storage**: MinIO (dev) / Alibaba OSS (prod)
- **Authentication**: Auth0 (SPA SDK + OIDC/JWKS validation)
- **Infrastructure**: Docker Compose (dev) → DigitalOcean DOKS → Alibaba Cloud ACK

## Additional Diagrams
- `high-level-db-components-relationship.png` - Entity Relationship diagram showing core entities (User, Role, Resource, License, Distribution, AccessRequest, UsageEvent)
- `high-level-db-components-relationship.mmd` - Mermaid source for the ER diagram above
- `api-surface-overview.mmd` - Complete API surface design with Public, Developer, Publisher, and Admin endpoints

## C4 Model Overview

The C4 model provides a hierarchical way to think about and communicate software architecture through four levels of abstraction:

| Level | Name | Audience | Purpose |
|-------|------|----------|---------|
| **Level 1** | **System Context** | Stakeholders, Business Analysts, Everyone | Shows the Quranic CMS in its Islamic content ecosystem with users and external systems |
| **Level 2** | **Container** | Architects, Technical Leads | Shows Angular frontend, Django backend, and supporting services interaction |
| **Level 3** | **Component** | Developers, Technical Teams | Zooms into Django backend showing domain-driven apps and DRF architecture |
| **Level 4** | **Data Models** | Developers, Implementers | Shows complete database schema optimized for Quranic content management |

## Diagram Files

### [Level 1: System Context Diagram](./level1-system-context.md)
- **File**: `level1-system-context.md`
- **Shows**: Itqan CMS in the Islamic content ecosystem
- **Key Elements**: 
  - **Users**: Publishers (Islamic orgs), Developers (app builders), Administrators, Reviewers, End Users
  - **External Systems**: Auth0, Alibaba Cloud, DigitalOcean, Email Service, External Quranic APIs
  - **Focus**: Quranic content aggregation, licensing, and distribution workflows

### [Level 2: Container Diagram](./level2-container-diagram.md)
- **File**: `level2-container-diagram.md`
- **Shows**: Angular + Django architecture with supporting services
- **Key Elements**: 
  - **Frontend**: Angular 19 SPA with NG-ZORRO and Auth0 SPA SDK
  - **Backend**: Django 4.2 + Wagtail monolith with domain-driven apps
  - **Data Layer**: PostgreSQL, Redis, MeiliSearch, MinIO
  - **Background**: Celery workers for indexing and notifications

### [Level 3: Component Diagram](./level3-component-diagram.md)
- **File**: `level3-component-diagram.md`
- **Shows**: Internal structure of Django backend container
- **Key Elements**: 
  - **Django Apps**: Core, Accounts, Content, Licensing, Analytics, API (domain-driven)
  - **Wagtail Layer**: Admin interface, workflows, page management
  - **DRF Layer**: API views, serializers, permissions, pagination
  - **Services**: Auth, Content, License, Search, Notification services

### [Level 4: Data Models](./level4-data-models.md)
- **File**: `level4-data-models.md`
- **Shows**: Complete database schema for Quranic content management
- **Key Elements**: 
  - **Core Entities**: User, Role, Resource, License, Distribution, AccessRequest, UsageEvent
  - **Content Management**: ResourceRevision, MediaFile, SearchIndex
  - **CMS Integration**: ContentPage (Wagtail), RateLimit
  - **Islamic Content Features**: Multilingual support, content verification, scholarly review

## How to Use These Diagrams

### For Islamic Organizations & Publishers
Start with **Level 1** to understand:
- How to publish and manage Quranic content
- Licensing and access control workflows
- Integration with existing Islamic content systems
- Revenue opportunities through licensed content distribution

### For App Developers & API Consumers
Focus on **Level 1 & 2** to understand:
- How to request access to Quranic content APIs
- Available content formats (REST, GraphQL, download packages)
- Authentication flow via Auth0
- Rate limiting and usage analytics

### for Architects and Technical Leads
Use **Level 2 & 3** to understand:
- Angular 19 + Django 4.2 architecture decisions
- Microservices data layer with monolithic application layer
- Auth0 integration patterns (SPA SDK + OIDC validation)
- Scalability path: DigitalOcean → Alibaba Cloud migration
- Background processing with Celery for search indexing

### For Development Teams
Reference **Level 3 & 4** for:
- Domain-driven Django app organization
- Django REST Framework patterns and conventions
- Wagtail CMS integration for editorial workflows
- MeiliSearch integration for Arabic-optimized search
- Database schema with Islamic content considerations

## Architecture Principles

The Itqan CMS architecture follows these key principles tailored for Islamic content management:

### Content Authenticity & Integrity
- **Checksum Verification**: SHA-256 hashes for Quranic text and audio integrity
- **Scholarly Review**: Wagtail workflows for Islamic scholar content approval
- **Version Control**: Complete revision history for all content changes
- **Source Tracking**: Integration with verified Islamic content APIs

### Multilingual & Cultural Support
- **Arabic-First Design**: Native Arabic support with RTL layout
- **Linguistic Accuracy**: MeiliSearch optimized for Arabic text search
- **Cultural Sensitivity**: Respect for Islamic content handling practices
- **Translation Management**: Support for multiple language translations

### Licensing & Access Control
- **Islamic Licensing**: Support for Islamic copyright and usage principles
- **Geographic Distribution**: Region-specific content licensing
- **Commercial vs. Non-Profit**: Flexible licensing for different use cases
- **Access Request Workflows**: Transparent approval processes

### Scalability for Global Islamic Community
- **Global CDN**: Alibaba Cloud for worldwide content delivery
- **Multi-Region Support**: Database and storage replication
- **High Availability**: Kubernetes deployment for reliability
- **Performance Optimization**: Caching strategies for high-traffic Islamic apps

### Developer Experience
- **Clear API Design**: RESTful APIs following OpenAPI 3.0 specification
- **Comprehensive Documentation**: Detailed guides for Islamic app developers
- **SDK Support**: Future SDKs for popular mobile development frameworks
- **Community Support**: Open channels for developer assistance

## Islamic Content Management Features

### Quranic Text Management
- **Precision Handling**: Character-level accuracy for Arabic text
- **Multiple Recitations**: Support for different Qira'at (recitation styles)
- **Tajweed Integration**: Markup support for Tajweed rules
- **Cross-Referencing**: Verse-level linking and citation systems

### Audio Content
- **High-Quality Storage**: Lossless audio formats for recitations
- **Metadata Management**: Reciter information, Tajweed style, speed
- **Streaming Optimization**: Efficient delivery for mobile applications
- **Synchronization**: Text-audio alignment for educational apps

### Translation & Commentary
- **Multiple Languages**: Support for translations in various languages
- **Scholarly Commentary**: Tafsir integration with proper attribution
- **Historical Context**: Support for classical and contemporary interpretations
- **Cross-References**: Hadith and other Islamic text connections

## Related Documentation

- [C4 Model Levels Reference](../C4-Model-Levels.md) - Overview of C4 model levels and audiences
- [Business Requirements](../Itqan_CMS_BRS.md) - Detailed business requirements for Islamic content management
- [API Documentation](../api/openapi-spec.yaml) - Complete OpenAPI 3.0 specification
- [Database Schema](./high-level-db-components-relationship.mmd) - Mermaid ER diagram source
- [Task Management](../../ai-memory-bank/) - Development tasks and progress tracking

## Contributing to Architecture

When proposing architecture changes, please:
1. **Update Relevant Diagrams**: Ensure C4 model consistency across levels
2. **Consider Islamic Requirements**: Respect content authenticity and cultural sensitivity
3. **Maintain Scalability**: Design for global Islamic community scale
4. **Document Decisions**: Update this README with architectural reasoning
5. **Review with Community**: Engage Islamic scholars for content-related changes