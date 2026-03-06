# Web Frontend Setup Guide

This guide explains how to set up and run the Flask backend and React frontend for the cube visualization system.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│              React Frontend (Port 3000)                 │
│  - TypeScript + Vite                                    │
│  - Tailwind CSS                                         │
│  - D3.js for DAG visualization                          │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP/REST API
                       │ (Proxy via Vite)
                       ▼
┌─────────────────────────────────────────────────────────┐
│            Flask Backend (Port 5000)                    │
│  - REST API endpoints                                   │
│  - CORS enabled                                          │
└──────────────────────┬──────────────────────────────────┘
                       │
                       │ Uses
                       ▼
┌─────────────────────────────────────────────────────────┐
│         VisualizationAPI (cube/api/)                    │
│  - Thread-safe visualization management                 │
│  - Parameter updates                                    │
│  - Effect management                                    │
└─────────────────────────────────────────────────────────┘
```

## Prerequisites

- Python 3.8+ with pip
- Node.js 18+ with npm
- The cube visualization system installed and configured

## Backend Setup

1. Navigate to the web server directory:
```bash
cd web_server
```

2. Install Python dependencies:
```bash
pip install -r requirements.txt
```

3. Start the Flask server:
```bash
python run_server.py
```

The server will start on `http://127.0.0.1:5000`

## Frontend Setup

1. Navigate to the frontend directory:
```bash
cd web_frontend
```

2. Install Node.js dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

The frontend will be available at `http://localhost:3000`

## Usage

1. **Start both servers**: Run the Flask backend first, then the React frontend
2. **Open browser**: Navigate to `http://localhost:3000`
3. **Start visualization**: Click the "Start" button in the header
4. **Browse resources**: Use the left sidebar to browse shaders and videos
5. **Select visualization**: Click on a shader or video to deploy it
6. **Control effects**: Use the effects panel to enable/disable effects
7. **Adjust parameters**: Use the Parameters tab to control shader parameters
8. **Edit DAG**: Use the DAG Editor tab to visualize and modify the node graph

## API Endpoints

### Visualization Control
- `POST /api/visualization/start` - Start visualization
- `POST /api/visualization/stop` - Stop visualization
- `GET /api/status` - Get current status

### Pipeline Management
- `POST /api/pipeline/deploy` - Deploy a DAG pipeline

### Parameters
- `POST /api/parameters` - Update parameters (single or batch)
- `GET /api/parameters` - Get all parameter values

### Effects
- `GET /api/effects` - List all available effects
- `POST /api/effects/<action_name>/enable` - Enable an effect
- `POST /api/effects/<action_name>/disable` - Disable an effect

### Settings
- `GET /api/settings` - Get all settings
- `POST /api/settings` - Update a setting

### Resources
- `GET /api/resources/shaders` - List all shader files by directory
- `GET /api/resources/videos` - List all video files by directory

## Frontend Features

### Visualization Browser
- Browse shaders organized by directory (primitives, graphics, effects, etc.)
- Browse videos organized by directory
- Click to deploy a shader or video as the visualization source

### Effects Panel
- List of all available effects
- Toggle effects on/off
- Visual indicators for active effects

### DAG Editor
- Interactive node-based graph visualization
- Drag-and-drop node positioning
- Visual representation of the rendering pipeline
- (Basic implementation - can be extended for full editing)

### Parameters Panel
- Real-time parameter control
- Sliders for numeric parameters
- Support for vector parameters (arrays)
- Updates applied immediately to visualization

### Audio Stats
- Placeholder for audio signal monitoring
- Will display audio input statistics when implemented

## Development

### Backend Development
- Edit `web_server/app.py` to add new endpoints
- The Flask server auto-reloads in debug mode

### Frontend Development
- Edit React components in `web_frontend/src/components/`
- Vite provides hot module replacement for instant updates
- TypeScript provides type checking

### Adding New Features

1. **New API Endpoint**:
   - Add route in `web_server/app.py`
   - Add corresponding function in `web_frontend/src/hooks/useAPI.ts`
   - Use the hook in components

2. **New Frontend Component**:
   - Create component in `web_frontend/src/components/`
   - Import and use in `App.tsx`

3. **Styling**:
   - Use Tailwind CSS classes
   - Custom styles in `web_frontend/src/index.css`

## Troubleshooting

### Backend won't start
- Check that all Python dependencies are installed
- Verify the cube module is importable (check PYTHONPATH)
- Check that port 5000 is not in use

### Frontend won't connect
- Ensure the Flask backend is running on port 5000
- Check browser console for CORS errors
- Verify Vite proxy configuration in `vite.config.ts`

### Visualizations don't start
- Check that the visualization API is properly initialized
- Verify MIDI state is configured (if using MIDI)
- Check backend logs for errors

## Production Deployment

For production:
1. Build the frontend: `npm run build` in `web_frontend/`
2. Serve static files from Flask or a web server
3. Configure CORS appropriately
4. Use a production WSGI server (gunicorn, uWSGI, etc.)

## Next Steps

- Implement full DAG editor with node creation/deletion
- Add audio signal visualization
- Implement parameter presets
- Add pipeline save/load functionality
- Add real-time preview of parameter changes


