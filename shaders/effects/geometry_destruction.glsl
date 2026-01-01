// Geometry Destruction: Convert image into geometric primitives and aggressively rearrange them
// iChannel0: source frame
// iParam0: tile size (0..1 -> 0.02..0.3)
// iParam1: extrusion depth (0..1 -> 0.0..1.0)
// iParam2: rotation chaos (0..1 -> 0.0..2.0)
// iParam3: explosion force (0..1 -> 0.0..2.0)
// iParam4: time speed (0..1 -> 0.5..3.0)
// iParam5: audio reactivity (0..1 -> 0.0..1.0)
// iParam6: tile pattern (0..1 -> triangular/block hybrid)

// Hash function for pseudo-random values
vec3 hash3(vec3 p) {
    p = vec3(dot(p, vec3(127.1, 311.7, 74.7)),
             dot(p, vec3(269.5, 183.3, 246.1)),
             dot(p, vec3(113.5, 271.9, 124.6)));
    return fract(sin(p) * 43758.5453123);
}

// 3D rotation matrix
mat3 rotateX(float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat3(1.0, 0.0, 0.0,
                0.0, c, -s,
                0.0, s, c);
}

mat3 rotateY(float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat3(c, 0.0, s,
                0.0, 1.0, 0.0,
                -s, 0.0, c);
}

mat3 rotateZ(float angle) {
    float c = cos(angle);
    float s = sin(angle);
    return mat3(c, -s, 0.0,
                s, c, 0.0,
                0.0, 0.0, 1.0);
}

// Get tile ID and local coordinates
vec4 getTile(vec2 uv, float tileSize, float patternMix) {
    float tileScale = mix(0.02, 0.3, tileSize);
    vec2 tileCoord = floor(uv / tileScale);
    vec2 localUV = fract(uv / tileScale);
    
    // Pattern selection: triangular vs block
    vec2 tileID = tileCoord;
    if (patternMix > 0.5) {
        // Triangular tiling (alternating diagonal split)
        float triID = mod(tileCoord.x + tileCoord.y, 2.0);
        if (triID < 1.0) {
            // Lower triangle
            if (localUV.x + localUV.y > 1.0) {
                tileID += vec2(1.0, 0.0);
                localUV = vec2(1.0 - localUV.x, 1.0 - localUV.y);
            }
        } else {
            // Upper triangle
            if (localUV.x + localUV.y < 1.0) {
                tileID += vec2(0.0, 1.0);
                localUV = vec2(1.0 - localUV.x, 1.0 - localUV.y);
            }
        }
    }
    
    return vec4(tileID, localUV);
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
    uv *= aspect;
    
    float tileSizeParam = clamp(iParam0, 0.0, 1.0);
    float tileScale = mix(0.02, 0.3, tileSizeParam);
    float extrusion = mix(0.0, 1.0, clamp(iParam1, 0.0, 1.0));
    float rotationChaos = mix(0.0, 2.0, clamp(iParam2, 0.0, 1.0));
    float explosionForce = mix(0.0, 2.0, clamp(iParam3, 0.0, 1.0));
    float timeSpeed = mix(0.5, 3.0, clamp(iParam4, 0.0, 1.0));
    float audioReact = clamp(iParam5, 0.0, 1.0);
    float patternMix = clamp(iParam6, 0.0, 1.0);
    
    // Audio enhancement
    float audioBoost = mix(1.0, 1.0 + iAudioLevel * 3.0, audioReact);
    float beatBoost = mix(1.0, 1.0 + iBeatPulse * 5.0, audioReact);
    float time = iTime * timeSpeed * audioBoost;
    
    // Get tile information
    vec4 tileInfo = getTile(uv, tileSizeParam, patternMix);
    vec2 tileID = tileInfo.xy;
    vec2 localUV = tileInfo.zw;
    
    // Generate multiple random seeds for different behaviors
    vec3 seed1 = vec3(tileID, 0.0);
    vec3 seed2 = vec3(tileID * 1.7, time * 0.15);
    vec3 seed3 = vec3(tileID * 2.3, time * 0.23);
    vec3 rand1 = hash3(seed1);
    vec3 rand2 = hash3(seed2);
    vec3 rand3 = hash3(seed3);
    
    // Base rotation (constant per tile)
    float baseRot = (rand1.x - 0.5) * 6.28318 * rotationChaos;
    // Time-based rotation (spinning tiles)
    float timeRot = time * (rand1.y - 0.5) * 2.0 * rotationChaos;
    float rotAngle = baseRot + timeRot;
    mat3 rotMat = rotateZ(rotAngle);
    
    // Radial explosion: tiles fly away from center
    vec2 center = vec2(0.5, 0.5) * aspect;
    vec2 tileCenter = (tileID + 0.5) * tileScale;
    vec2 toCenter = normalize(tileCenter - center);
    float distFromCenter = length(tileCenter - center);
    
    // Explosion velocity (radial + random)
    vec2 explosionDir = toCenter * explosionForce * (1.0 + distFromCenter * 2.0);
    vec2 randomDir = (rand2.xy - 0.5) * 2.0 * explosionForce * 1.5;
    vec2 velocity = explosionDir + randomDir;
    
    // Time-based displacement (tiles move over time) - scale by tile size
    vec2 timeDisplacement = velocity * time * beatBoost * tileScale * 2.0;
    
    // Random scatter (completely random position offset) - scale by tile size
    vec2 scatterOffset = (rand3.xy - 0.5) * 2.0 * explosionForce * tileScale * 2.5;
    
    // Total displacement combines all effects
    vec2 totalOffset = timeDisplacement + scatterOffset;
    
    // Center local UV for rotation
    vec2 centeredUV = localUV - 0.5;
    vec3 rotatedUV = rotMat * vec3(centeredUV, 0.0);
    vec2 finalLocalUV = rotatedUV.xy + 0.5;
    
    // Sample original texture - but from a completely different location!
    // Use the tile's random seed to pick a random source location
    vec2 sourceOffset = (rand1.yz - 0.5) * 2.0 * explosionForce * tileScale * 3.0;
    vec2 sourceUV = (tileID + finalLocalUV) * tileScale + sourceOffset;
    sourceUV /= aspect;
    sourceUV = fract(sourceUV);
    
    // Also sample at tile center for extrusion calculation
    vec2 tileCenterUV = (tileID + 0.5) * tileScale / aspect;
    vec3 tileColor = texture(iChannel0, tileCenterUV).rgb;
    float luminance = dot(tileColor, vec3(0.299, 0.587, 0.114));
    
    // Extrusion: push tiles forward/back based on luminance
    float extrudeAmount = (luminance - 0.5) * 2.0 * extrusion * beatBoost;
    
    // Apply perspective-like distortion based on extrusion
    vec2 perspective = vec2(1.0 + extrudeAmount * 0.5);
    vec2 distortedUV = (finalLocalUV - 0.5) * perspective + 0.5;
    
    // Calculate final UV - tiles can end up anywhere!
    vec2 finalUV = (tileID + distortedUV) * tileScale + totalOffset;
    finalUV /= aspect;
    
    // Wrap around instead of clamping (tiles can wrap to other side)
    finalUV = fract(finalUV);
    
    // Sample from the scrambled source location
    vec3 color = texture(iChannel0, sourceUV).rgb;
    
    // Mix with original location for extra chaos
    vec3 color2 = texture(iChannel0, finalUV).rgb;
    color = mix(color, color2, 0.5);
    
    // Subtle edge darkening for 3D effect (reduced to preserve color)
    vec2 edgeDist = min(finalLocalUV, 1.0 - finalLocalUV);
    float edgeFactor = min(edgeDist.x, edgeDist.y);
    float edgeDarken = 1.0 - smoothstep(0.0, 0.12, edgeFactor) * 0.15;
    color *= edgeDarken;
    
    // Subtle color shift based on tile rotation (preserves color intensity)
    float hueShift = rotAngle * 0.1 + distFromCenter * 0.5;
    // Very subtle channel mixing to add interest without destroying color
    color = mix(color, color.gbr, abs(sin(hueShift)) * 0.08);
    color = mix(color, color.bgr, abs(cos(hueShift * 0.7)) * 0.05);
    
    // Add brightness variation based on displacement (tiles in motion are brighter)
    float motionBrightness = 1.0 + length(totalOffset) * 0.3;
    color *= motionBrightness;
    
    // Reduced inversion chance and make it less aggressive
    float invertChance = rand1.x;
    if (invertChance > 0.85) {
        // Invert but preserve luminance to keep it colorful
        float lum = dot(color, vec3(0.299, 0.587, 0.114));
        color = mix(1.0 - color, color, 0.3);
        // Restore some original color
        vec3 originalColor = mix(color, color2, 0.5);
        color = mix(color, originalColor, 0.4);
    }
    
    // Intensity fade
    color *= intensity;
    
    fragColor = vec4(color, 1.0);
}

