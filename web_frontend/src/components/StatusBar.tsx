import { useAPI } from '../hooks/useAPI'

export default function StatusBar() {
  const { status, statusInfo } = useAPI()

  const getStatusColor = () => {
    switch (status) {
      case 'running':
        return 'bg-green-500'
      case 'starting':
        return 'bg-yellow-500'
      case 'stopping':
        return 'bg-orange-500'
      case 'error':
        return 'bg-red-500'
      default:
        return 'bg-gray-500'
    }
  }

  return (
    <div className="flex items-center gap-3">
      <div className="flex items-center gap-2">
        <div className={`w-2 h-2 rounded-full ${getStatusColor()}`} />
        <span className="text-sm capitalize">{status}</span>
      </div>
      {statusInfo?.error && (
        <span className="text-xs text-red-400">{statusInfo.error}</span>
      )}
    </div>
  )
}


