import { NextResponse, type NextRequest } from 'next/server';

import { SESSION_COOKIE_NAME, SESSION_EXPIRED_PATH } from '@/lib/auth';

const PUBLIC_PATHS = new Set(['/', '/signup']);

export function proxy(request: NextRequest) {
  const { pathname } = request.nextUrl;
  // Clears the cookie itself, with or without one, so never redirect it.
  if (pathname === SESSION_EXPIRED_PATH) return NextResponse.next();

  const isAuthenticated = request.cookies.has(SESSION_COOKIE_NAME);
  const isPublicPath = PUBLIC_PATHS.has(pathname);

  if (!isAuthenticated && !isPublicPath) {
    const loginUrl = new URL('/', request.url);
    loginUrl.searchParams.set('from', pathname);
    return NextResponse.redirect(loginUrl);
  }

  if (isAuthenticated && isPublicPath) {
    return NextResponse.redirect(new URL('/home', request.url));
  }

  return NextResponse.next();
}

export const config = {
  // Run on everything except static assets/image optimizer output.
  matcher: ['/((?!_next/static|_next/image|favicon.ico).*)'],
};
