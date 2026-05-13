const STATUS_COLORS: Record<string, string> = {
  // Case statuses
  OPEN: 'bg-gray-100 text-gray-600',
  PARTY_A_FILED: 'bg-blue-100 text-blue-700',
  PARTY_B_RESPONDED: 'bg-purple-100 text-purple-700',
  IN_ARBITRATION: 'bg-amber-100 text-amber-700',
  VERDICT_DELIVERED: 'bg-green-100 text-green-700',
  // Document statuses
  PENDING: 'bg-gray-100 text-gray-500',
  PROCESSING: 'bg-yellow-100 text-yellow-700',
  DONE: 'bg-green-100 text-green-700',
  FAILED: 'bg-red-100 text-red-600',
}

const STATUS_LABELS: Record<string, string> = {
  OPEN: 'Open',
  PARTY_A_FILED: 'Filed',
  PARTY_B_RESPONDED: 'Responded',
  IN_ARBITRATION: 'In Arbitration',
  VERDICT_DELIVERED: 'Verdict Delivered',
  PENDING: 'Pending',
  PROCESSING: 'Processing…',
  DONE: 'Processed',
  FAILED: 'Failed',
}

interface Props {
  status: string
  small?: boolean
}

export default function StatusBadge({ status, small }: Props) {
  const color = STATUS_COLORS[status] || 'bg-gray-100 text-gray-600'
  const label = STATUS_LABELS[status] || status
  return (
    <span className={`inline-flex items-center rounded-full font-medium whitespace-nowrap ${color} ${small ? 'text-xs px-2 py-0.5' : 'text-sm px-3 py-1'}`}>
      {label}
    </span>
  )
}
