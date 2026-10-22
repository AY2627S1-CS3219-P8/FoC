import 'server-only';

import { cache } from 'react';
import { cookies } from 'next/headers';
import { redirect } from 'next/navigation';

import { SESSION_COOKIE_NAME, SESSION_EXPIRED_PATH } from '@/lib/auth';
import { type User, UserServiceError, userService } from '@/lib/user-service';

export async function getSessionToken() {
  return (await cookies()).get(SESSION_COOKIE_NAME)?.value;
}

/**
 * Secure unless `COOKIE_SECURE=false`, which Compose sets because it serves
 * plain http. Read from config, not `x-forwarded-proto`, because clients can
 * send that header themselves.
 */
const COOKIE_SECURE = process.env.COOKIE_SECURE !== 'false';

/**
 * Only callable from Server Actions and Route Handlers. There is no max-age:
 * User Service extends the session while it is used, so it decides when the
 * token expires and pages handle the resulting 401.
 */
export async function setSessionCookie(token: string) {
  (await cookies()).set(SESSION_COOKIE_NAME, token, {
    httpOnly: true,
    sameSite: 'lax',
    secure: COOKIE_SECURE,
    path: '/',
  });
}

export async function clearSessionCookie() {
  (await cookies()).delete(SESSION_COOKIE_NAME);
}

/**
 * The signed-in user for the current request, deduplicated across the layout
 * and page. A missing or rejected session redirects to the login page; a User
 * Service outage is rethrown so the error boundary shows it, because it does
 * not mean the user has logged out.
 */
export const requireCurrentUser = cache(async (): Promise<User> => {
  const token = await getSessionToken();
  if (!token) redirect('/');

  try {
    return await userService.getCurrentUser(token);
  } catch (error) {
    if (error instanceof UserServiceError && error.status === 401) {
      redirect(SESSION_EXPIRED_PATH);
    }
    throw error;
  }
});
