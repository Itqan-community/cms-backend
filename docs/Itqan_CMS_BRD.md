# Business Requirements Document (BRD)  
## Project: Itqan Qur’anic Content Management System (CMS)  
**Version:** 1.0  
**Date:** August 2025  
**Prepared by:** Itqan Community  

---

## 1. Introduction  
This BRD outlines the detailed requirements for the Itqan CMS. The CMS is intended to provide standardized, developer-friendly access to verified Qur’anic content (text, tafsir, translations, audio) with proper licensing.  

---

## 2. Project Objectives  
- Deliver a **centralized CMS platform** that aggregates Qur’anic content.  
- Provide **secure, scalable APIs** for developers.  
- Establish **licensing workflows** to ensure compliance with publishers.  
- Enable **scholarly review processes** to maintain authenticity.  
- Support **open-source contribution and collaboration**.  

---

## 3. Functional Requirements  

### 3.1 User Management  
- Users can register using **email** or **OAuth (Google, GitHub)**.  
- Role-based access control: **Admin, Publisher, Developer, Reviewer**.  
- Users can update profiles with **name, institution, business model, team size**.  

### 3.2 Content Management  
- Publishers can upload Qur’anic resources (text, tafsir, translations, audio).  
- System validates format (JSON/XML/MP3/ZIP) and verifies integrity (checksums).  
- Content tagged with metadata: **language, narration, version, format**.  
- Resources maintain version history (immutable storage).  

### 3.3 Licensing & Permissions  
- Publishers define licensing terms for each resource.  
- Developers must **accept license agreements** before API use.  
- Licensing constraints: **geography, usage limits, attribution**.  
- License registry maintains all approved and rejected grants.  

### 3.4 APIs for Developers  
- **Resource API:** access Qur’anic content (text, tafsir, translations).  
- **Discovery API:** search across resources using language/metadata filters.  
- **Authentication:** API keys tied to user accounts with scopes.  
- **Rate limiting:** protect against abuse.  

### 3.5 Search & Indexing  
- Indexes built automatically after ingestion.  
- Full-text search across Qur’anic content and metadata.  
- Query service for developers with response under **200ms** for typical queries.  

### 3.6 Review & Approval Workflow  
- Submissions undergo validation and scholarly review.  
- Reviewers can **approve/reject** content.  
- Audit logs track all changes.  

### 3.7 Notifications  
- Email confirmations for registration, approvals, license requests.  
- Webhooks for publishers (content status updates).  

---

## 4. Non-Functional Requirements  

- **Security:**  
  - All endpoints require HTTPS.  
  - Authentication: OAuth2, API keys, RBAC.  
  - Logs stored for audit and compliance.  

- **Performance:**  
  - 99.9% API uptime SLA.  
  - Queries return in under 200ms.  
  - System scales to 10M+ requests/month.  

- **Usability:**  
  - Intuitive web portal for publishers and admins.  
  - Developer-friendly API documentation.  

- **Compliance:**  
  - Data must comply with scholarly standards.  
  - Infrastructure must comply with **POPIA/GDPR** where relevant.  

---

## 5. Assumptions  
- Publishers will cooperate in providing digital rights.  
- Developers will adopt the CMS if APIs are simple and reliable.  
- Funding for hosting is sustained via endowments/donations.  

---

## 6. Constraints  
- Limited internal technical resources initially.  
- Dependencies on third-party providers (OAuth, email).  
- Reliance on cloud infrastructure for global scale.  

---

## 7. Dependencies  
- Verified Qur’anic datasets (text, tafsir, translations, audio).  
- Publisher agreements and licensing compliance.  
- Identity provider integrations (Google, GitHub).  

---

## 8. Acceptance Criteria  
- **MVP Success:**  
  - Qur’anic text + at least 2 translations available via API.  
  - Licensing flow functional.  
  - Minimum 5 publishers onboarded.  
  - Minimum 20 developers actively using API.  

- **Extended Success:**  
  - Audio, tafsir, and advanced metadata integrated.  
  - Performance meets SLA.  
  - Documented scholarly review process in place.  

---

## 9. Appendices  

### 9.1 Glossary  
- **CMS:** Content Management System.  
- **API:** Application Programming Interface.  
- **RBAC:** Role-Based Access Control.  

### 9.2 References  
- Itqan Strategic Plan (1447H).  
- PRD Release 1 – v0.3 (MVP Initial).  

---
