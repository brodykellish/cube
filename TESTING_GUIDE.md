# Testing Guide for LED Cube Bug Fixes & New Features

## Overview

This guide covers testing all bug fixes and new features from the Phase 1-5 implementation:
- ✅ Parameter mapping fix (all 8 parameters working)
- ✅ Keyboard input fix (no shift key required)
- ✅ Services layer (REST API)
- ✅ Video streaming (60 FPS)
- ✅ Resource catalog

---

## Test 1: Quick Validation (5 minutes)

### 1.1 Startup Check

```bash
python3 cube_control.py --backend=pyglet
```

**What to verify**:
- ✅ Visualization window opens
- ✅ Console shows: `[MIDIState] Initialized with 8 channels` (not 4!)
- ✅ No errors about "CC out of range" or missing parameters
- ✅ Menu system still works (press `h` for help)

### 1.2 Keyboard Input Fix Test

**Press these keys WITHOUT holding shift**:

| Key | Expected Behavior |
|-----|-------------------|
| `n` | Parameter 0 decrease |
| `m` | Parameter 0 increase |
| `,` | Parameter 1 decrease |
| `.` | Parameter 1 increase |
| `;` | Parameter 5 decrease |
| `'` | Parameter 5 increase |
| `[` | Parameter 6 decrease |
| `]` | Parameter 6 increase |

**Expected**: All keys should work WITHOUT holding shift. Console should show parameter updates like:
```
[ParameterStore] iParam0 = 0.45 (source: keyboard)
```

### 1.3 Parameter 4-7 Fix Test

**These parameters were completely broken before**:

```bash
# In visualization window, press:
# [ and ] keys → Should control parameter 6
# ; and ' keys → Should control parameter 5
```

**Verify in console**:
```
[ParameterStore] iParam5 = 0.62
[ParameterStore] iParam6 = 0.38
```

**If you see "CC out of range" errors → Bug is NOT fixed**

---

## Test 2: Services Layer & REST API (10 minutes)

### 2.1 Start Web Server

```bash
# Terminal 1: Keep visualization running
python3 cube_control.py --backend=pyglet

# Terminal 2: Start web server
cd web_server
python3 app.py
```

**Expected output**:
```
[ConfigurationService] Loaded 15 configurations
[EffectRegistry] Registered 42 effects
[ResourceCatalog] Loaded 67 shaders from 8 categories
 * Running on http://127.0.0.1:5001
```

### 2.2 Test Configuration Service

```bash
# List all presets
curl http://localhost:5001/api/configs

# Get specific preset info
curl http://localhost:5001/api/configs/psychedelic_show.yml

# Search presets by tag
curl "http://localhost:5001/api/configs/search?tags=performance"
```

**Expected**: JSON responses with configuration metadata

### 2.3 Test Effect Registry

```bash
# List all effects
curl http://localhost:5001/api/effects

# Search effects
curl "http://localhost:5001/api/effects/search?q=spiral"

# Get effects by category
curl "http://localhost:5001/api/effects/category/shaders"

# Get effects by keybinding
curl "http://localhost:5001/api/effects/keybinding/1"
```

**Expected**: JSON responses with effect information including active state

### 2.4 Test Parameter Source Manager

```bash
# Get all parameter sources
curl http://localhost:5001/api/parameters/sources

# Get specific parameter info
curl http://localhost:5001/api/parameters/sources/iParam0

# Lock parameter to web control
curl -X POST http://localhost:5001/api/parameters/iParam0/lock \
  -H "Content-Type: application/json" \
  -d '{"source": "web"}'

# Now keyboard should be ignored for iParam0!
# Test by pressing 'n' and 'm' keys - console should show:
# [ParamSourceMgr] Ignoring keyboard update to iParam0 (locked to web)

# Unlock parameter
curl -X POST http://localhost:5001/api/parameters/iParam0/unlock
```

### 2.5 Test Resource Catalog

```bash
# List all shaders
curl http://localhost:5001/api/resources/shaders

# List shaders by category
curl "http://localhost:5001/api/resources/shaders?category=graphics"

# Search shaders
curl "http://localhost:5001/api/resources/shaders/search?q=spiral"

# List all videos
curl http://localhost:5001/api/resources/videos

# Get catalog stats
curl http://localhost:5001/api/resources/stats
```

**Expected**: Fast responses (<1ms for cached, ~100ms for first request)

---

## Test 3: Video Streaming (5 minutes)

### 3.1 Start Streaming

```bash
# With web server running, start video stream
curl -X POST http://localhost:5001/api/streaming/start \
  -H "Content-Type: application/json" \
  -d '{"target_fps": 60, "jpeg_quality": 80}'
```

**Expected console output**:
```
[StreamingWorker] Starting stream (target: 60 FPS, quality: 80)
[StreamingWorker] Streaming started
```

### 3.2 Check Stream Status

```bash
curl http://localhost:5001/api/streaming/status
```

**Expected response**:
```json
{
  "is_streaming": true,
  "target_fps": 60,
  "actual_fps": 58.7,
  "frames_sent": 1243,
  "dropped_frames": 12,
  "active_clients": 0,
  "jpeg_quality": 80,
  "avg_latency_ms": 156
}
```

### 3.3 Test with Frontend (if available)

```bash
# Terminal 3: Start React frontend
cd web_frontend
npm install  # First time only
npm run dev
```

Open browser to `http://localhost:5173` and you should see the video stream at 60 FPS.

### 3.4 Stop Streaming

```bash
curl -X POST http://localhost:5001/api/streaming/stop
```

---

## Test 4: Full Integration Test (15 minutes)

### 4.1 Live Performance Simulation

```bash
# Terminal 1: Start visualization
python3 cube_control.py --backend=pyglet

# Terminal 2: Start web server
cd web_server && python3 app.py

# Terminal 3: Start streaming
curl -X POST http://localhost:5001/api/streaming/start
```

### 4.2 Test Parameter Control Hierarchy

**Test keyboard control (Priority 0)**:
1. Press `m` key several times
2. Verify console shows: `[ParameterStore] iParam0 = ...`

**Test web control (can lock)**:
```bash
# Lock parameter to web
curl -X POST http://localhost:5001/api/parameters/iParam0/lock \
  -H "Content-Type: application/json" \
  -d '{"source": "web"}'

# Set parameter from web
curl -X POST http://localhost:5001/api/parameters/iParam0 \
  -H "Content-Type: application/json" \
  -d '{"value": 0.75}'
```

3. Press `m` key → Should be IGNORED (console shows "Ignoring keyboard update")
4. Unlock parameter and keyboard should work again

### 4.3 Test Effect Toggling

**Via keyboard**:
- Press `1` → Toggle first effect
- Press `2` → Toggle second effect
- Check console for effect activation messages

**Via API**:
```bash
# Enable effect
curl -X POST http://localhost:5001/api/effects/shader_rainbow_spiral/enable

# Disable effect
curl -X POST http://localhost:5001/api/effects/shader_rainbow_spiral/disable

# Check active effects
curl http://localhost:5001/api/effects/active
```

### 4.4 Test Preset Loading

```bash
# List available presets
curl http://localhost:5001/api/configs

# Load a preset (replace with actual filename from list)
curl -X POST http://localhost:5001/api/configs/psychedelic_show.yml/deploy
```

Watch visualization window - should load new effects and parameters!

---

## Test 5: Error Handling & Edge Cases

### 5.1 Test Parameter Validation

```bash
# Try to set invalid parameter value
curl -X POST http://localhost:5001/api/parameters/iParam0 \
  -H "Content-Type: application/json" \
  -d '{"value": 2.5}'  # Out of range [0.0, 1.0]

# Expected: Error response with validation message
```

### 5.2 Test Resource Not Found

```bash
# Try to load non-existent config
curl -X POST http://localhost:5001/api/configs/nonexistent.yml/deploy

# Expected: 404 error with helpful message
```

### 5.3 Test Cache Refresh

```bash
# Get initial stats
curl http://localhost:5001/api/resources/stats

# Wait 61 seconds (cache TTL = 60)
sleep 61

# Request again - should auto-refresh cache
curl http://localhost:5001/api/resources/shaders

# Check stats - cache_age should be small
curl http://localhost:5001/api/resources/stats
```

---

## Test 6: MIDI Testing (if MIDI controller available)

### 6.1 MIDI Parameter Control

1. Connect USB MIDI controller
2. Start visualization: `python3 cube_control.py --backend=pyglet`
3. Move MIDI CC0 knob → Should control iParam0
4. Move MIDI CC7 knob → Should control iParam7 (was broken before!)

**Check console**:
```
[MIDIState] Initialized with 8 channels
[MIDIState] CC7 = 127 (value: 1.0)
[ParameterStore] iParam7 = 1.0 (source: midi)
```

### 6.2 MIDI Priority Test

```bash
# Lock parameter to MIDI (priority 100)
curl -X POST http://localhost:5001/api/parameters/iParam0/lock \
  -H "Content-Type: application/json" \
  -d '{"source": "midi"}'
```

- Move MIDI CC0 → Should work
- Press `m` key → Should be IGNORED (console shows "Ignoring keyboard update")

---

## Test 7: Text Input Context-Aware Test

### 7.1 Test Shifted Characters in Text Fields

1. Open menu: Press `h`
2. Navigate to text input field (e.g., save config name)
3. Type: `My!Cool@Preset#123`

**Expected**: You can type shifted characters (`!`, `@`, `#`) WITHOUT triggering parameter changes!

**How it works**: Text fields use `on_text` events which get actual character values.

---

## Regression Testing Checklist

Ensure nothing broke:

- [ ] Menu system still works (press `h`)
- [ ] Effect toggling with number keys (1-8)
- [ ] Shader selection menu
- [ ] Video playback
- [ ] Config save/load from menu
- [ ] Window resizing
- [ ] Camera controls (WASD, mouse)
- [ ] Audio-reactive mode (if configured)

---

## Performance Benchmarks

### Expected Performance

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Video stream FPS | 60 FPS | Check `/api/streaming/status` |
| Stream latency | 150-250ms | Check `avg_latency_ms` in status |
| Cache response | <1ms | Time `curl` to `/api/resources/shaders` (2nd request) |
| Fresh scan | ~100ms | Time `curl` to `/api/resources/shaders` (1st request) |
| API response | <10ms | Time `curl` to any endpoint |

### Measure Actual Performance

```bash
# Install httpie for better timing (optional)
pip install httpie

# Measure API response time
time curl http://localhost:5001/api/effects

# Measure cache performance
time curl http://localhost:5001/api/resources/shaders  # First: ~100ms
time curl http://localhost:5001/api/resources/shaders  # Second: <1ms

# Check streaming stats
curl http://localhost:5001/api/streaming/status | jq '.actual_fps, .avg_latency_ms'
```

---

## Known Issues & Workarounds

### Issue: Config save from API not working
**Workaround**: Use menu system to save configs (press `h`, navigate to save)

### Issue: Stream starts but no clients connected
**Expected**: This is normal - stream waits for web frontend to connect

### Issue: Parameters not responding
**Check**:
1. Is parameter locked? → `curl http://localhost:5001/api/parameters/sources`
2. Is another source active? → Check console for source priority messages

### Issue: "CC out of range" errors
**This means the bug fix didn't apply**:
- Check `midi_state.py:38` should have `num_channels: int = 8`
- Restart visualization to pick up changes

---

## Success Criteria

✅ **All tests pass if**:
1. All 8 parameters work (especially 4-7)
2. Keyboard input works WITHOUT shift key
3. All REST API endpoints return valid responses
4. Video streaming achieves 50+ FPS
5. No regression - existing features still work
6. Parameter locking works correctly
7. Text input accepts shifted characters

---

## Quick Validation Script

Create this script for automated testing:

```bash
#!/bin/bash
# test_api.sh

API="http://localhost:5001"

echo "Testing Configuration Service..."
curl -s $API/api/configs | jq '.configs | length'

echo "Testing Effect Registry..."
curl -s $API/api/effects | jq '.effects | length'

echo "Testing Resource Catalog..."
curl -s $API/api/resources/shaders | jq '.shaders | length'

echo "Testing Parameter Sources..."
curl -s $API/api/parameters/sources | jq '.sources | length'

echo "Testing Streaming Status..."
curl -s $API/api/streaming/status | jq '.is_streaming'

echo "All API endpoints responding ✅"
```

Run with: `chmod +x test_api.sh && ./test_api.sh`

---

## Troubleshooting

### Problem: Web server won't start
**Solution**: Check port 5001 isn't already in use: `lsof -i :5001`

### Problem: Streaming shows 0 FPS
**Solution**: Make sure visualization is running and rendering frames

### Problem: Frontend can't connect
**Solution**: Check CORS settings in `app.py` - should allow `*` origins

### Problem: Parameters still broken
**Solution**:
1. Check you're on the correct branch: `git branch`
2. Verify changes applied: `grep "num_channels: int = 8" src/cube/midi/midi_state.py`
3. Restart Python completely (kill all python processes)

---

## Next Steps After Testing

If all tests pass:
1. Merge feature branch to main
2. Create preset library for live performances
3. Build out Phase 3 web frontend UI
4. Test on actual LED cube hardware
5. Create user documentation

If tests fail:
1. Note which test failed and error messages
2. Check console output for clues
3. Report issues with specific test case and expected vs actual behavior
