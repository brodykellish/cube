import { useState, useEffect } from 'react'
import axios from 'axios'

interface AudioStats {
  available: boolean
  message?: string
  [key: string]: any
}

export default function AudioStats() {
  const [stats, setStats] = useState<AudioStats>({ available: false })

  useEffect(() => {
    const fetchStats = () => {
      axios.get('/api/audio/stats')
        .then(response => setStats(response.data))
        .catch(error => console.error('Failed to load audio stats:', error))
    }

    fetchStats()
    const interval = setInterval(fetchStats, 1000) // Poll every second
    return () => clearInterval(interval)
  }, [])

  return (
    <div className="p-4">
      <h3 className="text-sm font-semibold mb-3 text-gray-300">Audio Signal</h3>
      {stats.available ? (
        <div className="space-y-2">
          {/* Audio stats will be displayed here when implemented */}
          <div className="text-sm text-gray-400">
            Audio input monitoring will be displayed here
          </div>
        </div>
      ) : (
        <div className="text-sm text-gray-500">
          {stats.message || 'Audio stats not available'}
        </div>
      )}
    </div>
  )
}


