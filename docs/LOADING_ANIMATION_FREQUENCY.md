# Loading Animation Frequency Change

## Change Summary

The loading ellipsis animation frequency has been reduced from ~60 FPS (every frame) to 1 FPS (once per second) for improved readability.

## Implementation

### Modified Files

**src/cube/menu/prompt_menu.py**

### Changes

1. **Added animation timer** (line 68):
```python
self.loading_animation_time = 0  # Timer for loading ellipsis animation
```

2. **Added timer reset** when generation starts (line 345):
```python
self.loading_animation_time = 0  # Reset animation timer
```

3. **Modified update() method** to throttle animation (lines 537-552):
```python
# Animate loading ellipsis at 1 FPS (once per second)
if self.is_generating and self.text_box.lines:
    self.loading_animation_time += dt
    if self.loading_animation_time >= 1.0:  # Update every 1 second
        self.loading_animation_time = 0
        # Find the loading message
        for i in range(len(self.text_box.lines) - 1, -1, -1):
            if self.text_box.lines[i].startswith("cube: ."):
                # Cycle through . .. ... ....
                current = self.text_box.lines[i]
                dots = current.count('.')
                if dots >= 4:
                    self.text_box.lines[i] = "cube: ."
                else:
                    self.text_box.lines[i] = "cube: " + "." * (dots + 1)
                break
```

## Behavior

### Before
```
Frame 0: cube: .
Frame 1: cube: ..
Frame 2: cube: ...
Frame 3: cube: ....
Frame 4: cube: .
...
(Cycles every 4 frames = ~0.067 seconds at 60 FPS)
```

### After
```
Second 0: cube: .
Second 1: cube: ..
Second 2: cube: ...
Second 3: cube: ....
Second 4: cube: .
...
(Cycles every 4 seconds)
```

## Rationale

1. **Readability**: 60 FPS animation was too fast to be useful
2. **Visual Clarity**: 1 FPS provides smooth, easily readable progress indication
3. **Performance**: Reduces unnecessary text buffer modifications
4. **Consistency**: Matches common loading indicator patterns

## Technical Details

- **Timer Accumulation**: `self.loading_animation_time += dt` accumulates frame time
- **Update Threshold**: Animation updates when accumulated time ≥ 1.0 seconds
- **Timer Reset**: Timer resets to 0 after each animation update
- **State Isolation**: Only affects visual animation, not generation speed

## Impact

- ✅ More readable loading indicator
- ✅ Clearer progress feedback
- ✅ Slightly reduced CPU usage (fewer text updates)
- ✅ No change to actual generation performance
- ✅ UI still updates at 60 FPS (only animation throttled)

## Example Usage

When user submits a shader generation request:

```
t=0.0s:  cube: .
t=1.0s:  cube: ..
t=2.0s:  cube: ...
t=3.0s:  cube: ....
t=4.0s:  cube: .     (cycles)
t=5.0s:  cube: ..
...
(continues until generation completes)
```

User can clearly see that:
- The system is working (animation continues)
- Time is passing (dots increase periodically)
- The request hasn't hung or frozen

## Configuration

To change the update frequency, modify the threshold in `prompt_menu.py:540`:

```python
# Current: 1 FPS (update every 1 second)
if self.loading_animation_time >= 1.0:

# Examples:
if self.loading_animation_time >= 0.5:  # 2 FPS (twice per second)
if self.loading_animation_time >= 2.0:  # 0.5 FPS (every 2 seconds)
```

## Related Systems

This change works in conjunction with:
- Async shader generation (background threading)
- Menu update system (MenuNavigator.update())
- Cursor blink animation (0.5s interval, unaffected)
- Main render loop (60 FPS, unaffected)
