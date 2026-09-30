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

## Authentication

> **⚠️ Temporary: authentication is stubbed out on this branch.**
> The frontend makes **no backend calls at all** right now. `login()` in
> `lib/auth.ts` accepts any email and password, writes the `foc_session`
> cookie client-side, and routes to `/home`. Nothing is verified and no
> credentials leave the browser. This is only so the post-login pages can be
> built and reviewed — it must be removed before anything ships.

The intended design is cookie-based auth where the frontend never manages
tokens: the User Service issues and validates the session, and the frontend
only checks whether the cookie is present.

- **Login** (`lib/auth.ts`): `login({ email, password })` currently ignores
  its arguments and sets `foc_session` directly. It is a stub with a
  restoration note in its doc comment.
- **Route gating** (`proxy.ts`): on every request (except static assets),
  checks only whether the `foc_session` cookie is _present_. This part is
  real and unchanged.
  - No cookie + private route → redirect to `/` (login) with
    `?from=<original path>` so the login form can send the user back after
    a successful login.
  - Cookie present + public route (`/`, `/signup`) → redirect to `/home`.
  - `/` and `/signup` are the only public paths; everything else requires
    the cookie.
- **Login form** (`components/auth/login-form.tsx`): on submit, calls
  `login()`, then routes to `?from=` (or `/home`) and calls `router.refresh()`
  so `proxy.ts` re-evaluates with the new cookie. It shows a visible banner
  saying auth is stubbed. The "Incorrect email or password." branch is dead
  code for now, kept so the real flow is easy to restore.
- **Signup** (`app/signup/page.tsx`) is a placeholder page; account creation
  is not implemented.

Because the cookie is set client-side, you can clear it from the DevTools
console to get back to the login page (while it is set, `/` redirects to
`/home`):

```js
document.cookie = 'foc_session=; path=/; max-age=0';
```

`lib/auth.ts` also exports a `logout()` helper that does the same thing.

### Restoring the real flow

`user-service/app/main.py` currently only exposes `/health`. The user model,
password hashing, and login/register endpoints exist on `main` (merged via
other PRs) but have not been pulled into this branch. Once that lands, or
this branch is rebased on `main`:

1. Replace the stubbed `login()` body with a POST to
   `${NEXT_PUBLIC_USER_SERVICE_URL}/auth/login` using
   `credentials: 'include'`, and let the User Service set the cookie via
   `Set-Cookie`. Delete `logout()` and the banner in the login form.
2. Uncomment `NEXT_PUBLIC_USER_SERVICE_URL` in the root `.env.example` and
   pass it as a **build arg** — `NEXT_PUBLIC_*` values are inlined at
   `next build` time, so setting it at runtime has no effect.
3. Add CORS to user-service with `allow_credentials=True` and an explicit
   origin, so the cross-origin `Set-Cookie` survives.

There are no working test credentials to give out; this section will be
updated with a real test account once `/auth/login` exists.

## Learn More

To learn more about Next.js, take a look at the following resources:

- [Next.js Documentation](https://nextjs.org/docs) - learn about Next.js features and API.
- [Learn Next.js](https://nextjs.org/learn) - an interactive Next.js tutorial.

You can check out [the Next.js GitHub repository](https://github.com/vercel/next.js) - your feedback and contributions are welcome!

## Deploy on Vercel

The easiest way to deploy your Next.js app is to use the [Vercel Platform](https://vercel.com/new?utm_medium=default-template&filter=next.js&utm_source=create-next-app&utm_campaign=create-next-app-readme) from the creators of Next.js.

Check out our [Next.js deployment documentation](https://nextjs.org/docs/app/building-your-application/deploying) for more details.
