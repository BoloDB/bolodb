# 10. Authentication and Workspaces

BoloDB is built as a multi-tenant web application. All data—connections, query history, saved queries, dashboards, and the knowledge base—is isolated per **workspace**.

---

## 1. Authentication

Authentication is handled via JWT tokens issued by the backend server (`backend/app/routes/auth.py` and `backend/app/controllers/auth.py`).

### Auth Methods
- **Email + Password**: Users register via `/api/auth/signup` and authenticate via `/api/auth/login`. Password hashes are stored securely using passlib/bcrypt.
- **Google OAuth**: Google authentication flow produces a verified OAuth token handled at `/api/auth/supabase-google`.
- **Email Verification & Password Reset**: Handled via token generation in `backend/app/services/email_verification.py` and dispatched using the Resend API service (`backend/app/services/email.py`).

### Token Management & Cookies
- Upon successful authentication, the server sets secure HTTP-only cookies containing the JWT access and refresh tokens.
- `backend/app/dependencies.py` exposes `get_current_user`, which validates the token on incoming API calls.
- Centralized secrets management (`backend/app/secrets.py`) retrieves secrets like `JWT_SECRET`, `RESEND_API_KEY`, and `FRONTEND_URL` from the environment.

---

## 2. Workspace Multi-Tenancy

A **Workspace** is the primary boundary of data isolation. Each workspace contains:
- **Database Connections**: Connections registered within the workspace context (encrypted at rest).
- **Knowledge Base**: Verified Q&A, business glossary, and semantic layer entries (`backend/app/pgdatabase/knowledge.py`).
- **Dashboards & Saved Queries**: Custom dashboards with ECharts visual panels.
- **Activity Log**: Workspace audit log (`backend/app/models/activity.py`).

### Context Propagation
Client requests include `X-Workspace-Id` and `X-Db-Id` headers. The FastAPI dependencies `get_current_workspace()` and `get_current_db_id()` in `backend/app/dependencies.py` ensure:
1. The requested workspace exists and the authenticated user is an active member of that workspace.
2. The active target database connection context (`X-Db-Id`) is validated and propagated to database services and controllers.

---

## 3. Role-Based Access Control (RBAC)

BoloDB uses a granular permission registry defined in `backend/app/permissions.py`.

### Roles
Every workspace member holds one of three roles:
1. **Owner**: Full administrative control over workspace settings, members, permissions, and database connections.
2. **Admin**: Can manage connections, edit the semantic catalog, invite members, and build dashboards.
3. **Member**: Can execute queries, view dashboards, view schemas, and save queries.

### Permission Registry Matrix

The system defines 21 fine-grained capabilities across 7 resources:

| Resource | Capability Key | Description | Default Owner | Default Admin | Default Member |
|---|---|---|---|---|---|
| **members** | `members.view` | View workspace member list and member details | Yes | Yes | Yes |
| | `members.invite` | Invite new members to join the workspace | Yes | Yes | No |
| | `members.update_role` | Change roles of workspace members | Yes | Yes | No |
| | `members.remove` | Remove members from the workspace | Yes | Yes | No |
| **connections** | `connections.view` | View configured database connections | Yes | Yes | Yes |
| | `connections.manage` | Create, edit, or delete database connections | Yes | Yes | No |
| | `connections.view_schema` | View schema and metadata for database connections | Yes | Yes | Yes |
| **catalog** | `catalog.view` | View data catalog, verified Q&A, and metrics | Yes | Yes | Yes |
| | `catalog.manage` | Create or update data catalog definitions | Yes | Yes | No |
| **dashboards** | `dashboards.view` | View dashboards and visualization panels | Yes | Yes | Yes |
| | `dashboards.create` | Create new dashboards and panels | Yes | Yes | No |
| | `dashboards.manage` | Edit or delete existing dashboards | Yes | Yes | No |
| **queries** | `queries.execute` | Execute natural language and SQL queries | Yes | Yes | Yes |
| | `queries.explain` | Generate query explanations and execution plans | Yes | Yes | Yes |
| | `queries.save` | Save queries for workspace access | Yes | Yes | Yes |
| | `queries.delete_saved` | Delete saved queries | Yes | Yes | No |
| **activity** | `activity.view` | View workspace activity logs | Yes | Yes | No |
| | `activity.export` | Export workspace activity logs | Yes | Yes | No |
| **workspace_management** | `workspace.view` | View workspace details and configuration | Yes | Yes | Yes |
| | `workspace.update` | Update workspace basic profile details | Yes | Yes | No |
| | `workspace.settings` | Manage workspace defaults and role permission matrix | Yes | Yes | No |

Custom role overrides can be saved per workspace in `WorkspaceSettings` (`backend/app/models/workspace_settings.py`).

---

## 4. Member Invites & Onboarding Flow

1. Workspace owners/admins generate an invitation link or email invite.
2. An invitation pin/token is created (`backend/app/pgdatabase/otp.py`).
3. Invited users accept the invitation during registration or via their workspace switcher in the app.
