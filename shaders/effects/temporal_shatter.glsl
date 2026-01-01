// Temporal Shatter: Split frame into tiles, each sampling a different moment in time
// iChannel0: current frame
// iChannel1: previous frame (feedback buffer)
// iParam0: tile size (0..1 -> 0.02..0.3)
// iParam1: time offset range (0..1 -> 0.0..1.0, how far back tiles can look)
// iParam2: freeze chance (0..1 -> 0.0..1.0, probability tiles freeze on previous frame)
// iParam3: time speed (0..1 -> 0.5..3.0)
// iParam4: audio reactivity (0..1 -> 0.0..1.0)
// iParam5: pattern type (0..1 -> mosaic/radial/wedge)
// iParam6: chaos reset (0..1, triggers random reset when > 0.5)

// Hash function for pseudo-random values
vec3 hash3(vec3 p) {
    p = vec3(dot(p, vec3(127.1, 311.7, 74.7)),
             dot(p, vec3(269.5, 183.3, 246.1)),
             dot(p, vec3(113.5, 271.9, 124.6)));
    return fract(sin(p) * 43758.5453123);
}

// Get tile ID and local coordinates
vec4 getTile(vec2 uv, float tileSize, float patternType) {
    float tileScale = mix(0.02, 0.3, tileSize);
    
    if (patternType < 0.33) {
        // Mosaic pattern (grid)
        vec2 tileCoord = floor(uv / tileScale);
        vec2 localUV = fract(uv / tileScale);
        return vec4(tileCoord, localUV);
    } else if (patternType < 0.66) {
        // Radial slices
        vec2 centered = uv - vec2(0.5, 0.5);
        float angle = atan(centered.y, centered.x);
        float radius = length(centered);
        float sliceCount = 16.0;
        float sliceID = floor((angle + 3.14159) / (6.28318 / sliceCount));
        float radialID = floor(radius / tileScale);
        vec2 tileCoord = vec2(sliceID, radialID);
        vec2 localUV = vec2(fract((angle + 3.14159) / (6.28318 / sliceCount)), fract(radius / tileScale));
        return vec4(tileCoord, localUV);
    } else {
        // Wedge pattern (diagonal slices)
        vec2 centered = uv - vec2(0.5, 0.5);
        float wedgeAngle = atan(centered.y, centered.x) + 3.14159;
        float wedgeCount = 12.0;
        float wedgeID = floor(wedgeAngle / (6.28318 / wedgeCount));
        float dist = length(centered);
        float distID = floor(dist / tileScale);
        vec2 tileCoord = vec2(wedgeID, distID);
        vec2 localUV = vec2(fract(wedgeAngle / (6.28318 / wedgeCount)), fract(dist / tileScale));
        return vec4(tileCoord, localUV);
    }
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    float intensity = clamp(iParam7, 0.0, 1.0);
    if (intensity < 0.001) {
        vec2 uv = fragCoord / iResolution.xy;
        fragColor = texture(iChannel0, uv);
        return;
    }
    
    vec2 uv = fragCoord / iResolution.xy;
    vec2 aspect = vec2(iResolution.x / iResolution.y, 1.0);
    vec2 aspectUV = uv * aspect;
    
    float tileSize = clamp(iParam0, 0.0, 1.0);
    float timeOffsetRange = clamp(iParam1, 0.0, 1.0);
    float freezeChance = clamp(iParam2, 0.0, 1.0);
    float timeSpeed = mix(0.5, 3.0, clamp(iParam3, 0.0, 1.0));
    float audioReact = clamp(iParam4, 0.0, 1.0);
    float patternType = clamp(iParam5, 0.0, 1.0);
    float chaosReset = clamp(iParam6, 0.0, 1.0);
    
    // Audio enhancement
    float audioBoost = mix(1.0, 1.0 + iAudioLevel * 2.0, audioReact);
    float beatBoost = mix(1.0, 1.0 + iBeatPulse * 4.0, audioReact);
    float time = iTime * timeSpeed * audioBoost;
    
    // Get tile information
    vec4 tileInfo = getTile(aspectUV, tileSize, patternType);
    vec2 tileID = tileInfo.xy;
    vec2 localUV = tileInfo.zw;
    
    // Generate random seed for this tile (use time for chaos reset)
    float resetSeed = floor(time * 0.5) * step(0.5, chaosReset);
    vec3 seed = vec3(tileID, resetSeed);
    vec3 rand = hash3(seed);
    
    // Determine time offset for this tile
    // Some tiles look forward (negative offset), some backward (positive offset)
    float timeOffset = (rand.x - 0.5) * 2.0 * timeOffsetRange;
    
    // Freeze some tiles completely (they stay on previous frame)
    float isFrozen = step(freezeChance, rand.y);
    
    // Time-based variation (some tiles drift over time)
    float timeDrift = sin(time * 0.3 + rand.z * 6.28318) * 0.1 * (1.0 - isFrozen);
    timeOffset += timeDrift;
    
    // Beat-triggered chaos: on beat, randomize all offsets
    float beatChaos = iBeatPulse * audioReact;
    if (beatChaos > 0.3) {
        vec3 beatSeed = vec3(tileID, time * 2.0);
        vec3 beatRand = hash3(beatSeed);
        timeOffset = (beatRand.x - 0.5) * 2.0 * timeOffsetRange * 1.5;
    }
    
    // Calculate mix factor between current and previous frame
    // timeOffset > 0 means look backward (use previous frame)
    // timeOffset < 0 means look forward (use current frame, or extrapolate)
    float mixFactor = clamp(timeOffset, 0.0, 1.0);
    
    // Frozen tiles always use previous frame
    mixFactor = mix(mixFactor, 1.0, isFrozen);
    
    // Calculate final UV (within tile)
    float tileScale = mix(0.02, 0.3, tileSize);
    vec2 finalUV;
    
    if (patternType < 0.33) {
        // Mosaic: simple grid
        finalUV = (tileID + localUV) * tileScale;
    } else if (patternType < 0.66) {
        // Radial: reconstruct from polar
        float sliceCount = 16.0;
        float angle = (tileID.x / sliceCount) * 6.28318 - 3.14159;
        float radius = (tileID.y + localUV.y) * tileScale;
        vec2 centered = vec2(cos(angle), sin(angle)) * radius;
        finalUV = centered + vec2(0.5, 0.5) * aspect;
    } else {
        // Wedge: reconstruct from polar
        float wedgeCount = 12.0;
        float wedgeAngle = (tileID.x / wedgeCount) * 6.28318;
        float dist = (tileID.y + localUV.y) * tileScale;
        vec2 centered = vec2(cos(wedgeAngle), sin(wedgeAngle)) * dist;
        finalUV = centered + vec2(0.5, 0.5) * aspect;
    }
    
    finalUV /= aspect;
    finalUV = clamp(finalUV, 0.0, 1.0);
    
    // Sample from current and previous frames
    vec3 currentColor = texture(iChannel0, finalUV).rgb;
    vec3 previousColor = texture(iChannel1, finalUV).rgb;
    
    // Check if previous frame is valid (not black/uninitialized)
    // Use a higher threshold to be more conservative
    float prevLuminance = dot(previousColor, vec3(0.299, 0.587, 0.114));
    float prevValid = step(0.05, prevLuminance);
    
    // Only use previous frame if it's valid, otherwise always use current
    // This prevents any black flashing
    vec3 color;
    if (prevValid > 0.5 && mixFactor > 0.01) {
        // Previous frame is valid and we want to use it
        color = mix(currentColor, previousColor, mixFactor);
    } else {
        // Previous frame is invalid or we don't want to use it - use current
        color = currentColor;
    }
    
    // Enhance saturation for intensity while preserving true colors
    float luminance = dot(color, vec3(0.299, 0.587, 0.114));
    vec3 saturated = mix(vec3(luminance), color, 1.5);
    color = mix(color, saturated, 0.25);
    
    // Add subtle color shift for frozen tiles (preserve intensity)
    if (isFrozen > 0.5) {
        color = mix(color, color.gbr, 0.08);
    }
    
    // Remove edge darkening completely - no brightness reduction
    // Just use the color as-is
    
    // Intensity fade
    color *= intensity;
    
    fragColor = vec4(color, 1.0);
}

