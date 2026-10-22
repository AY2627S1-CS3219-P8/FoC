import type { Metadata } from 'next';

import { RequestErrand } from '@/components/request/request-errand';
import {
  type Supplier,
  SupplierServiceError,
  supplierService,
} from '@/lib/supplier-service';

export const metadata: Metadata = { title: 'Request · Friend on Campus' };

export default async function RequestPage({
  searchParams,
}: {
  searchParams: Promise<{ store?: string | string[] }>;
}) {
  const { store: storeId } = await searchParams;

  let store: Supplier | null = null;
  let storeError: string | null = null;
  if (typeof storeId === 'string') {
    try {
      store = await supplierService.getSupplier(storeId);
      if (!store) storeError = 'That store is no longer available.';
    } catch (error) {
      if (!(error instanceof SupplierServiceError)) throw error;
      storeError = error.message;
    }
  }

  // Keyed so choosing another store remounts the form with it preselected.
  return (
    <RequestErrand
      key={store?.id ?? 'none'}
      initialStore={store}
      storeError={storeError}
    />
  );
}
