import type { Metadata } from 'next';

import { FavorFeed } from '@/components/feed/favor-feed';

export const metadata: Metadata = { title: 'Feed · Friend on Campus' };

export default function HomePage() {
  return <FavorFeed />;
}
