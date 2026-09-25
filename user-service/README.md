# FoC User Service

The User Service manages student accounts and authentication for Friend on
Campus (FoC). It is responsible for user identity, profile information,
authentication sessions, roles, permissions, and account status. Other
microservices should access user data through this service's API; they must
not access its database directly.

## Responsibilities

- Register NUS student accounts.
- Validate registration input and enforce uniqueness of the NUS student
  number (User UID).
- Store passwords as one-way hashes and never expose plaintext passwords or
  password hashes in responses.
- Authenticate registered users and issue, validate, expire, and revoke
  sessions or equivalent authentication tokens.
- Provide authenticated users with their own profile and basic information
  about other users where permitted.
- Allow updates to mutable profile fields while protecting immutable and
  protected fields.
- Deactivate and reactivate user accounts without losing the account record.
- Manage user roles, permissions, and account statuses such as active,
  deactivated, and suspended.
- Produce structured logs for significant authentication and account-management events.

## User data

The service must collect and maintain the following registration/profile data:

- NUS student number (User UID)
- Email address
- Display/profile name
- Password hash
- Account role and status
- Account-creation timestamp
- Profile-update timestamp, where applicable

The NUS student number and account-creation timestamp are immutable. The
profile name, email address, and password are mutable, subject to validation.
Order history and credit balance are protected profile information and should
only be exposed through an appropriate authenticated response or consuming
service; sensitive authentication data must never be included.

## Authentication and authorization

### Registration

Registration should:

1. Validate required fields and normalize fields where applicable, including
   email addresses and NUS student numbers.
2. Reject duplicate NUS student numbers.
3. Reject empty, malformed, unsupported, or disallowed input.
4. Enforce the configured password policy: 8–100 characters, at least one
   number, one alphabetic character, and one special character.
5. Hash the password before persistence.
6. Create the account with the default status: active and non-administrative.

Failed registration attempts must not partially create an account or corrupt
existing user data.

### Login and sessions

Login must validate the supplied credentials against the stored password hash.
Successful authentication creates an authenticated session/token. Invalid,
expired, malformed, or tampered credentials/tokens must be rejected without
revealing whether a particular account exists.

Sessions must expire after the configured inactivity period (30 minutes) or 24 absolute hours, whichever comes first. A session refresh period longer than 30 days requires re-authentication. Logout must invalidate the session, and invalidated sessions must not be accepted for protected operations.

Protected requests must verify that the authenticated identity matches the
requested user where required. Ordinary users cannot grant themselves
administrative privileges, modify another user's profile, or perform
administrative operations.

### Roles and account status

The service supports regular users and administrators. Administrative
privileges must be explicitly authorized, persisted, and revocable.

Account status changes must be enforced during authentication and protected
operations:

- **Active** — normal account access is allowed.
- **Deactivated** — set by the user; the account record is retained.
- **Suspended** — set by an administrator; access is blocked until changed.

Reactivating a profile must restore it to an active state and must not
silently create a new account.

## Profile access rules

- An authenticated user may view their own profile, including their NUS
  student number, display name, and order-history information made available
  by the platform.
- An authenticated user may view another user's basic profile information,
  limited to the profile name.
- Sensitive information must be omitted or masked in full-value displays.
- Users may update permitted mutable fields only.
- NUS student numbers, account timestamps, roles, statuses, and another
  user's profile are not user-editable.
- Successful updates return the updated permitted profile fields.

## Security requirements

- Store passwords in a non-reversible form using a password-hashing
  algorithm; never persist or return plaintext passwords.
- Do not log passwords, password hashes, session tokens, or other sensitive
  authentication credentials.
- Require authentication and authorization for protected operations.
- Use generic authentication and registration errors that do not disclose
  account existence or internal implementation details.
- Keep the User Service database private to this service.
- Expose only the minimum user information required by each consuming
  service.
- Record structured audit logs for significant authentication and
  account-management events.

## Non-functional targets

The project requirements specify the following targets for the User Service:

- A normal login should complete within 2 seconds for at least 95% of
  requests under normal load.
- Support up to 60,000 active profiles.
- Remain available independently of unrelated services where possible.
- Avoid duplicate accounts when clients retry registration.
- Preserve persistent user data when another microservice fails.
- Encapsulate account, authentication, authorization, and profile logic in
  this service.

## API and integration notes

Route names and request/response schemas will be added when the service API is implemented. Any API contract should document, at minimum:

- Registration, login, logout, session validation/refresh, and profile
  operations.
- Authentication and authorization requirements for each operation.
- Validation rules and safe error responses.
- Which profile fields are returned to the account owner, other users, and
  consuming services.
- Account-status and role-management behavior.

Consuming services should depend on the User Service API or documented
authentication events, not on implementation details or direct database
access.

## Local development

The service is containerized from this directory. Once the application entry
point and dependencies are added, build and run it from the repository root
with the project compose configuration:

```bash
docker compose build user-service
docker compose up user-service
```

The local compose setup also starts PostgreSQL as `user-db`. The service uses
the `DATABASE_URL` environment variable and creates the initial `users` table
on startup. For local development:

```bash
cp .env.example .env
docker compose up --build user-db user-service
```

The service is available to other containers on the Compose network at
`http://user-service:8080`. The current Compose configuration does not publish
port 8080 to the host. To access the API from the host, temporarily add this
to the `user-service` definition in `compose.yaml`:

```yaml
ports:
  - "8080:8080"
```

Once the port is published, create a user with:

```bash
curl -X POST http://localhost:8080/users \
  -H 'Content-Type: application/json' \
  -d '{"nus_student_number":"A0123456X","email":"student@example.com","display_name":"Student","password":"Password1!"}'
```

The development database credentials are defined in `compose.yaml`; replace
them with secrets or an untracked environment file before using a deployed
environment. Schema creation here is intended as a starting point; add
Alembic migrations before evolving the production schema.

Do not commit credentials, tokens, private keys, or production configuration.
Use environment variables or a local, untracked environment file for local
development.

## Requirements source

This README summarizes the User Service requirements in the FoC Project
Milestone 1 document, especially functional requirements F5–F9 and User
Service non-functional requirements NFR7. The README is a service-level guide;
the project document remains the authoritative source for the full
requirements set.
