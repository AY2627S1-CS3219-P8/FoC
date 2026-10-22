import type { Metadata } from 'next';

import { ErrandList } from '@/components/orders/errand-list';
import { loadMyOrders } from '@/lib/order-actions';

export const metadata: Metadata = { title: 'Orders · Friend on Campus' };

export default async function OrdersPage({
  searchParams,
}: {
  searchParams: Promise<{ role?: string | string[] }>;
}) {
  const { role } = await searchParams;
  // Both lists load up front so each tab can show its count.
  const [requester, courier] = await Promise.all([
    loadMyOrders('requester'),
    loadMyOrders('courier'),
  ]);

  return (
    <ErrandList
      initialRole={role === 'courier' ? 'courier' : 'requester'}
      initial={{ requester, courier }}
    />
  );
}
