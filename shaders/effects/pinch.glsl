// Pinch distortion effect
// iChannel0: source frame
// iParam0: pinch intensity (0..1 -> 0..1.0 distortion strength)
// iParam1: center X position (0..1, default 0.5 = center)
// iParam2: center Y position (0..1, default 0.5 = center)
// iParam3: pinch radius falloff (0..1 -> 0.1..1.0, controls how far the effect extends)

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float intensity = clamp(iParam7, 0.0, 1.0);
    
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    
    // Get center position from parameters (default to center)
    vec2 center = vec2(
        mix(0.0, 1.0, clamp(iParam1, 0.0, 1.0)),
        mix(0.0, 1.0, clamp(iParam2, 0.0, 1.0))
    );
    
    // If center not set, default to center of screen
    if (iParam1 < 0.001 && iParam2 < 0.001) {
        center = vec2(0.5, 0.5);
    }
    
    // Calculate distance from center
    vec2 offset = uv - center;
    float dist = length(offset);
    
    // Pinch intensity (0 to 1.0)
    float pinchStrength = mix(0.0, 1.0, clamp(iParam0, 0.0, 1.0)) * intensity;
    
    // Radius falloff - controls how far the effect extends
    float radiusFalloff = mix(0.1, 1.0, clamp(iParam3, 0.0, 1.0));
    float maxDist = radiusFalloff * 0.707; // Max distance to corner (diagonal)
    
    // Normalize distance (0 to 1 within effect radius)
    float normalizedDist = dist / maxDist;
    
    // Apply pinch distortion: pull pixels inward
    // The further from center, the more we pull inward
    // Use a smooth falloff function
    float pinchFactor = 1.0 - smoothstep(0.0, 1.0, normalizedDist);
    float distortion = pinchFactor * pinchStrength;
    
    // Calculate new UV coordinates
    // Pull inward toward center proportionally to distance
    vec2 direction = normalize(offset);
    vec2 distortedUV = uv - direction * distortion * dist;
    
    // Clamp to valid UV range
    distortedUV = clamp(distortedUV, vec2(0.0), vec2(1.0));
    
    fragColor = texture(iChannel0, distortedUV);
}

