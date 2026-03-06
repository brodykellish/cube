import { useState, useEffect } from 'react'
import { useAPI } from '../hooks/useAPI'

export default function ParametersPanel() {
  const { statusInfo, setParameter } = useAPI()
  const [parameters, setParameters] = useState<Record<string, any>>({})

  useEffect(() => {
    if (statusInfo?.parameters) {
      setParameters(statusInfo.parameters)
    }
  }, [statusInfo])

  const handleParameterChange = async (name: string, value: any) => {
    setParameters(prev => ({ ...prev, [name]: value }))
    try {
      await setParameter(name, value)
    } catch (error) {
      console.error('Failed to update parameter:', error)
    }
  }

  // Filter to show only iParam parameters and a few others
  const displayParams = Object.entries(parameters)
    .filter(([name]) => 
      name.startsWith('iParam') || 
      ['iMouse', 'iSeed', 'iBeatPulse', 'iBeatPhase'].includes(name)
    )

  return (
    <div className="p-6">
      <h2 className="text-xl font-semibold mb-4">Parameters</h2>
      <div className="space-y-4">
        {displayParams.map(([name, value]) => (
          <div key={name} className="bg-gray-800 rounded-lg p-4">
            <label className="block text-sm font-medium mb-2">{name}</label>
            {typeof value === 'number' ? (
              <div>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.01"
                  value={value}
                  onChange={(e) => handleParameterChange(name, parseFloat(e.target.value))}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-gray-400 mt-1">
                  <span>0</span>
                  <span className="font-mono">{value.toFixed(3)}</span>
                  <span>1</span>
                </div>
              </div>
            ) : Array.isArray(value) ? (
              <div className="space-y-2">
                {value.map((v, i) => (
                  <div key={i} className="flex items-center gap-2">
                    <span className="text-xs text-gray-400 w-8">[{i}]</span>
                    <input
                      type="range"
                      min="0"
                      max="1"
                      step="0.01"
                      value={v}
                      onChange={(e) => {
                        const newValue = [...value]
                        newValue[i] = parseFloat(e.target.value)
                        handleParameterChange(name, newValue)
                      }}
                      className="flex-1"
                    />
                    <span className="text-xs text-gray-400 w-12 font-mono">{v.toFixed(3)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-gray-400 text-sm">{String(value)}</div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}


