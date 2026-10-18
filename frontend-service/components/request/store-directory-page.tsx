'use client';

import { useRouter } from 'next/navigation';
import { ArrowLeft } from 'lucide-react';

import { PageContainer } from '@/components/page-header';
import { StoreDirectory } from '@/components/request/store-directory';
import type { Store } from '@/lib/mock-data';

export function StoreDirectoryPage() {
  const router = useRouter();

  function selectStore(store: Store) {
    router.push(`/request?store=${store.id}`);
  }

  return (
    <PageContainer className='flex min-h-dvh flex-col md:min-h-0'>
      <header className='sticky top-0 z-30 flex items-center gap-2 border-b bg-white/95 px-4 py-3 backdrop-blur md:static md:border-none md:bg-transparent md:px-0 md:pt-8 md:pb-4 md:backdrop-blur-none'>
        <button
          type='button'
          aria-label='Back to request form'
          onClick={() => router.back()}
          className='grid size-10 shrink-0 place-items-center rounded-full text-slate-700 hover:bg-slate-100'
        >
          <ArrowLeft className='size-5' />
        </button>
        <h1 className='text-xl font-bold text-slate-900 md:text-2xl'>
          Campus Store Directory
        </h1>
      </header>

      <StoreDirectory
        onSelect={selectStore}
        className='min-h-0 flex-1 px-4 pt-4 pb-4 md:px-0'
      />
    </PageContainer>
  );
}
