import { useState, useEffect } from 'react'
import VisualizationBrowser from './components/VisualizationBrowser'
import EffectsPanel from './components/EffectsPanel'
import DAGEditor from './components/DAGEditor'
import ParametersPanel from './components/ParametersPanel'
import AudioStats from './components/AudioStats'
import StatusBar from './components/StatusBar'
import { useAPI } from './hooks/useAPI'

function App() {
  const { status, startVisualization, stopVisualization } = useAPI()
  const [activeTab, setActiveTab] = useState<'browser' | 'dag' | 'parameters'>('browser')

  return (
    <div className="min-h-screen bg-gray-900 text-gray-100">
      <div className="flex flex-col h-screen">
        {/* Header */}
        <header className="bg-gray-800 border-b border-gray-700 px-4 py-3">
          <div className="flex items-center justify-between">
            <h1 className="text-2xl font-bold">Cube Visualization Control</h1>
            <div className="flex items-center gap-4">
              <StatusBar />
              <button
                onClick={() => status === 'running' ? stopVisualization() : startVisualization()}
                className={`px-4 py-2 rounded ${
                  status === 'running'
                    ? 'bg-red-600 hover:bg-red-700'
                    : 'bg-green-600 hover:bg-green-700'
                }`}
              >
                {status === 'running' ? 'Stop' : 'Start'}
              </button>
            </div>
          </div>
        </header>

        {/* Main Content */}
        <div className="flex-1 flex overflow-hidden">
          {/* Left Sidebar - Resources */}
          <div className="w-64 bg-gray-800 border-r border-gray-700 flex flex-col">
            <div className="p-4 border-b border-gray-700">
              <h2 className="text-lg font-semibold">Resources</h2>
            </div>
            <div className="flex-1 overflow-y-auto">
              <VisualizationBrowser />
            </div>
            <div className="border-t border-gray-700">
              <EffectsPanel />
            </div>
          </div>

          {/* Center - Main Editor */}
          <div className="flex-1 flex flex-col">
            {/* Tabs */}
            <div className="bg-gray-800 border-b border-gray-700 flex">
              <button
                onClick={() => setActiveTab('browser')}
                className={`px-6 py-3 ${
                  activeTab === 'browser'
                    ? 'bg-gray-700 border-b-2 border-blue-500'
                    : 'hover:bg-gray-700'
                }`}
              >
                Browser
              </button>
              <button
                onClick={() => setActiveTab('dag')}
                className={`px-6 py-3 ${
                  activeTab === 'dag'
                    ? 'bg-gray-700 border-b-2 border-blue-500'
                    : 'hover:bg-gray-700'
                }`}
              >
                DAG Editor
              </button>
              <button
                onClick={() => setActiveTab('parameters')}
                className={`px-6 py-3 ${
                  activeTab === 'parameters'
                    ? 'bg-gray-700 border-b-2 border-blue-500'
                    : 'hover:bg-gray-700'
                }`}
              >
                Parameters
              </button>
            </div>

            {/* Tab Content */}
            <div className="flex-1 overflow-auto">
              {activeTab === 'browser' && (
                <div className="p-6">
                  <h2 className="text-xl font-semibold mb-4">Visualization Browser</h2>
                  <p className="text-gray-400">Select a shader or video from the left sidebar to start.</p>
                </div>
              )}
              {activeTab === 'dag' && <DAGEditor />}
              {activeTab === 'parameters' && <ParametersPanel />}
            </div>
          </div>

          {/* Right Sidebar - Audio Stats */}
          <div className="w-64 bg-gray-800 border-l border-gray-700">
            <AudioStats />
          </div>
        </div>
      </div>
    </div>
  )
}

export default App

