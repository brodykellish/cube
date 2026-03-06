# Quick Start Guide

## Start the Server

```bash
cd web_server
python3 app.py
```

**You should see:**
```
[WebServer] System running!
🎨 Open in browser: http://localhost:5001
```

## Open the Interface

Navigate to: **http://localhost:5001**

## What You'll See

### 📹 Live Preview (Top)
- Shows video stream when shader is loaded
- Displays FPS and latency
- Click canvas for fullscreen (not yet implemented)

### 🎨 Shaders Section
- **Click any shader card** to load it → Video auto-streams!
- **Filter by category**: Click buttons like "graphics", "effects", "templates"
- **Search**: Type in search box to find shaders by name
- **Active shader** has green border and "ACTIVE" badge

### 🎛️ Parameters Section
- 8 parameter sliders (iParam0-7)
- **Move slider** → Sends to visualization via WebSocket
- See values update in real-time

### ✨ Effects Section
- **Click any effect card** to toggle it on/off
- **Active effects** have green border and "ON" badge
- Works via WebSocket for instant response

### ⚙️ Presets Section
- **Click any preset** to load saved configuration
- Shows description and tags

## Controls

| Action | Result |
|--------|--------|
| Click shader | Loads shader, auto-starts streaming |
| Move slider | Updates parameter in real-time |
| Click effect | Toggles effect on/off |
| Click preset | Loads saved configuration |
| Type in search | Filters shader list |
| Click category | Filters by category |

## Status Bar

- **Gray**: Disconnected
- **Green**: Connected to WebSocket
- **Shows**: Current visualization name

## Troubleshooting

### Port already in use
```bash
lsof -ti :5001 | xargs kill -9
```

### Server won't start
- Check you're in `web_server/` directory
- Ensure dependencies installed: `pip install flask flask-socketio python-socketio flask-cors`

### WebSocket not connecting
- Check browser console (F12)
- Should see: `[WebSocket] Connected`
- If not, refresh page

### Video not streaming
- Click a shader first
- Check status bar shows green "Connected"
- Look for errors in browser console

### Shaders not loading
- Ensure shaders directory exists: `../shaders/`
- Check API response: Open DevTools → Network tab

## Features

✅ Click-to-load shaders
✅ Real-time parameter control
✅ Effect toggling
✅ Category filtering
✅ Search functionality
✅ Auto-streaming video
✅ WebSocket bidirectional control
✅ Active state indicators
✅ Loading feedback
✅ FPS/latency display

## Next Steps

1. **Load a shader**: Click "rainbow_spiral" or any shader
2. **Adjust parameters**: Move iParam0 slider and watch changes
3. **Try effects**: Click "TOGGLE_GLITCH" or other effects
4. **Experiment**: Try different shaders and parameter combinations

That's it! The interface is now fully functional with click-to-load and real-time controls.
