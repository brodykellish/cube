import { useState, useEffect, useCallback } from 'react'
import axios from 'axios'

const API_BASE = '/api'

export interface VisualizationStatus {
  status: string
  is_running: boolean
  error: string | null
  settings: Record<string, any>
  parameters?: Record<string, any>
  active_effects?: string[]
}

export function useAPI() {
  const [status, setStatus] = useState<'stopped' | 'starting' | 'running' | 'stopping' | 'error'>('stopped')
  const [statusInfo, setStatusInfo] = useState<VisualizationStatus | null>(null)

  const fetchStatus = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE}/status`)
      setStatusInfo(response.data)
      setStatus(response.data.status)
    } catch (error) {
      console.error('Failed to fetch status:', error)
    }
  }, [])

  useEffect(() => {
    fetchStatus()
    const interval = setInterval(fetchStatus, 1000) // Poll every second
    return () => clearInterval(interval)
  }, [fetchStatus])

  const startVisualization = useCallback(async () => {
    try {
      await axios.post(`${API_BASE}/visualization/start`)
      await fetchStatus()
    } catch (error) {
      console.error('Failed to start visualization:', error)
    }
  }, [fetchStatus])

  const stopVisualization = useCallback(async () => {
    try {
      await axios.post(`${API_BASE}/visualization/stop`)
      await fetchStatus()
    } catch (error) {
      console.error('Failed to stop visualization:', error)
    }
  }, [fetchStatus])

  const deployPipeline = useCallback(async (source: any, effects: any[] = [], pixelMapper: string = 'surface') => {
    try {
      await axios.post(`${API_BASE}/pipeline/deploy`, {
        source,
        effects,
        pixel_mapper: pixelMapper,
      })
      await fetchStatus()
    } catch (error) {
      console.error('Failed to deploy pipeline:', error)
      throw error
    }
  }, [fetchStatus])

  const setParameter = useCallback(async (name: string, value: any) => {
    try {
      await axios.post(`${API_BASE}/parameters`, { name, value })
    } catch (error) {
      console.error('Failed to set parameter:', error)
      throw error
    }
  }, [])

  const setParameters = useCallback(async (parameters: Record<string, any>) => {
    try {
      await axios.post(`${API_BASE}/parameters`, { parameters })
    } catch (error) {
      console.error('Failed to set parameters:', error)
      throw error
    }
  }, [])

  const enableEffect = useCallback(async (actionName: string) => {
    try {
      await axios.post(`${API_BASE}/effects/${actionName}/enable`)
      await fetchStatus()
    } catch (error) {
      console.error('Failed to enable effect:', error)
      throw error
    }
  }, [fetchStatus])

  const disableEffect = useCallback(async (actionName: string) => {
    try {
      await axios.post(`${API_BASE}/effects/${actionName}/disable`)
      await fetchStatus()
    } catch (error) {
      console.error('Failed to disable effect:', error)
      throw error
    }
  }, [fetchStatus])

  const setSetting = useCallback(async (name: string, value: any) => {
    try {
      await axios.post(`${API_BASE}/settings`, { name, value })
      await fetchStatus()
    } catch (error) {
      console.error('Failed to set setting:', error)
      throw error
    }
  }, [fetchStatus])

  return {
    status,
    statusInfo,
    startVisualization,
    stopVisualization,
    deployPipeline,
    setParameter,
    setParameters,
    enableEffect,
    disableEffect,
    setSetting,
    refreshStatus: fetchStatus,
  }
}


