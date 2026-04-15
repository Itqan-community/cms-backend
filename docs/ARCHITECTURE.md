# Itqan CMS — System Architecture

This document provides an overview of the Itqan CMS system architecture from a product perspective, showing the main components, their responsibilities, how they interact, and where the system boundaries lie.

---

## Overview

Itqan CMS is a **Quranic Content Management System** designed to help **Publishers** distribute high-quality, licensed content while enabling **Developers** to integrate it into their applications.

```mermaid
flowchart TB
    subgraph External["External Users"]
        DEV["Developers"]
        PUB["Publishers"]
        STAFF["Internal Staff"]
    end

    subgraph ItqanCMS["Itqan CMS Platform"]
        CMS_API["CMS API<br/>(Internal Frontend)<br/>cms-api/"]
        DEV_API["Public API<br/>(Developers' API)<br/>/"]
        TENANT_API["Tenant API<br/>(Publisher SaaS)<br/>tenant/"]
        PORTAL_API["Portal API<br/>(Admin CRUD)<br/>portal/"]
        CORE["Core System"]
    end

    DEV -->|"Create Account & OAuth Apps"| CMS_API
    DEV -->|"Consume Content (OAuth2)"| DEV_API
    PUB -->|"Branded Domain Access"| TENANT_API
    STAFF -->|"Upload & Manage Content"| PORTAL_API
    CMS_API --> CORE
    DEV_API --> CORE
    TENANT_API --> CORE
    PORTAL_API --> CORE
```

---

## User Types

The system serves **four distinct API surfaces**, each with their own audience and authentication mechanism:

| API | Mount | Purpose | Authentication |
|-----|-------|---------|----------------|
| **CMS API** (Internal) | `cms-api/` | Powers the frontend SPA. Users can create accounts, explore the platform, and create OAuth applications. | django-allauth (JWT), social login (Google/GitHub) |
| **Public API** (Developers') | `/` (root) | Public-facing API consumed by external developers using OAuth applications created via the CMS API. **Expected to receive the majority of traffic.** | django-oauth-toolkit (OAuth2 client credentials) |
| **Tenant API** | `tenant/` | Multi-tenant SaaS API for publishers. Each publisher can have their own domain; content is filtered by the `Domain` the request originates from. All tenants share a single database. | JWT/Session |
| **Portal API** | `portal/` | Internal admin portal for uploading, writing, updating, and managing content (full CRUD). All users are internal company staff. | JWT/Session + role-based permissions |

---

## Core Domain Models

The system is built around a hierarchy of content entities that ensure **authenticity**, **versioning**, and **controlled access**.

```mermaid
erDiagram
    Publisher ||--o{ Resource : "uploads"
    Publisher ||--o{ PublisherMember : "has members"
    User ||--o{ PublisherMember : "belongs to"

    Resource ||--o{ ResourceVersion : "has versions"
    Resource ||--o{ Asset : "derives"

    Asset ||--o{ AssetVersion : "has versions"
    AssetVersion }o--|| ResourceVersion : "linked to"

    Asset ||--o{ AssetAccessRequest : "receives"
    Asset ||--o{ AssetAccess : "grants"

    User ||--o{ AssetAccessRequest : "submits"
    User ||--o{ AssetAccess : "holds"
    User ||--o| Developer : "has profile"

    PUBLISHER {
        string name
        string slug
        string description
        boolean is_verified
    }

    RESOURCE {
        string name
        string category
        string license
        string status
    }

    RESOURCEVERSION {
        string semvar
        file storage_url
        int size_bytes
    }

    ASSET {
        string name
        string category
        string license
        string format
    }

    ASSETVERSION {
        file file_url
        int size_bytes
    }
```

---

## Component Responsibilities

### 1. Publisher

The **Publisher** represents an organization or individual who owns and uploads original content.

- Uploads **Resources** (original, unmodified content)
- Manages licensing terms for their content
- Can require approval for each usage request or enable auto-approval
- Has members with roles (Owner, Manager)

### 2. Resource

A **Resource** is the **original, authoritative content** uploaded by a Publisher. It acts as the **source of truth** and remains unmodified.

- Belongs to a single Publisher
- Has a **Category**: `recitation`, `mushaf`, or `tafsir`
- Has a **License** (Creative Commons variants)
- Has a **Status**: `draft` or `ready`

### 3. ResourceVersion

Each **ResourceVersion** represents a specific uploaded file of a Resource, enabling **version tracking**.

- Uses **semantic versioning** (e.g., `1.0.0`, `1.1.0`)
- Contains the actual file (`storage_url`)
- Tracks file size

### 4. Asset

An **Asset** is a **derivation** of a Resource. It represents content that has been adapted or transformed for specific use cases.

> **Example**: A publisher uploads a Tafsir as a PDF (Resource). A contributor then creates a JSON version of the same Tafsir for API consumption — this becomes an Asset derived from the original Resource.

- Linked to a parent Resource
- Inherits or specifies its own license
- Can have multiple preview images
- For recitation assets: linked to a **Reciter** and **Riwayah**

### 5. AssetVersion

Similar to ResourceVersion, **AssetVersion** tracks each uploaded file version of an Asset.

- Linked to both an Asset and a ResourceVersion
- Contains the actual downloadable file
- Enables tracking of which Asset version corresponds to which Resource version

---

## Content Lifecycle

```mermaid
flowchart LR
    subgraph Publisher Flow
        A["Upload Resource"] --> B["Create ResourceVersion<br/>(v1.0.0)"]
        B --> C["Set Status: Ready"]
    end

    subgraph Derivation Flow
        C --> D["Create Asset<br/>(Derived from Resource)"]
        D --> E["Create AssetVersion<br/>(linked to ResourceVersion)"]
    end

    subgraph Version Updates
        B -.->|"New version"| F["ResourceVersion<br/>(v1.1.0)"]
        E -.->|"New version"| G["AssetVersion<br/>(linked to v1.1.0)"]
    end
```

---

## Access Control Flow

Publishers control how developers access their content through a **request-approval** workflow.

```mermaid
sequenceDiagram
    participant Dev as Developer
    participant API as Developers API
    participant System as Itqan CMS
    participant Pub as Publisher

    Dev->>API: Request access to Asset
    API->>System: Create AssetAccessRequest

    alt Auto-Approve Enabled
        System->>System: Auto-approve request
        System->>Dev: Grant AssetAccess
    else Manual Approval Required
        System->>Pub: Notify: New access request
        Pub->>System: Review & Approve/Reject
        alt Approved
            System->>Dev: Grant AssetAccess
        else Rejected
            System->>Dev: Notify rejection
        end
    end

    Dev->>API: Download Asset (with valid access)
    API->>System: Log UsageEvent
    API->>Dev: Return file
```

### Access Request States

| Status | Description |
|--------|-------------|
| `pending` | Request submitted, awaiting review |
| `approved` | Access granted |
| `rejected` | Access denied by publisher |

---

## Developer API Access

Developers can create **OAuth2 applications** via the CMS frontend to access the public API programmatically.

**Key Points:**
- Register account via CMS frontend
- Create OAuth application at `/o/applications/`
- Receive `client_id` and `client_secret`
- Use client credentials flow to obtain access tokens
- Make authenticated API requests

**For complete OAuth flow diagrams, security best practices, and step-by-step guides, see [AUTHENTICATION.md](./AUTHENTICATION.md)**

---



## Distribution Channels

Assets can be distributed through multiple channels:

```mermaid
flowchart TB
    AV["AssetVersion"]

    AV --> D1["FILE_DOWNLOAD<br/>Direct file download"]
    AV --> D2["API<br/>Programmatic access"]
    AV --> D3["PACKAGE<br/>SDK/Library distribution"]
```

---

## Usage Tracking

The system tracks all interactions for analytics and auditing:

```mermaid
flowchart LR
    subgraph Events
        E1["View"]
        E2["File Download"]
        E3["API Access"]
    end

    subgraph Subjects
        S1["Resource"]
        S2["Asset"]
    end

    E1 & E2 & E3 --> UE["UsageEvent"]
    UE --> S1
    UE --> S2

    UE --> Stats["Analytics Dashboard"]
```

---

## System Boundaries

```mermaid
flowchart TB
    subgraph External
        Browser["CMS Frontend<br/>(Browser)"]
        DevApp["Developer Apps"]
        PubDomain["Publisher Domains"]
        AdminUI["Admin Portal"]
    end

    subgraph Itqan Platform
        subgraph APIs
            CMS["CMS API - cms-api/<br/>(django-allauth)"]
            PUB["Public API - /<br/>(OAuth2)"]
            TENANT["Tenant API - tenant/<br/>(JWT/Session)"]
            PORTAL["Portal API - portal/<br/>(JWT/Session + Permissions)"]
        end

        subgraph Core
            Models["Domain Models"]
            Services["Business Logic"]
        end

        subgraph Storage
            DB[(PostgreSQL)]
            Files[(Cloudflare R2 /<br/>Local Storage)]
        end

        subgraph Background
            Celery["Celery Workers"]
            Redis[(Redis)]
        end
    end

    Browser --> CMS
    DevApp --> PUB
    PubDomain --> TENANT
    AdminUI --> PORTAL
    CMS --> Models
    PUB --> Models
    TENANT --> Models
    PORTAL --> Models
    Models --> Services
    Services --> DB
    Services --> Files
    Services --> Celery
    Celery --> Redis
```

---

## Recitation-Specific Components

For recitation-type assets, the system provides specialized tracking:

```mermaid
erDiagram
    Asset ||--o{ RecitationSurahTrack : "contains"
    RecitationSurahTrack ||--o{ RecitationAyahTiming : "has timings"
    Asset }o--|| Reciter : "performed by"
    Asset }o--|| Riwayah : "follows"

    RECITER {
        string name
        string slug
    }

    RIWAYAH {
        string name
        string slug
    }

    RECITATIONSURAHTRACK {
        int surah_number
        file audio_file
        int duration_ms
    }

    RECITATIONAYAHTIMING {
        string ayah_key
        int start_ms
        int end_ms
    }
```

---

## Summary

| Component | Responsibility |
|-----------|---------------|
| **Publisher** | Content ownership and governance |
| **Resource** | Original, authoritative content |
| **ResourceVersion** | Version tracking for resources |
| **Asset** | Derived/transformed content for distribution |
| **AssetVersion** | Version tracking for assets |
| **AssetAccessRequest** | Developer access request workflow |
| **AssetAccess** | Granted access records |
| **Distribution** | Defines how assets are delivered |
| **UsageEvent** | Tracks all content interactions |

---

**See also:**
- [Authentication Guide](./AUTHENTICATION.md) — Complete OAuth flows and security practices
- [README.md](./README.md) — Quick start and project overview
