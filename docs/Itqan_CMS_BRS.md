# Business Requirements Specification (BRS)  
## Project: Itqan Qur’anic Content Management System (CMS)  
**Version:** 1.0  
**Date:** August 2025  
**Prepared by:** Itqan Community  

---

## 1. Introduction  
The Itqan Qur’anic CMS project aims to establish a structured and reliable platform for aggregating, managing, and distributing Qur’anic digital resources. It addresses the current fragmentation in Qur’anic data sources and the lack of standardized, developer-friendly access to verified content.  

---

## 2. Purpose  
The purpose of this project is to:  
- Provide a unified platform for **Qur’anic content aggregation**.  
- Enable **verified, open-source, and licensed** resources for developers, researchers, and institutions.  
- Reduce duplication of efforts by offering **ready-to-use APIs, datasets, and libraries**.  
- Support the long-term mission of Itqan to **advance Qur’anic technologies** globally.  

---

## 3. Business Objectives  
- **Accessibility:** Make Qur’anic content easily accessible in reliable, developer-ready formats.  
- **Standardization:** Establish common standards for Qur’anic data, including text, audio, tafsir, translations, and metadata.  
- **Efficiency:** Eliminate inefficiencies caused by fragmented data and lack of interoperability.  
- **Collaboration:** Strengthen cooperation between developers, publishers, researchers, and institutions.  
- **Impact:** Empower global Muslim communities with innovative Qur’anic applications.  

---

## 4. Scope  
### In-Scope  
- Aggregation of Qur’anic content (text, tafsir, audio, translations).  
- Licensing and permissions management.  
- Development of a **Qur’anic Content API**.  
- Providing **developer tools** (SDKs, documentation, sandbox).  
- Open-source contributions and community participation.  

### Out-of-Scope  
- End-user mobile apps or products.  
- Non-Qur’anic religious content.  
- Direct publishing without partner verification.  

---

## 5. Stakeholders  
- **Primary Users:** Independent developers, Qur’anic app creators, researchers.  
- **Supporting Partners:** Publishers, Qur’an institutions, academic research centers.  
- **Sponsors:** Waqf institutions, donors, Islamic tech foundations.  
- **Internal Stakeholders:** Itqan Community leadership, technical teams, advisory boards.  

---

## 6. Business Requirements  
1. Provide a **central repository** of Qur’anic resources in digital formats.  
2. Ensure **licensing compliance** and respect intellectual rights of publishers.  
3. Offer **high-quality APIs** for content retrieval and integration.  
4. Guarantee **data authenticity and accuracy** through scholarly review.  
5. Enable **scalability** to serve global developers and institutions.  
6. Facilitate **community collaboration** via open-source projects.  
7. Deliver clear **metrics of success**: adoption rate, number of integrated apps, number of active developers.  

---

## 7. Success Criteria  
- **By Year 1:** Launch CMS v1.0 with verified Qur’anic text and translations available via API.  
- **By Year 2:** Onboard 20+ Qur’anic apps and 100+ developers using the CMS.  
- **By Year 3:** Expand to tafsir, audio, and advanced metadata; achieve measurable global adoption.  

---

## 8. Risks & Constraints  
- **Risks:**  
  - Limited funding may slow development.  
  - Resistance from traditional publishers to share digital rights.  
  - Fragmentation if global developers are not aligned.  

- **Constraints:**  
  - Must comply with **scholarly and Shariah standards**.  
  - Limited technical resources within initial Itqan setup.  
  - Dependence on sustainable hosting and infrastructure.  

---

## 9. Dependencies  
- Partnerships with Qur’an publishers and institutions.  
- Access to existing verified Qur’anic datasets.  
- Technical hosting infrastructure (cloud or hybrid).  
- Active community engagement for contributions.  

---

## 10. High-Level Data Model Overview
The CMS centres around seven core entities:

| Entity | Description | Key Relations |
|--------|-------------|---------------|
| **User** | Account representing developers, publishers, admins, reviewers | belongs-to **Role**; can act *as publisher* for Resources; submits **AccessRequest**s; generates **UsageEvent**s |
| **Role** | RBAC role (Admin, Publisher, Developer, Reviewer) | one-to-many Users |
| **Resource** | Any Qur'anic asset (text corpus, audio set, tafsir, translation) | owned by a Publisher (User); has many **License** records; exposed through **Distribution** endpoints |
| **License** | Legal terms attached to a Resource | many-to-one Resource; gate access for Developers |
| **Distribution** | Deliverable package/API endpoint for a Resource (e.g., REST JSON, audio zip) | many-to-one Resource; developers request via **AccessRequest** |
| **AccessRequest** | Developer's request to use a Distribution under a License | belongs to User (Developer) and Distribution; approval required |
| **UsageEvent** | Logged event each time an API/key consumes a Resource | belongs to User and Resource (or Distribution) |

See `docs/diagrams/high-level-db-components-relationship.png` for the full ER diagram.

---

## 11. Glossary  
- **CMS:** Content Management System.  
- **API:** Application Programming Interface.  
- **Itqan:** A global community initiative for advancing Qur’anic technologies.  

---

## 11. High-Level Data Model Overview
The CMS centres around seven core entities:
| Entity | Description | Key Relations |
|--------|-------------|---------------|
| **User** | Account representing developers, publishers, admins, reviewers | belongs-to **Role**; can act *as publisher* for Resources; submits **AccessRequest**s; generates **UsageEvent**s |
| **Role** | RBAC role (Admin, Publisher, Developer, Reviewer) | one-to-many Users |
| **Resource** | Any Qur’anic asset (text corpus, audio set, tafsir, translation) | owned by a Publisher (User); has many **License** records; exposed through **Distribution** endpoints |
| **License** | Legal terms attached to a Resource | many-to-one Resource; gate access for Developers |
| **Distribution** | Deliverable package/API endpoint for a Resource (e.g., REST JSON, audio zip) | many-to-one Resource; developers request via **AccessRequest** |
| **AccessRequest** | Developer’s request to use a Distribution under a License | belongs to User (Developer) and Distribution; approval required |
| **UsageEvent** | Logged event each time an API/key consumes a Resource | belongs to User and Resource (or Distribution) |

See `docs/diagrams/high-level-db-components-relationship.png` for the full ER diagram.

---

## 12. Approval  
**Project Sponsor:** [Name]  
**Project Owner:** Itqan Community Board  
**Date:** [To be signed]  

---
