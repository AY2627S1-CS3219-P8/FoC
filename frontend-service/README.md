# React NextJS Shadcn + TailwindCSS Template

Components installed in template:

- Shadcn component library
- TailWindCSS
- ESLint + Prettier

This is a [Next.js](https://nextjs.org) project bootstrapped with [`create-next-app`](https://nextjs.org/docs/app/api-reference/cli/create-next-app).

## Getting Started

First, install dependencies:

```bash
yarn install
```

Then, run the development server:

```bash
yarn dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

You can start editing the page by modifying `app/page.tsx`. The page auto-updates as you edit the file.

This project uses [`next/font`](https://nextjs.org/docs/app/building-your-application/optimizing/fonts) to automatically optimize and load [Geist](https://vercel.com/font), a new font family for Vercel.

## Adding shadcn Components

This template is preconfigured for [shadcn](https://ui.shadcn.com). Add new components with:

```bash
npx shadcn@latest add <component>
```

Components are added to `components/ui`.

## Linting & Formatting

```bash
yarn lint          # ESLint
yarn format        # Prettier (writes changes)
yarn format:check  # Prettier (check only)
```

## Test Production Build

First build the project:

```bash
yarn build
```

Then serve the production build:

```bash
yarn start
```

## Running with Docker

Build the image (run from the `frontend-service` directory):

```bash
docker build -t frontend-service .
```

Run the container:

```bash
docker run -p 3000:3000 frontend-service
```

Open [http://localhost:3000](http://localhost:3000) to see the result.

## Supplier Service

The store directory (`/request/store`) and the store preselected on the
request form (`/request?store=<supplier id>`) come from Supplier Service's
public reads: `GET /suppliers`, `GET /suppliers/{id}`, `GET /categories` and
`GET /areas`.

- **Server-side only** (`lib/supplier-service.ts`): Supplier Service sets no
  CORS headers, so it is called from Server Components and the
  `loadSuppliers` Server Action (`lib/supplier-actions.ts`), never from the
  browser. Set `SUPPLIER_SERVICE_URL` at runtime; Compose uses
  `http://supplier-service:8080`, and `yarn dev` defaults to
  `http://localhost:8081`, the port Compose publishes on the host.
- **Filtering**: the directory filters by area and category (any of the
  selected categories) and pages 20 suppliers at a time, matching what the
  service supports. There is no free-text search because the service has none.
- **Display** follows the service's suggested UI behaviour: missing building or
  floor labels are omitted, null hours show "Hours unknown", equal opening and
  closing times show "Open 24 hours", and all times are Asia/Singapore.
- **Images**: Supplier Service returns only an `image_key` filename. The
  browser loads it directly from `NEXT_PUBLIC_SUPPLIER_IMAGE_BASE_URL`,
  defaulting to the seed images the CSV references
  (`raw.githubusercontent.com/CS3219-AY2627S1/FoC-Template/main/data/images`);
  the frontend neither stores nor proxies image files. Suppliers without an
  image show a category icon. `NEXT_PUBLIC_*` values are inlined at build time.
- **Unavailable service**: the frontend does not depend on Supplier Service to
  start (no Compose `depends_on`). If the service is down, unreachable, slow
  (5 s timeout) or returns an invalid response, supplier pages show an error
  message instead of failing, and the rest of the app works as normal.
  `docker compose up frontend-service` therefore does not start Supplier
  Service; use `docker compose up` for the full stack.

Supplier Service never seeds itself. To fill an empty local database, run from
the repository root:

```bash
docker compose --profile tools run --rm supplier-seed
```

## Authentication

Authentication goes through User Service, but the browser never talks to it
directly. Server Actions call User Service from the Next.js server and keep
its bearer token in an httpOnly `foc_session` cookie, so client JavaScript
never sees the token and User Service needs no CORS configuration.

- **User Service client** (`lib/user-service.ts`): typed `fetch` wrapper for
  the User Service endpoints the app uses. Its base URL comes from
  `USER_SERVICE_URL`, which is read at runtime on the server and defaults to
  `https://localhost:8080`. Compose sets it to `https://user-service:8080`.
  User Service only serves HTTPS with a certificate from the local internal
  CA (see [`docs/internal-https.md`](../docs/internal-https.md)), so Node
  must trust that CA through `NODE_EXTRA_CA_CERTS`. Compose mounts `ca.crt`
  into the container and sets it.
  It builds every request body field by field, so nothing extra from the
  browser reaches User Service. It and `lib/session.ts` import
  `server-only`, so importing either from a client component fails the build.
- **Server Actions** (`lib/auth-actions.ts`): `login`, `signup`,
  `reactivate`, `logout`, `updateProfile` and `deactivateAccount`. They return
  `{ ok, error, fieldErrors }` instead of throwing, so forms can show User
  Service validation messages next to the matching field.
- **Session** (`lib/session.ts`): sets and clears the cookie. The cookie is
  `Secure` unless `COOKIE_SECURE=false`; Compose sets that because it serves
  plain http.
  `requireCurrentUser()` calls `GET /users/me` once per request. The `(main)`
  layout calls it, so every private page confirms the session is still valid.
  A 401 redirects to `/auth/expired`, which clears the cookie and returns to
  the login page. Any site can link there, so it first checks the token with
  User Service and keeps a session that is still valid. A User Service outage shows the error page and does not log
  the user out.
- **Route gating** (`proxy.ts`): only checks that the cookie is _present_.
  - No cookie + private route → redirect to `/` (login) with
    `?from=<original path>`; after login the form returns there (same-origin
    paths only).
  - Cookie present + public route (`/`, `/signup`) → redirect to `/home`.

| Page                | User Service endpoints                                                 |
| ------------------- | ---------------------------------------------------------------------- |
| `/` login           | `POST /login`; `POST /users/me/reactivate` from "Reactivate it"        |
| `/signup`           | `POST /users`, then `POST /login`                                      |
| `/profile`          | `GET /users/me`, `PATCH /users/me`, `DELETE /users/me`, `POST /logout` |
| every `(main)` page | `GET /users/me`                                                        |

Login uses the **NUS student number** (for example `A1234567B`) and
password. User Service returns the same 401 for a wrong password and a
deactivated account, so the login form offers "Reactivate it" after User
Service rejects the credentials. A password change revokes every session, so `updateProfile` logs in
again with the new password to keep the current device signed in.

Not integrated yet: the admin endpoints (`/admin/users/{id}/suspend`,
`/unsuspend` and `/revoke-admin`) have no UI. `userService.getDisplayName()`
(`GET /users/{id}`) is ready for showing requester and courier names once the
feed and orders pages use Order Service data.

### Tests

```bash
yarn test
```

Vitest covers the User Service client, the auth Server Actions and the
`?from=` redirect check. CI runs it before the build.

### Running against User Service locally

With `yarn dev`, start User Service from the repo root. Compose publishes it
on `127.0.0.1:8080`. Generate the development certificates once first
(`.\scripts\generate-dev-tls.ps1`); User Service will not start without them:

```bash
docker compose up --build user-db user-migrate user-bootstrap user-service
```

Then start the dev server trusting the internal CA, from `frontend-service/`:

```bash
NODE_EXTRA_CA_CERTS=../certs/ca.crt yarn dev
```

Create an account at `/signup`, or set the `BOOTSTRAP_ADMIN_*` values in
`.env` to create an administrator. The full stack (`docker compose up`)
needs only the certificates: the frontend container reaches User Service over
the Compose network and trusts its CA through the mounted `ca.crt`.

Chrome and Firefox keep the `Secure` session cookie on `http://localhost`.
If you open the dev server another way, such as Safari or a LAN address,
start it with `COOKIE_SECURE=false yarn dev`.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
