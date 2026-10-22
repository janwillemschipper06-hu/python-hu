> # ⚠️ SUPERSEDED — historical brainstorm only
>
> **This document is archived and no longer authoritative.** It was the initial planning
> brainstorm and now **contradicts** the current design. Do **not** implement from it. It still
> describes ideas that have since been replaced or removed, including: customer access
> tokens / invite links / OTP-PIN (replaced by Entra External ID), Azure Key Vault as the secret
> store (replaced by external-vault write-through — see `docs/adr/0001`), Blob storage / file /
> evidence uploads / malware scanning (removed — see `docs/architecture-design.md` §1.2), task
> dependencies and a `Blocked` status (removed — see `docs/architecture-design.md` §1.4), and six
> internal roles (reduced to two — see `docs/functional-design.md` §3).
>
> **Authoritative sources:** `CONTEXT.md`, `docs/adr/`, `docs/functional-design.md`,
> `docs/architecture-design.md`, `docs/api-design.md`, and `docs/security-design.md`.

# Microsoft Fabric Customer Onboarding Portal Plan

## 1. Goal

We want to create a secure web portal that helps customers prepare all requirements before a Microsoft Fabric solution can be installed.

Today, this preparation process is time-consuming because customers often skip instructions, miss details, or send sensitive information through insecure channels.

The portal should allow our company to:

- Create a new customer onboarding project.
- Select which requirements apply to that customer.
- Invite the customer to a secure web wizard.
- Guide the customer step by step.
- Track progress.
- Collect required values and evidence.
- Securely handle secrets, credentials, and sensitive information.
- Review and approve completed steps before starting the implementation.

The most important design principle is:

> Customers should have a low-friction onboarding experience, but sensitive information must be handled as write-only, strongly protected data.

---

## 2. High-Level Solution

The solution should consist of two main portals:

1. **Internal admin portal**
2. **Customer onboarding wizard**

### Internal Admin Portal

Used by our company to:

- Create customers.
- Create onboarding projects.
- Select required preparation tasks.
- Assign internal consultants.
- Configure due dates.
- Track progress.
- Review submitted information.
- Approve or reject completed steps.
- Access audit logs.
- Manage requirement templates.
- Revoke or regenerate customer access tokens.
- Manage submitted secret references.

### Customer Wizard Portal

Used by the customer to:

- Open their assigned wizard using a unique secure access token or access code.
- View only their assigned onboarding project.
- Follow step-by-step instructions.
- Enter required values.
- Upload evidence such as screenshots.
- Submit tasks for review.
- Securely provide secrets where absolutely required.
- Replace previously submitted sensitive values if needed.
- See which tasks are still open, blocked, submitted, or approved.

The customer should **not** be able to:

- View previously submitted secrets.
- View passwords.
- View client secrets.
- View API keys.
- View internal review notes.
- Access other customers or projects.
- Access admin functionality.

---

## 3. Customer Access Model

The customer should not be required to connect their tenant to our tenant or use B2B login.

Instead, the customer accesses their wizard using a **unique secure access token** that is scoped to one specific customer onboarding project.

### Recommended Flow

1. Internal admin creates a customer onboarding project.
2. The system generates a unique secure access token.
3. The customer receives a secure invitation link or access code.
4. Customer opens the wizard.
5. Portal validates the token.
6. Portal creates a secure session.
7. Token is removed from the browser URL if it was passed through a link.
8. Customer completes only the assigned wizard.
9. Customer can submit or replace values.
10. Customer cannot view submitted sensitive information afterward.
11. Internal users review the submitted data through the admin portal.

### Important Principle

A customer access token must be treated like a password or bearer credential.

Anyone who has the token may be able to access the wizard, so the token must be:

- Long.
- Random.
- Unguessable.
- Unique per customer project.
- Stored hashed.
- Never logged.
- Revocable.
- Scoped to one project.
- Expiring where possible.

---

## 4. Access Token Design

### Token Requirements

The access token should be generated using a cryptographically secure random generator.

Recommended requirements:

- Minimum 128 bits of entropy.
- Preferably 256 bits of entropy.
- URL-safe format.
- Unique per project.
- Stored only as a hash in the database.
- Displayed only once internally.
- Never stored in plaintext.
- Never logged.
- Revocable by internal admins.
- Regeneratable by internal admins.
- Optional expiry date.
- Rate-limited validation attempts.

Example token format:

```text
onb_8NwP7xKq2MzR4vT9sL6aY3cH1bD5eF0gJ2kLmQ9rX
```

Do not use predictable access keys such as:

```text
customer123
fabric-contoso
welcome2026
123456
contoso-fabric
```

---

## 5. Invitation Link Design

Avoid keeping the full access token in the browser URL during the wizard session.

URLs can leak through:

- Browser history.
- Proxy logs.
- Email security scanners.
- Referrer headers.
- Screenshots.
- Support tickets.
- Web analytics tools.

### Better Option: Temporary Link to Secure Session

Customer receives:

```text
https://portal.yourcompany.com/start?t=temporary_invite_token
```

The portal then:

1. Validates the temporary token.
2. Creates a secure session cookie.
3. Redirects the customer to:

```text
https://portal.yourcompany.com/wizard
```

This removes the token from the address bar.

### Alternative Option: Access Code Entry

Customer receives a normal portal link:

```text
https://portal.yourcompany.com/wizard
```

The customer then manually enters an access code.

This avoids putting the access token in the URL entirely.

---

## 6. Optional Low-Friction Extra Protection

If stronger security is needed without connecting the customer tenant, add a simple second check.

### Option A: Token + Email Verification

1. Customer opens wizard link.
2. Portal asks for their email address.
3. Portal sends a one-time code to that email address.
4. Customer enters the code.
5. Wizard opens.

This avoids tenant federation while reducing the risk of link forwarding.

### Option B: Token + PIN

Send:

- Portal link by email.
- PIN through a separate channel, such as phone, Teams, or a separate email.

This is stronger than using a single link.

### Recommended Approach

Use this model by default:

```text
Secure invitation link + secure session cookie + optional email OTP or PIN for sensitive projects
```

For projects involving secrets, passwords, API keys, or production access, strongly consider requiring either:

- Email OTP, or
- Separate PIN.

---

## 7. Internal Authentication Model

The low-friction token model should apply only to the customer wizard.

Internal users should authenticate using proper identity controls.

Recommended internal authentication:

- Microsoft Entra ID.
- MFA.
- Role-based access control.
- Conditional Access where possible.
- Separate permission for secret access.
- Full audit logging.

The model becomes:

```text
Customer side:
Unique secure wizard token, optionally with email OTP or PIN.

Internal side:
Microsoft Entra ID, MFA, RBAC, audit logging, and least privilege.
```

---

## 8. Roles and Permissions

The portal should use role-based access control for internal users and scoped access for customer wizard sessions.

| Role | Description |
|---|---|
| Internal Admin | Can manage templates, customers, users, access tokens, and all projects. |
| Internal Consultant | Can view assigned customers and approve/reject steps. |
| Internal Security Reviewer | Can review security-sensitive tasks and secret-related steps. |
| Internal Secret Handler | Can access submitted secrets if explicitly allowed. |
| Read-only Auditor | Can view progress and audit history. |
| Customer Wizard Session | Can access only one assigned wizard using a valid token/session. |

Every API call must validate that the user or wizard session is allowed to access the requested project, task, file, or secret reference.

Frontend filtering is not enough.

---

## 9. Customer Portal Permissions

The customer wizard session should only allow:

- Viewing assigned instructions.
- Seeing task status.
- Entering new values.
- Uploading evidence.
- Submitting tasks.
- Replacing previously submitted values.
- Adding customer comments.

The customer wizard session should not allow:

- Viewing submitted secrets.
- Viewing previous sensitive values.
- Downloading sensitive submitted files unless explicitly allowed.
- Seeing internal comments.
- Seeing internal users.
- Listing customers.
- Listing projects.
- Accessing admin APIs.
- Accessing another wizard.
- Exporting all submitted data.
- Viewing raw stored secret references.

---

## 10. Write-Only Customer Input Model

Since customers should not be able to view entered sensitive information afterward, the portal should use a **write-only input model**.

### Normal Non-Sensitive Values

For non-sensitive values, the customer may be allowed to view or edit the value later.

Examples:

- Tenant ID.
- Object ID.
- Group name.
- Workspace name.
- Contact email.
- DevOps organization URL.

### Sensitive Values

For sensitive values, the customer should only be able to submit or replace the value.

Examples:

- Passwords.
- Client secrets.
- API keys.
- Tokens.
- Connection strings.
- Certificate private keys.
- Recovery keys.

After submission, the portal should show only metadata.

Example:

```text
Secret submitted: Yes
Submitted at: 2026-07-10 14:32
Status: Waiting for review
```

The portal should not show:

```text
Password: ********
Client secret: ********
API key: ********
```

Even masked values should generally be avoided for secrets, because users may expect they can reveal, copy, or edit them.

---

## 11. Replacing Sensitive Values

If a customer made a mistake, they should not be able to view or edit the existing secret.

Instead, they should be able to replace it.

### Recommended Replacement Flow

```text
Current status: Secret submitted

Available action:
[Replace submitted secret]

When customer clicks:
- Old secret is marked as superseded.
- Customer enters a new secret.
- New secret is stored securely.
- Audit event is created.
- Internal team sees which version is active.
```

Old secret versions should not remain accessible unless there is a strict operational requirement.

---

## 12. Recommended Architecture

### Frontend

Possible options:

- React
- Next.js
- Angular
- Blazor

The customer wizard should be simple and clear:

- One task per page.
- Progress bar.
- Clear status indicators.
- “What you need.”
- “Why this is required.”
- “Step-by-step instructions.”
- “How to verify.”
- “Common mistakes.”
- File upload support.
- Comments and feedback.
- Write-only sensitive input fields.

### Backend

Possible options:

- ASP.NET Core Web API
- Node.js
- Python FastAPI

The backend should handle:

- Customer records.
- Onboarding projects.
- Requirement templates.
- Requirement instances.
- Access token validation.
- Secure session creation.
- Task status changes.
- Evidence uploads.
- Comments.
- Secret submission.
- Secret replacement.
- Notifications.
- Audit logging.
- Internal user authorization.

### Database

Recommended:

- Azure SQL Database
- PostgreSQL

The database stores:

- Customers.
- Projects.
- Users.
- Requirement templates.
- Project-specific requirements.
- Task status.
- Non-secret values.
- Secret references.
- Audit records.
- Notification history.
- Hashed access tokens.

The database must not store plaintext secrets.

### File Storage

Recommended:

- Azure Blob Storage with private containers.

Used for:

- Screenshots.
- Evidence files.
- Exported configuration files.
- Customer documents.

Security requirements:

- Private containers only.
- Short-lived access URLs.
- File type restrictions.
- Malware scanning.
- Audit download events.

### Secret Storage

Recommended:

- Azure Key Vault.

Secrets should not be stored in the normal database.

Examples of sensitive values:

- Passwords.
- Client secrets.
- API keys.
- Certificates.
- Recovery keys.
- Tokens.
- Connection strings.

---

## 13. Secret Storage Model

Sensitive values should never be stored in the normal database.

Recommended model:

```text
Customer submits secret
        ↓
Backend receives secret over TLS
        ↓
Backend immediately stores secret in Azure Key Vault
        ↓
Database stores only a reference
        ↓
Portal shows customer only "submitted"
```

Database stores:

```text
secret_id
project_requirement_id
key_vault_secret_uri
status
created_at
expires_at
submitted_by_session_id
version
```

Database should not store:

```text
password
client_secret
api_key
connection_string
certificate_private_key
token
```

---

## 14. Sealed Secret Submission Option

For higher-security secret submission, use a sealed or encrypted submission model.

### Flow

1. Portal has a public encryption key for the project.
2. Customer browser encrypts the secret before sending it.
3. Backend receives encrypted data.
4. Backend stores encrypted data or sends it to Key Vault.
5. Only trusted backend/deployment processes can decrypt it.

This makes the customer portal behave more like a secure dropbox than a normal form.

This model reduces the risk of plaintext secrets passing through the application layer, but it increases complexity.

---

## 15. Requirement Template System

Requirements should be stored as structured templates instead of hardcoded pages.

This allows our company to reuse the same task library for multiple customers and solution types.

### Example Requirement Categories

#### Microsoft Entra ID

- Create service account.
- Create security group.
- Assign users to security group.
- Create app registration.
- Grant API permissions.
- Configure Conditional Access exception if needed.

#### Microsoft Fabric / Power BI

- Enable required tenant settings.
- Configure workspace settings.
- Create capacities.
- Assign workspace admins.
- Configure gateway settings.
- Configure data source credentials.

#### Azure

- Create resource group.
- Create Key Vault.
- Create storage account.
- Configure private endpoints.
- Assign RBAC roles.

#### Azure DevOps / GitHub

- Create project or repository.
- Create service connection.
- Create variable groups.
- Configure pipeline permissions.
- Add deployment identity.

#### Networking

- Firewall allowlists.
- Private endpoint approvals.
- DNS entries.
- Gateway installation.

#### Security and Compliance

- Confirm data residency.
- Confirm admin contacts.
- Confirm break-glass process.
- Confirm audit/logging requirements.

---

## 16. Example Requirement Template

```json
{
  "id": "fabric-enable-tenant-setting",
  "title": "Enable required Fabric tenant setting",
  "category": "Microsoft Fabric",
  "description": "Enable the tenant setting required for deployment.",
  "whyRequired": "This allows the deployment process to create and configure the required Fabric artifacts.",
  "estimatedTimeMinutes": 10,
  "requiredRole": "Power BI/Fabric Admin",
  "instructions": [
    {
      "type": "text",
      "content": "Open the Microsoft Fabric admin portal."
    },
    {
      "type": "text",
      "content": "Go to Tenant settings."
    },
    {
      "type": "input",
      "fieldKey": "tenantSettingValue",
      "label": "Confirm the setting value",
      "sensitive": false,
      "required": true,
      "writeOnly": false
    },
    {
      "type": "secretInput",
      "fieldKey": "clientSecret",
      "label": "Enter the client secret",
      "sensitive": true,
      "required": true,
      "writeOnly": true
    },
    {
      "type": "fileUpload",
      "fieldKey": "screenshot",
      "label": "Upload screenshot as evidence",
      "required": true
    }
  ],
  "validationType": "manual-review",
  "dependencies": [],
  "riskLevel": "medium"
}
```

---

## 17. Task Status Flow

Each task should have a clear status.

| Status | Meaning |
|---|---|
| Not started | Customer has not opened the task. |
| In progress | Customer has started but not submitted. |
| Submitted | Customer says the task is done. |
| Needs changes | Internal consultant rejected the submission with feedback. |
| Approved | Internal consultant verified the task. |
| Blocked | Task cannot continue because of a dependency or issue. |
| Not applicable | Requirement was removed for this customer. |

### Recommended Flow

1. Internal admin creates project.
2. Admin selects solution package.
3. System generates the task list.
4. Admin adjusts customer-specific tasks.
5. Customer receives invitation.
6. Customer opens the wizard.
7. Portal validates the access token.
8. Portal creates a secure session.
9. Customer completes tasks step by step.
10. Customer submits tasks.
11. Consultant reviews tasks.
12. Consultant approves or rejects tasks.
13. When all blocking tasks are approved, deployment can start.
14. After deployment, secrets are deleted or expired.
15. Final onboarding report is generated.

---

## 18. Secret Handling Principles

Secret handling is the most critical part of the solution.

The best approach is to avoid collecting raw passwords or secrets whenever possible.

### Preferred Alternatives

#### 1. Temporary Delegated Access

The customer gives our named consultant or deployment account temporary access.

Benefits:

- No password sharing.
- Clear accountability.
- Access can be removed after onboarding.

#### 2. Customer Creates a Service Principal

The customer creates an app registration/service principal and grants only the required permissions.

Prefer:

- Certificate-based authentication.
- Federated identity.
- Short-lived credentials.

Avoid:

- Long-lived client secrets.
- Shared admin passwords.

#### 3. Use Workload Identity / Federated Credentials

For Azure DevOps or GitHub pipelines, prefer OIDC/federated identity instead of stored secrets.

Benefits:

- No secret storage.
- Better rotation model.
- Reduced risk of leaked credentials.

#### 4. Customer-Owned Key Vault

The customer stores secrets in their own Azure Key Vault and grants controlled access to our deployment identity.

This is the highest-security model.

---

## 19. If Secrets Must Be Submitted

If the portal must collect secrets, use a dedicated secure secret submission flow.

Requirements:

- Secrets are never stored in the normal database.
- Secrets are stored in Azure Key Vault.
- Secrets are encrypted in transit.
- Secrets are encrypted at rest.
- Access is limited to a small internal group.
- Access requires MFA.
- Every access is audited.
- Secrets have expiration dates.
- Secrets are deleted after onboarding.
- Secrets are never sent by email.
- Secrets are never logged.
- Secrets are never stored in telemetry.
- Secrets are masked or hidden in the UI.
- Customers cannot retrieve submitted secrets.
- Customers can only replace submitted secrets.
- Backend request logging must redact secret fields.

---

## 20. Security Controls

### Customer Access Security

- Unique secure access token per project.
- Token stored hashed.
- Token never logged.
- Token scoped to one project.
- Token can be revoked.
- Token can be regenerated.
- Optional token expiry.
- Optional email OTP or PIN.
- Secure session cookie after token validation.
- Token removed from URL after validation.
- Rate limiting on token attempts.
- Lockout or delay after repeated failures.

### Session Security

- HTTPS only.
- Secure cookies.
- HttpOnly cookies.
- SameSite cookie protection.
- Session timeout.
- CSRF protection.
- Content Security Policy headers.
- Referrer-Policy header.
- No sensitive data in browser local storage.
- No secrets in frontend logs.

### Internal Authentication

- Microsoft Entra ID for internal users.
- MFA required.
- Role-based access control.
- Least privilege access.
- Separate permission for secret access.
- Conditional Access where possible.

### Authorization

- Object-level authorization.
- Customer/project isolation.
- Separate permission for viewing or retrieving secrets.
- No cross-project access.
- Admin APIs inaccessible to customer sessions.

### Data Protection

- TLS everywhere.
- Database encryption at rest.
- Azure Key Vault for secrets.
- Private Blob Storage containers.
- Short-lived file access URLs.
- No secrets in logs.
- No secrets in emails.
- No secrets in analytics.
- Data retention policy.
- Secure deletion process.

### Audit Logging

Log the following events:

- Customer wizard opened.
- Token validated.
- Session created.
- Failed token attempt.
- Invitation created.
- Invitation revoked.
- Invitation regenerated.
- Task viewed.
- Task submitted.
- Task approved.
- Task rejected.
- Comment added.
- File uploaded.
- File downloaded.
- Secret submitted.
- Secret replaced.
- Secret accessed internally.
- Secret deleted.
- Admin configuration changed.

Do not log:

- Access tokens.
- Passwords.
- Client secrets.
- API keys.
- Connection strings.
- Private keys.
- Full request bodies containing sensitive data.

### Operational Security

- Separate dev, test, and production environments.
- Separate Key Vaults per environment.
- CI/CD with approvals.
- Dependency scanning.
- Vulnerability scanning.
- Backup and restore testing.
- Penetration test before production.
- Incident response process.
- GDPR/data processing review if applicable.

---

## 21. Validation and Automation

The portal should validate as much as possible to reduce manual back-and-forth.

### Manual Validation

Use when APIs are not available or access is not granted.

Examples:

- Customer uploads screenshot.
- Customer enters confirmation value.
- Consultant reviews manually.

### Semi-Automated Validation

Examples:

- Validate email format.
- Validate tenant ID GUID format.
- Validate client ID GUID format.
- Validate DevOps organization URL.
- Check that required fields are filled.
- Check that evidence was uploaded.

### Automated Validation

Where possible, use APIs such as:

- Microsoft Graph API.
- Azure Management API.
- Microsoft Fabric REST APIs.
- Power BI REST APIs.
- Azure DevOps APIs.
- GitHub APIs.

Possible automated checks:

- Does the security group exist?
- Does the service principal exist?
- Does the group contain the required members?
- Are required API permissions granted?
- Does the Fabric workspace exist?
- Are tenant settings configured?
- Is the DevOps service connection available?
- Does the storage account exist?
- Does the Key Vault exist?

---

## 22. Suggested Data Model

```text
Customer
- id
- name
- tenant_id
- primary_contact_email
- status

Project
- id
- customer_id
- name
- solution_type
- status
- created_by
- created_at
- target_go_live_date

InternalUser
- id
- entra_object_id
- email
- display_name
- role

CustomerAccessToken
- id
- project_id
- token_hash
- status
- expires_at
- created_at
- created_by
- revoked_at
- revoked_by
- last_used_at

CustomerWizardSession
- id
- project_id
- access_token_id
- created_at
- expires_at
- last_seen_at
- ip_address_hash
- user_agent_hash

RequirementTemplate
- id
- category
- title
- description
- instructions_json
- default_required_role
- risk_level
- version

ProjectRequirement
- id
- project_id
- requirement_template_id
- status
- assigned_to_label
- submitted_at
- approved_by
- approved_at
- rejection_reason

RequirementInput
- id
- project_requirement_id
- field_key
- value
- sensitivity_level
- write_only
- created_at
- updated_at

SecretReference
- id
- project_requirement_id
- field_key
- key_vault_secret_uri
- status
- version
- expires_at
- created_at
- superseded_at
- deleted_at

EvidenceFile
- id
- project_requirement_id
- blob_uri
- file_name
- content_type
- uploaded_by_session_id
- uploaded_at

AuditEvent
- id
- actor_type
- actor_id
- customer_id
- project_id
- event_type
- target_type
- target_id
- timestamp
- metadata_json
```

---

## 23. MVP Scope

Start with an MVP instead of building everything at once.

### MVP Version 1

Include:

- Internal login.
- Customer/project creation.
- Requirement template library.
- Customer access token generation.
- Customer invitation link or access code.
- Customer wizard session handling.
- Wizard UI.
- Task statuses.
- Write-only sensitive fields.
- File uploads.
- Comments.
- Manual approval.
- Basic audit log.
- Secure secret submission to Key Vault.
- Email notifications.
- Token revocation and regeneration.

### Version 2

Add:

- Optional email OTP or PIN for sensitive projects.
- Automated validation using Microsoft APIs.
- Conditional tasks.
- Multi-language support.
- Dashboard per consultant.
- Exportable onboarding report.
- SLA tracking.
- Reminder automation.
- Template versioning.

### Version 3

Add:

- Deployment readiness score.
- Integration with deployment automation.
- Customer-specific branding.
- Advanced policy engine.
- Evidence retention automation.
- One-time internal secret retrieval.
- Customer-owned Key Vault integration.
- Compliance reporting.
- Sealed client-side secret submission.

---

## 24. Recommended Technology Stack

Because this solution targets Microsoft Fabric customers, a Microsoft-oriented stack is recommended.

| Layer | Recommendation |
|---|---|
| Hosting | Azure App Service, Azure Container Apps, or AKS |
| Frontend | React, Next.js, or Blazor |
| Backend | ASP.NET Core Web API |
| Internal Identity | Microsoft Entra ID |
| Customer Access | Secure access token + session cookie |
| Database | Azure SQL Database |
| Secrets | Azure Key Vault |
| Files | Azure Blob Storage |
| Background Jobs | Azure Functions, WebJobs, or Azure Service Bus |
| Email | Azure Communication Services, SendGrid, or Microsoft Graph |
| Monitoring | Application Insights + Log Analytics |
| Infrastructure as Code | Bicep or Terraform |
| CI/CD | Azure DevOps or GitHub Actions |

---

## 25. Critical Design Decisions

Before implementation, decide:

1. Will customer access be link-based, access-code-based, or both?
   - Recommended: support both, but avoid keeping tokens in URLs after validation.

2. Should sensitive projects require OTP or PIN?
   - Recommended: yes.

3. Will the portal accept raw passwords?
   - Recommended: no, unless unavoidable.

4. Which customer-entered fields are write-only?
   - Recommended: all secrets, passwords, API keys, tokens, and private keys.

5. Who can access secrets internally?
   - Recommended: very small group with separate permissions and audit logging.

6. How long are secrets retained?
   - Recommended: delete after deployment or after a fixed expiry period.

7. Can customers use their own Key Vault?
   - Recommended: offer this as the highest-security option.

8. Which tasks can be automatically validated?
   - Start manual, then automate high-volume checks.

9. Should the app be designed as multi-tenant from the start?
   - Recommended: yes.

---

## 26. Example Customer Journey

1. Customer receives an invitation email.
2. Customer opens the portal link.
3. Portal validates the temporary token or asks for an access code.
4. Portal creates a secure wizard session.
5. Customer sees only their onboarding project.
6. Customer sees a list of required tasks.
7. Customer opens the first task.
8. Wizard explains what is needed, why it is needed, and how to do it.
9. Customer completes the task.
10. Customer enters required non-sensitive values.
11. Customer uploads evidence.
12. Customer submits the task.
13. For sensitive values, customer submits the secret once.
14. Portal stores the secret securely and clears the input.
15. Customer can only see that the secret was submitted.
16. Consultant reviews the submission.
17. Consultant approves or requests changes.
18. Customer fixes rejected tasks if needed.
19. Customer can replace secrets but cannot view existing secrets.
20. Deployment team is notified when all blocking tasks are approved.
21. Deployment starts.
22. Secrets are deleted or expired after deployment.
23. Final onboarding report is generated.

---

## 27. Recommended Next Step

Create a requirements matrix before building the software.

For every Microsoft Fabric solution type, define:

| Requirement | Needed for which package | Customer role needed | Secret involved? | Write-only? | Can validate automatically? | Evidence needed |
|---|---|---|---|---|---|---|

Example:

| Requirement | Package | Customer Role | Secret Involved | Write-only | Auto Validation | Evidence |
|---|---|---|---|---|---|---|
| Create security group | Standard Fabric Deployment | Entra Admin | No | No | Yes, via Graph API | Group object ID |
| Enable tenant setting | Standard Fabric Deployment | Fabric Admin | No | No | Maybe | Screenshot |
| Create service principal | Automated Deployment | Entra Admin | Yes | Yes | Yes, via Graph API | Client ID |
| Configure DevOps connection | CI/CD Deployment | DevOps Admin | Maybe | Yes if secret is entered | Maybe | Screenshot |
| Submit API key | Integration Deployment | Application Admin | Yes | Yes | No | Submitted status |

Once this matrix is complete, the portal can be designed around reusable requirement templates and customer-specific onboarding projects.

---

## 28. Summary

The portal should be a secure onboarding and readiness platform for Microsoft Fabric implementations.

The key capabilities are:

- Internal project setup.
- Reusable requirement templates.
- Customer-specific task selection.
- Low-friction customer wizard access.
- Unique secure access tokens.
- Secure session handling.
- Step-by-step wizard experience.
- Progress tracking.
- Manual and automated validation.
- Evidence upload.
- Write-only secret submission.
- Secret replacement without secret viewing.
- Audit logging.
- Deployment readiness reporting.

The most important security recommendations are:

- Do not require customers to connect their tenant if low friction is required.
- Use unique secure access tokens scoped to one wizard.
- Treat access tokens like passwords.
- Store access tokens only as hashes.
- Remove tokens from URLs after validation.
- Use secure session cookies.
- Avoid collecting raw passwords where possible.
- Store secrets only in Azure Key Vault.
- Make sensitive customer input write-only.
- Allow customers to replace secrets, but never view them.
- Audit every sensitive action.
- Delete secrets after they are no longer needed.