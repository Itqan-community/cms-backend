# Level 4: Data Models - Itqan CMS Database Schema

**Audience:** Developers, Implementers  
**Purpose:** Shows class-level/code structure and database schema for implementation.

```mermaid
erDiagram
    %% Core Content Entities
    User {
        uuid id PK
        string email UK
        string username UK
        string password_hash
        string first_name
        string last_name
        enum role
        boolean is_active
        timestamp created_at
        timestamp updated_at
        timestamp last_login
    }
    
    Content {
        uuid id PK
        string title
        string slug UK
        text body
        text excerpt
        enum status
        enum content_type
        uuid author_id FK
        uuid category_id FK
        json metadata
        timestamp published_at
        timestamp created_at
        timestamp updated_at
        integer view_count
        boolean is_featured
    }
    
    Category {
        uuid id PK
        string name UK
        string slug UK
        text description
        uuid parent_id FK
        string color
        integer sort_order
        boolean is_active
        timestamp created_at
        timestamp updated_at
    }
    
    Tag {
        uuid id PK
        string name UK
        string slug UK
        text description
        string color
        integer usage_count
        timestamp created_at
        timestamp updated_at
    }
    
    ContentTag {
        uuid content_id FK
        uuid tag_id FK
        timestamp created_at
    }
    
    Media {
        uuid id PK
        string filename
        string original_name
        string mime_type
        integer file_size
        string file_path
        json metadata
        uuid uploaded_by FK
        timestamp created_at
        timestamp updated_at
    }
    
    ContentMedia {
        uuid content_id FK
        uuid media_id FK
        enum usage_type
        integer sort_order
        timestamp created_at
    }
    
    Comment {
        uuid id PK
        uuid content_id FK
        uuid user_id FK
        uuid parent_id FK
        text body
        enum status
        string author_name
        string author_email
        timestamp created_at
        timestamp updated_at
    }
    
    ContentRevision {
        uuid id PK
        uuid content_id FK
        uuid created_by FK
        json content_data
        string change_summary
        timestamp created_at
    }
    
    Permission {
        uuid id PK
        string name UK
        string description
        string resource
        string action
        timestamp created_at
    }
    
    UserPermission {
        uuid user_id FK
        uuid permission_id FK
        timestamp granted_at
        uuid granted_by FK
    }
    

    
    %% Relationships
    User ||--o{ Content : "authors"
    User ||--o{ Media : "uploads"
    User ||--o{ Comment : "writes"
    User ||--o{ ContentRevision : "creates"
    User ||--o{ UserPermission : "has"
    
    Content ||--o{ ContentTag : "has"
    Content ||--o{ ContentMedia : "includes"
    Content ||--o{ Comment : "receives"
    Content ||--o{ ContentRevision : "versioned"
    Content }o--|| Category : "belongs_to"
    
    Category ||--o{ Category : "parent_child"
    
    Tag ||--o{ ContentTag : "tagged"
    
    Media ||--o{ ContentMedia : "used_in"
    
    Comment ||--o{ Comment : "parent_child"
    
    Permission ||--o{ UserPermission : "granted"
```

## Entity Descriptions

### Core Entities

#### User
- **Purpose**: Represents system users (authors, editors, admins)
- **Key Fields**: 
  - `role`: ENUM (admin, editor, author, subscriber)
  - `is_active`: Soft delete mechanism
- **Indexes**: email, username, role, is_active

#### Content
- **Purpose**: Main content entity (articles, pages, posts)
- **Key Fields**:
  - `status`: ENUM (draft, published, archived, deleted)
  - `content_type`: ENUM (article, page, post, product)
  - `metadata`: JSON field for flexible content properties
- **Indexes**: slug, status, content_type, published_at, author_id, category_id

#### Category
- **Purpose**: Hierarchical content organization
- **Key Fields**:
  - `parent_id`: Self-referencing for hierarchy
  - `sort_order`: Manual ordering within same level
- **Indexes**: slug, parent_id, is_active, sort_order

#### Tag
- **Purpose**: Non-hierarchical content labeling
- **Key Fields**:
  - `usage_count`: Denormalized count for performance
- **Indexes**: slug, usage_count

### Media Management

#### Media
- **Purpose**: File and asset management
- **Key Fields**:
  - `metadata`: JSON field for EXIF, dimensions, alt text
  - `file_path`: Relative path in storage system
- **Indexes**: mime_type, uploaded_by, created_at

#### ContentMedia
- **Purpose**: Links content to media assets
- **Key Fields**:
  - `usage_type`: ENUM (featured, gallery, inline, thumbnail)
  - `sort_order`: Order within content
- **Indexes**: content_id, usage_type

### Engagement Features

#### Comment
- **Purpose**: User comments on content
- **Key Fields**:
  - `parent_id`: Threaded comments support
  - `status`: ENUM (pending, approved, spam, deleted)
  - `author_name/email`: For non-registered users
- **Indexes**: content_id, status, parent_id

#### ContentRevision
- **Purpose**: Version control for content changes
- **Key Fields**:
  - `content_data`: Complete content snapshot as JSON
  - `change_summary`: Human-readable description
- **Indexes**: content_id, created_at

### Access Control

#### Permission
- **Purpose**: Granular permission definitions
- **Key Fields**:
  - `resource`: What (content, user, media)
  - `action`: How (create, read, update, delete)
- **Indexes**: name, resource

#### UserPermission
- **Purpose**: Many-to-many user permissions
- **Key Fields**:
  - `granted_at`: Audit trail
  - `granted_by`: Who granted permission
- **Indexes**: user_id, permission_id



## Database Considerations

### Performance
- **UUID Primary Keys**: Better for distributed systems and security
- **Strategic Indexes**: On frequently queried columns
- **JSON Fields**: For flexible metadata without schema changes

### Data Integrity
- **Foreign Key Constraints**: Enforce referential integrity
- **Unique Constraints**: Prevent duplicates (email, username, slugs)
- **Soft Deletes**: Use status flags instead of hard deletes

### Scalability
- **Normalized Design**: Reduces data redundancy
- **Denormalized Counters**: usage_count, view_count for performance
- **Partitioning Ready**: Timestamps support date-based partitioning
