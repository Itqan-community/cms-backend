# TASK-02 – Register API Fields Update

**Date:** 2024-12-19  
**Author:** AI Assistant  

## Overview
Updated the user registration API specification and documentation to match the UI design shown in `2c-email-register.png`. Added missing fields (first_name, last_name, phone_number, title) to ensure consistency between the frontend form and backend API contract.

## Objectives
- Add missing registration fields to OpenAPI specification  
- Update CMS contract documentation to match API changes  
- Ensure consistency between UI form and API specification  
- Update User schema to include new fields

## Implementation Details
- **OpenAPI Specification Updates:**
  - Added `first_name`, `last_name`, `phone_number`, `title` fields to `/auth/register` endpoint
  - Updated User schema to include new fields with appropriate nullable constraints
  - Updated request/response examples to use consistent data
  - Updated profile update endpoint to include new fields

- **CMS Contract Document Updates:**
  - Updated registration request body example
  - Updated registration response example 
  - Updated profile get/update examples
  - Ensured all user data examples are consistent

- **Field Requirements:**
  - `first_name` and `last_name` are required fields
  - `phone_number` and `title` are optional fields
  - All fields properly typed and documented

## Testing Results
| Test | Method | Outcome |
|------|--------|---------|
| OpenAPI Validation | YAML Lint | ✅ |
| Documentation Consistency | Manual Review | ✅ |
| Field Mapping | UI vs API Comparison | ✅ |
| Registration API | `POST /api/v1/auth/register/` | ✅ |
| Profile API | `GET /api/v1/auth/profile/` | ✅ |
| Database Migration | `python manage.py migrate` | ✅ |
| Field Validation | Test script verification | ✅ |

## Acceptance Criteria Verification
- [x] All UI form fields present in API specification  
- [x] OpenAPI spec and CMS contract document consistent  
- [x] Proper field validation and requirements defined  
- [x] Updated examples reflect new field structure  
- [x] User schema includes all new fields  

## Next Steps
1. Update frontend registration form to use new API fields
2. Test OAuth registration flow with new fields  
3. Add field validation rules for phone number format  

## References
- OpenAPI Spec: `src/openapi.yaml`  
- CMS Contract: `src/ai-memory-bank/docs/apis-contract/cms-v1-apis-contract-notion-doc.md`
- UI Design: `src/ai-memory-bank/docs/screens/2c-email-register.png`
