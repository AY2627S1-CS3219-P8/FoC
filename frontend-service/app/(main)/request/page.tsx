import type { Metadata } from 'next';
import { Suspense } from 'react';

import { RequestErrand } from '@/components/request/request-errand';

export const metadata: Metadata = { title: 'Request · Friend on Campus' };

export default function RequestPage() {
  return (
    <Suspense>
      <RequestErrand />
    </Suspense>
  );
}
