// Pinch distortion effect
// iChannel0: source frame
// iParam1: pinch intensity (0..1 -> 0..1.0 distortion strength)
// iParam7: global intensity multiplier (0..1, applies to all effects)

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // Pinch is always centered on screen
    vec2 center = vec2(0.5, 0.5);
    
    // Get intensity from parameter, modulated by global intensity
    float intensity = clamp(iParam1, 0.0, 1.0) * clamp(iParam7, 0.0, 1.0);
    
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    
    // Calculate distance from center
    vec2 offset = uv - center;
    float dist = length(offset);
    
    // Pinch intensity (0 to 1.0)
    float pinchStrength = intensity;
    
    // Fixed radius falloff - effect extends to screen edges
    float maxDist = 0.707; // Max distance to corner (diagonal)
    
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

