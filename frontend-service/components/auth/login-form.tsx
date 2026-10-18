'use client';

import { useState } from 'react';
import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { Lock, Mail, Package, TriangleAlert } from 'lucide-react';

import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { login } from '@/lib/auth';
import { cn } from '@/lib/utils';

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      // TEMPORARY: `login()` is stubbed and accepts anything — see lib/auth.ts.
      // The catch below is dead until the real endpoint is wired back up.
      await login({ email, password });
      router.push(searchParams.get('from') ?? '/home');
      router.refresh();
    } catch {
      setError('Incorrect email or password.');
    } finally {
      setIsSubmitting(false);
    }
  }

  return (
    <div className='flex min-h-dvh flex-col items-center justify-center px-6 py-12'>
      <div className='w-full max-w-sm'>
        <div className='flex flex-col items-center text-center'>
          <span className='bg-brand grid size-16 place-items-center rounded-2xl text-white'>
            <Package className='size-8' aria-hidden />
          </span>
          <h1 className='text-brand mt-4 text-3xl font-extrabold'>FoC</h1>
          <p className='mt-1 text-sm text-slate-500'>
            Campus errands, sorted by your peers
          </p>
        </div>

        {/* TEMPORARY: remove together with the stub in lib/auth.ts. */}
        <div
          role='status'
          className='mt-8 flex gap-2 rounded-xl border border-amber-300 bg-amber-50 px-3 py-2.5 text-left text-xs text-amber-900'
        >
          <TriangleAlert className='mt-px size-4 shrink-0' aria-hidden />
          <p>
            <span className='font-semibold'>Auth is stubbed.</span> Login is
            purely UI-only for now.
          </p>
        </div>

        <form onSubmit={handleSubmit} className='mt-4 space-y-4'>
          <div className='space-y-2'>
            <Label htmlFor='email'>Email</Label>
            <div className='relative'>
              <Mail
                className='pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400'
                aria-hidden
              />
              <Input
                id='email'
                type='email'
                autoComplete='email'
                required
                placeholder='alex.tan@u.nus.edu'
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className='h-12 rounded-xl pl-10'
              />
            </div>
          </div>

          <div className='space-y-2'>
            <Label htmlFor='password'>Password</Label>
            <div className='relative'>
              <Lock
                className='pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-slate-400'
                aria-hidden
              />
              <Input
                id='password'
                type='password'
                autoComplete='current-password'
                required
                placeholder='••••••••••'
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className='h-12 rounded-xl pl-10'
              />
            </div>
          </div>

          {error && (
            <p role='alert' className='text-sm text-red-600'>
              {error}
            </p>
          )}

          <Button
            type='submit'
            disabled={isSubmitting}
            className={cn(
              'bg-brand hover:bg-brand-strong h-12 w-full rounded-xl text-base font-bold text-white',
            )}
          >
            {isSubmitting ? 'Logging in…' : 'Log In'}
          </Button>
        </form>

        <p className='mt-6 text-center text-sm text-slate-500'>
          New to FoC?{' '}
          <Link
            href='/signup'
            className='text-brand-strong font-semibold hover:underline'
          >
            Create an account
          </Link>
        </p>
      </div>
    </div>
  );
}
