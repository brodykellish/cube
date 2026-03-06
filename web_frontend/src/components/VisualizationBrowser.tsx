import { useState, useEffect } from 'react'
import axios from 'axios'
import { useAPI } from '../hooks/useAPI'

interface ShaderFile {
  name: string
  path: string
  full_path: string
}

interface ShaderDirectory {
  [directory: string]: ShaderFile[]
}

export default function VisualizationBrowser() {
  const [shaders, setShaders] = useState<ShaderDirectory>({})
  const [videos, setVideos] = useState<ShaderDirectory>({})
  const [selectedDir, setSelectedDir] = useState<string | null>(null)
  const [selectedType, setSelectedType] = useState<'shader' | 'video'>('shader')
  const { deployPipeline } = useAPI()

  useEffect(() => {
    // Load shaders
    axios.get('/api/resources/shaders')
      .then(response => setShaders(response.data))
      .catch(error => console.error('Failed to load shaders:', error))

    // Load videos
    axios.get('/api/resources/videos')
      .then(response => setVideos(response.data))
      .catch(error => console.error('Failed to load videos:', error))
  }, [])

  const handleSelectResource = async (path: string, type: 'shader' | 'video') => {
    try {
      const source = type === 'shader' 
        ? { shader_path: path }
        : { video_path: path }
      
      await deployPipeline(source, [], 'surface')
    } catch (error) {
      console.error('Failed to deploy resource:', error)
    }
  }

  const directories = selectedType === 'shader' 
    ? Object.keys(shaders)
    : Object.keys(videos)

  const files = selectedDir 
    ? (selectedType === 'shader' ? shaders[selectedDir] : videos[selectedDir])
    : []

  return (
    <div className="p-4">
      <div className="mb-4">
        <div className="flex gap-2 mb-2">
          <button
            onClick={() => {
              setSelectedType('shader')
              setSelectedDir(null)
            }}
            className={`px-3 py-1 rounded text-sm ${
              selectedType === 'shader'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 hover:bg-gray-600'
            }`}
          >
            Shaders
          </button>
          <button
            onClick={() => {
              setSelectedType('video')
              setSelectedDir(null)
            }}
            className={`px-3 py-1 rounded text-sm ${
              selectedType === 'video'
                ? 'bg-blue-600 text-white'
                : 'bg-gray-700 hover:bg-gray-600'
            }`}
          >
            Videos
          </button>
        </div>
      </div>

      {!selectedDir ? (
        <div className="space-y-1">
          {directories.map(dir => (
            <button
              key={dir}
              onClick={() => setSelectedDir(dir)}
              className="w-full text-left px-3 py-2 rounded hover:bg-gray-700 flex items-center justify-between"
            >
              <span className="capitalize">{dir}</span>
              <span className="text-gray-400 text-sm">
                {selectedType === 'shader' 
                  ? shaders[dir]?.length || 0
                  : videos[dir]?.length || 0}
              </span>
            </button>
          ))}
        </div>
      ) : (
        <div>
          <button
            onClick={() => setSelectedDir(null)}
            className="mb-2 text-blue-400 hover:text-blue-300 text-sm"
          >
            ← Back
          </button>
          <div className="space-y-1 max-h-64 overflow-y-auto">
            {files.map(file => (
              <button
                key={file.path}
                onClick={() => handleSelectResource(file.path, selectedType)}
                className="w-full text-left px-3 py-2 rounded hover:bg-gray-700 text-sm"
              >
                {file.name}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}


