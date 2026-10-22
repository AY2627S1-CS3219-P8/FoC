import { cookies } from 'next/headers';

import { SESSION_COOKIE_NAME } from '@/lib/auth';

/**
 * The User Service bearer token that Order and Credit Service expect.
 *
 * Login is still stubbed on this branch, so the cookie holds a placeholder
 * and both services answer 401 until the real User Service login lands.
 * Replace this with `getSessionToken` from `lib/session.ts` at that point.
 */
export async function getSessionToken() {
  return (await cookies()).get(SESSION_COOKIE_NAME)?.value;
}
