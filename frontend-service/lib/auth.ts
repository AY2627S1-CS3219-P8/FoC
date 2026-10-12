/**
 * Name of the session cookie. `proxy.ts` checks for its presence to decide
 * whether a request is authenticated — it never inspects the value.
 */
export const SESSION_COOKIE_NAME = 'foc_session';

export type LoginCredentials = {
  email: string;
  password: string;
};

/**
 * TEMPORARY STUB - NOT REAL AUTHENTICATION
 *
 * `user-service` does not expose `/auth/login` yet, so this branch has no
 * backend to authenticate against. Until it does, `login()` accepts ANY
 * credentials and simply drops a `foc_session` cookie so `proxy.ts` lets the
 * request through to `/home` and the rest of the app. Nothing is verified,
 * nothing is sent anywhere, and the cookie's value is meaningless.
 *
 * This exists only so the post-login pages can be built and reviewed. It MUST
 * be deleted before anything ships.
 *
 * To restore the real flow once `/auth/login` exists, replace the body with a
 * POST to the user-service login endpoint using `credentials: 'include'` and
 * let that service issue the cookie via `Set-Cookie` — the frontend should go
 * back to never writing the cookie itself. The endpoint's base URL used to
 * come from `NEXT_PUBLIC_USER_SERVICE_URL`; that variable is unused for now.
 */
export async function login(credentials: LoginCredentials) {
  if (process.env.NODE_ENV !== 'production') {
    console.warn(
      `[auth] STUB LOGIN — "${credentials.email}" was not verified. ` +
        'Any credentials are accepted until user-service exposes /auth/login.',
    );
  }

  // `SameSite=Lax` and no `Secure` so it works over plain http://localhost.
  document.cookie = `${SESSION_COOKIE_NAME}=stub; path=/; SameSite=Lax`;
}

/**
 * ⚠️ TEMPORARY — companion to the stubbed `login()` above. ⚠️
 *
 * Clears the fake session cookie so you can get back to the login page. Real
 * logout belongs on the user-service side (it has to invalidate the session),
 * so this goes away together with the stub.
 */
export function logout() {
  document.cookie = `${SESSION_COOKIE_NAME}=; path=/; max-age=0; SameSite=Lax`;
}
