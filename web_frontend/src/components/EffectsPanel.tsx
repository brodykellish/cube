import { useState, useEffect } from 'react'
import axios from 'axios'
import { useAPI } from '../hooks/useAPI'

interface Effect {
  action: string
  shader: string
  node_class: string
  trigger_mode: string
  priority: number
}

export default function EffectsPanel() {
  const [effects, setEffects] = useState<Effect[]>([])
  const [activeEffects, setActiveEffects] = useState<Set<string>>(new Set())
  const { enableEffect, disableEffect, statusInfo } = useAPI()

  useEffect(() => {
    axios.get('/api/effects')
      .then(response => setEffects(response.data))
      .catch(error => console.error('Failed to load effects:', error))
  }, [])

  useEffect(() => {
    if (statusInfo?.active_effects) {
      setActiveEffects(new Set(statusInfo.active_effects))
    }
  }, [statusInfo])

  const handleToggleEffect = async (action: string) => {
    const isActive = activeEffects.has(action)
    try {
      if (isActive) {
        await disableEffect(action)
        setActiveEffects(prev => {
          const next = new Set(prev)
          next.delete(action)
          return next
        })
      } else {
        await enableEffect(action)
        setActiveEffects(prev => new Set(prev).add(action))
      }
    } catch (error) {
      console.error('Failed to toggle effect:', error)
    }
  }

  return (
    <div className="p-4 border-t border-gray-700">
      <h3 className="text-sm font-semibold mb-3 text-gray-300">Effects</h3>
      <div className="space-y-1 max-h-64 overflow-y-auto">
        {effects.map(effect => {
          const isActive = activeEffects.has(effect.action)
          return (
            <button
              key={effect.action}
              onClick={() => handleToggleEffect(effect.action)}
              className={`w-full text-left px-3 py-2 rounded text-sm flex items-center justify-between ${
                isActive
                  ? 'bg-blue-600 hover:bg-blue-700'
                  : 'bg-gray-700 hover:bg-gray-600'
              }`}
            >
              <span className="truncate">{effect.action.replace('TOGGLE_', '').replace('TRIGGER_', '')}</span>
              {isActive && (
                <span className="text-xs bg-green-500 px-2 py-0.5 rounded">ON</span>
              )}
            </button>
          )
        })}
      </div>
    </div>
  )
}


