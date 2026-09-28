import type { Metadata } from 'next';

import { ErrandList } from '@/components/orders/errand-list';

export const metadata: Metadata = { title: 'Orders · Friend on Campus' };

export default function OrdersPage() {
  return <ErrandList />;
}
