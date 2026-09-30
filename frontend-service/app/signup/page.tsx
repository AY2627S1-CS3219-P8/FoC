import type { Metadata } from 'next';
import Link from 'next/link';
import { Package } from 'lucide-react';

export const metadata: Metadata = {
  title: 'Create an account · Friend on Campus',
};

export default function SignupPage() {
  return (
    <div className='flex min-h-dvh flex-col items-center justify-center px-6 py-12 text-center'>
      <span className='bg-brand grid size-16 place-items-center rounded-2xl text-white'>
        <Package className='size-8' aria-hidden />
      </span>
      <h1 className='mt-4 text-2xl font-bold text-slate-900'>
        Sign-up is coming soon
      </h1>
      <p className='mt-2 max-w-sm text-sm text-slate-500'>
        Account creation isn&apos;t wired up yet. Check back once the auth
        service supports it.
      </p>
      <Link
        href='/'
        className='text-brand-strong mt-6 text-sm font-semibold hover:underline'
      >
        Back to log in
      </Link>
    </div>
  );
}
