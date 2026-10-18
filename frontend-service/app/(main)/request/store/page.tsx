import type { Metadata } from 'next';

import { StoreDirectoryPage } from '@/components/request/store-directory-page';

export const metadata: Metadata = {
  title: 'Select Store · Friend on Campus',
};

export default function RequestStorePage() {
  return <StoreDirectoryPage />;
}
