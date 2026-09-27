import { Button } from '@/components/ui/button';

export default function Home() {
  return (
    <div className='flex min-h-screen flex-col items-center justify-center gap-4 p-8'>
      <h1 className='text-2xl font-semibold'>React + Next.js + shadcn</h1>
      <p className='text-muted-foreground text-sm'>
        Edit <code className='font-mono'>app/page.tsx</code> to get started.
      </p>
      <Button>shadcn Button</Button>
    </div>
  );
}
