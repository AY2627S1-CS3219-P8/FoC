import type { Metadata } from 'next';

import { ProfileView } from '@/components/profile/profile-view';
import { requireCurrentUser } from '@/lib/session';

export const metadata: Metadata = { title: 'Profile · Friend on Campus' };

export default async function ProfilePage() {
  const user = await requireCurrentUser();
  return <ProfileView user={user} />;
}
