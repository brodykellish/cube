# Cube Web Frontend

React + TypeScript frontend for cube visualization control, built with Vite and Tailwind CSS.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Start development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Build

```bash
npm run build
```

## Features

- **Visualization Browser**: Browse and select shaders and videos organized by directory
- **Effects Panel**: Enable/disable effects with visual indicators
- **DAG Editor**: Interactive node-based graph editor (basic implementation with d3.js)
- **Parameters Panel**: Real-time parameter control with sliders
- **Audio Stats**: Audio signal monitoring (placeholder)
- **Status Bar**: Real-time visualization status

## Project Structure

```
src/
├── components/
│   ├── VisualizationBrowser.tsx  # Shader/video browser
│   ├── EffectsPanel.tsx          # Effects list and toggle
│   ├── DAGEditor.tsx             # Node-based DAG editor
│   ├── ParametersPanel.tsx       # Parameter controls
│   ├── AudioStats.tsx            # Audio signal display
│   └── StatusBar.tsx              # Status indicator
├── hooks/
│   └── useAPI.ts                  # API integration hook
├── App.tsx                        # Main app component
└── main.tsx                       # Entry point
```

## Development

The frontend proxies API requests to the Flask backend running on port 5000. Make sure the backend is running before starting the frontend.


