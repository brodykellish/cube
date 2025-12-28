// Bulge distortion effect
// iChannel0: source frame
// iParam0: bulge intensity (0..1 -> 0..1.0 distortion strength)
// iParam7: global intensity multiplier (0..1, applies to all effects)

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // Bulge is always centered on screen
    vec2 center = vec2(0.5, 0.5);
    
    // Get intensity from parameter, modulated by global intensity
    float intensity = clamp(iParam0, 0.0, 1.0) * clamp(iParam7, 0.0, 1.0);
    
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    
    // Calculate distance from center
    vec2 offset = uv - center;
    float dist = length(offset);
    
    // Bulge intensity (0 to 1.0)
    float bulgeStrength = intensity;
    
    // Fixed radius falloff - effect extends to screen edges
    float maxDist = 0.707; // Max distance to corner (diagonal)
    
    // Normalize distance (0 to 1 within effect radius)
    float normalizedDist = dist / maxDist;
    
    // Apply bulge distortion: push pixels outward
    // The further from center, the more we push outward
    // Use a smooth falloff function
    float bulgeFactor = 1.0 - smoothstep(0.0, 1.0, normalizedDist);
    float distortion = bulgeFactor * bulgeStrength;
    
    // Calculate new UV coordinates
    // Push outward from center proportionally to distance
    vec2 direction = normalize(offset);
    vec2 distortedUV = uv + direction * distortion * dist;
    
    // Clamp to valid UV range
    distortedUV = clamp(distortedUV, vec2(0.0), vec2(1.0));
    
    fragColor = texture(iChannel0, distortedUV);
}

