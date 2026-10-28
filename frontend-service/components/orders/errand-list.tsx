'use client';

import { useState, useTransition } from 'react';
import { ArrowRight, Store } from 'lucide-react';

import {
  CardGrid,
  ErrorBanner,
  LoadMoreButton,
  RefreshButton,
} from '@/components/list-controls';
import { DropOffFields } from '@/components/orders/drop-off-fields';
import { PageContainer, PageHeader } from '@/components/page-header';
import { Button } from '@/components/ui/button';
import { usePagedList } from '@/components/use-paged-list';
import type { PageResult } from '@/lib/action-result';
import {
  deliveryDetailsOf,
  dropOffValueOf,
  toDeliveryLocation,
} from '@/lib/drop-off';
import { formatDateTime } from '@/lib/format';
import {
  type OrderActionResult,
  cancelOrder,
  changeDelivery,
  completeOrder,
  loadMyOrders,
  pickUpOrder,
} from '@/lib/order-actions';
import type { OrderRole, OrderStatus } from '@/lib/order-service';
import {
  type OrderView,
  PRE_PICKUP_STATUSES,
  STATUS_LABELS,
  formatRejectionReason,
  orderPickupLocation,
  orderStoreName,
} from '@/lib/orders';
import { cn } from '@/lib/utils';

const STATUS_STYLES: Record<OrderStatus, string> = {
  PENDING_CREDIT: 'bg-slate-100 text-slate-600',
  OPEN: 'bg-amber-50 text-amber-700',
  ACCEPTED: 'bg-courier-soft text-courier',
  PICKED_UP: 'bg-sky-50 text-sky-700',
  COMPLETED: 'bg-emerald-50 text-emerald-700',
  CANCELLED: 'bg-red-50 text-red-600',
  EXPIRED: 'bg-slate-100 text-slate-500',
  REJECTED: 'bg-red-50 text-red-600',
};

const ROLE_TABS: { role: OrderRole; label: string }[] = [
  { role: 'requester', label: 'As Requester' },
  { role: 'courier', label: 'As Courier' },
];

/** What happens next, in the words of the person looking at the card. */
function statusNote(order: OrderView, role: OrderRole) {
  switch (order.status) {
    case 'PENDING_CREDIT':
      return `Reserving ${order.credit_amount} cr from your balance…`;
    case 'OPEN':
      return `Waiting for a courier · expires ${formatDateTime(order.expires_at)}`;
    case 'ACCEPTED':
      return role === 'requester'
        ? 'A courier is on the way to the store.'
        : 'Head to the store and mark the errand as picked up.';
    case 'PICKED_UP':
      return role === 'requester'
        ? 'Your courier has your items. Confirm once you receive them.'
        : 'Waiting for the requester to confirm delivery.';
    case 'COMPLETED':
      return role === 'requester'
        ? `${order.credit_amount} cr paid to your courier.`
        : `${order.credit_amount} cr earned.`;
    case 'CANCELLED':
      // Only an administrator can cancel after pickup; the courier is paid.
      if (order.picked_up_at) {
        return role === 'requester'
          ? `Cancelled after pickup. ${order.credit_amount} cr paid to your courier.`
          : `Cancelled after pickup. ${order.credit_amount} cr earned.`;
      }
      return role === 'requester'
        ? 'Cancelled. Any reserved credit is returned to your balance.'
        : 'Cancelled.';
    case 'EXPIRED':
      return 'No courier accepted in time. Any reserved credit is returned.';
    case 'REJECTED':
      return formatRejectionReason(order.rejection_reason);
  }
}

type ErrandCardProps = {
  order: OrderView;
  role: OrderRole;
  onUpdate: (order: OrderView) => void;
};

function ErrandCard({ order, role, onUpdate }: ErrandCardProps) {
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState(false);
  const [dropOff, setDropOff] = useState(() => dropOffValueOf(order));
  const [isPending, startTransition] = useTransition();

  const isRequester = role === 'requester';
  const beforePickup = PRE_PICKUP_STATUSES.includes(order.status);
  const delivery = toDeliveryLocation(dropOff);

  function run(action: () => Promise<OrderActionResult>) {
    setError(null);
    startTransition(async () => {
      const result = await action();
      if (result.ok) {
        onUpdate(result.order);
        setEditing(false);
      } else {
        setError(result.message);
      }
    });
  }

  function cancel() {
    if (window.confirm('Cancel this errand? Reserved credit is returned.')) {
      run(() => cancelOrder(order.id));
    }
  }

  const actionClass = 'h-9 rounded-lg px-4 text-sm font-semibold';

  return (
    <article className='flex flex-col rounded-2xl border bg-white p-4 shadow-sm'>
      <div className='flex items-center justify-between gap-3 border-b pb-3'>
        <p className='text-xs font-semibold tracking-wide text-slate-400 uppercase'>
          <span className={isRequester ? 'text-brand-strong' : 'text-courier'}>
            {role}
          </span>{' '}
          · #{order.id.slice(0, 8)}
        </p>
        <span
          className={cn(
            'rounded-full px-2.5 py-1 text-xs font-semibold',
            STATUS_STYLES[order.status],
          )}
        >
          {STATUS_LABELS[order.status]}
        </span>
      </div>
      <h2 className='mt-3 font-bold break-words whitespace-pre-line text-slate-900'>
        {order.item_description}
      </h2>
      <p className='mt-1 flex items-center gap-1.5 text-sm text-slate-500'>
        <Store className='size-4 shrink-0' aria-hidden />
        {orderStoreName(order)} · {orderPickupLocation(order)}
      </p>
      <p className='mt-1 flex items-start gap-1.5 text-sm text-slate-500'>
        <ArrowRight className='mt-0.5 size-4 shrink-0' aria-hidden />
        <span className='min-w-0 break-words'>
          {[
            order.delivery_label,
            deliveryDetailsOf(order.delivery_label, order.delivery_details),
          ]
            .filter(Boolean)
            .join(' · ')}
        </span>
      </p>
      <p
        className={cn(
          'mt-3 text-xs',
          order.status === 'REJECTED' ? 'text-red-600' : 'text-slate-500',
        )}
      >
        {statusNote(order, role)}
      </p>

      {editing && (
        <div className='mt-4 rounded-xl border bg-slate-50 p-3'>
          <DropOffFields
            idPrefix={`drop-off-${order.id}`}
            value={dropOff}
            onChange={setDropOff}
            renderLabel={(htmlFor, text) => (
              <label
                htmlFor={htmlFor}
                className='mb-1.5 block text-xs font-bold text-slate-700'
              >
                {text}
              </label>
            )}
          />
          <div className='mt-3 flex gap-2'>
            <Button
              onClick={() =>
                delivery && run(() => changeDelivery(order.id, delivery))
              }
              disabled={!delivery || isPending}
              className={cn(actionClass, 'bg-courier hover:bg-courier/90')}
            >
              Save drop-off
            </Button>
            <Button
              variant='outline'
              onClick={() => setEditing(false)}
              disabled={isPending}
              className={actionClass}
            >
              Keep current
            </Button>
          </div>
        </div>
      )}

      {error && (
        <p role='alert' className='mt-3 text-sm text-red-600'>
          {error}
        </p>
      )}

      <div className='mt-auto flex flex-wrap items-center justify-between gap-2 pt-4'>
        <span className='text-xs text-slate-400'>
          {formatDateTime(order.created_at)}
        </span>
        <span className='text-brand-strong font-bold'>
          {order.credit_amount} cr
        </span>
      </div>

      <div className='flex flex-wrap gap-2 pt-3 empty:hidden'>
        {isRequester && order.status === 'PICKED_UP' && (
          <Button
            onClick={() => run(() => completeOrder(order.id))}
            disabled={isPending}
            className={cn(actionClass, 'bg-emerald-600 hover:bg-emerald-700')}
          >
            Confirm received
          </Button>
        )}
        {isRequester && beforePickup && !editing && (
          <Button
            variant='outline'
            onClick={() => {
              // Start from the current drop-off, not edits that were discarded.
              setDropOff(dropOffValueOf(order));
              setEditing(true);
            }}
            disabled={isPending}
            className={actionClass}
          >
            Change drop-off
          </Button>
        )}
        {isRequester && beforePickup && (
          <Button
            variant='outline'
            onClick={cancel}
            disabled={isPending}
            className={cn(actionClass, 'text-red-600 hover:text-red-700')}
          >
            Cancel errand
          </Button>
        )}
        {!isRequester && order.status === 'ACCEPTED' && (
          <Button
            onClick={() => run(() => pickUpOrder(order.id))}
            disabled={isPending}
            className={cn(actionClass, 'bg-courier hover:bg-courier/90')}
          >
            Mark picked up
          </Button>
        )}
      </div>
    </article>
  );
}

type ErrandListProps = {
  initialRole: OrderRole;
  initial: Record<OrderRole, PageResult<OrderView>>;
};

export function ErrandList({ initialRole, initial }: ErrandListProps) {
  const [role, setRole] = useState(initialRole);
  const lists = {
    requester: usePagedList(initial.requester, (window) =>
      loadMyOrders('requester', window),
    ),
    courier: usePagedList(initial.courier, (window) =>
      loadMyOrders('courier', window),
    ),
  };
  const current = lists[role];
  const isLoading = lists.requester.isLoading || lists.courier.isLoading;

  function selectRole(next: OrderRole) {
    setRole(next);
    // Keeps the tab on reload without a server round trip; replacing rather
    // than pushing keeps tab switches out of the back button's history.
    window.history.replaceState(null, '', `?role=${next}`);
  }

  // Both tabs, so the other tab's count stays current too.
  function refresh() {
    lists.requester.refresh();
    lists.courier.refresh();
  }

  return (
    <PageContainer>
      <PageHeader
        title='My Campus Errands'
        actions={
          <RefreshButton
            label='Refresh errands'
            onClick={refresh}
            loading={isLoading}
          />
        }
      >
        <div
          role='tablist'
          aria-label='Errand role'
          className='bg-brand-soft grid grid-cols-2 gap-1 rounded-xl p-1 md:max-w-sm'
        >
          {ROLE_TABS.map((tab) => {
            const active = role === tab.role;
            return (
              <button
                key={tab.role}
                type='button'
                role='tab'
                aria-selected={active}
                onClick={() => selectRole(tab.role)}
                className={cn(
                  'h-10 rounded-lg text-sm font-semibold transition-colors',
                  active
                    ? 'bg-brand text-white shadow-sm'
                    : 'text-brand-strong hover:bg-brand/20',
                )}
              >
                {tab.label} ({lists[tab.role].total})
              </button>
            );
          })}
        </div>
      </PageHeader>

      {current.error && (
        <ErrorBanner className='mx-4 mt-4 md:mx-0'>{current.error}</ErrorBanner>
      )}

      <CardGrid
        empty={
          !current.error && current.items.length === 0 && 'No errands yet.'
        }
      >
        {current.items.map((order) => (
          <ErrandCard
            key={order.id}
            order={order}
            role={role}
            // The card's own list: the tab may change while the action runs.
            onUpdate={current.replace}
          />
        ))}
      </CardGrid>

      {current.hasMore && (
        <LoadMoreButton
          onClick={current.loadMore}
          loading={isLoading}
          className='px-4 pt-6 md:px-0'
        />
      )}
    </PageContainer>
  );
}
