// Swirl distortion effect
// iChannel0: source frame
// iParam3: swirl intensity/angle (0..1 -> 0..6.28 radians = 0..360 degrees)
// iParam7: global intensity multiplier (0..1, applies to all effects)

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // Swirl is always centered on screen
    vec2 center = vec2(0.5, 0.5);
    
    // Get intensity from parameter, modulated by global intensity
    float intensity = clamp(iParam3, 0.0, 1.0) * clamp(iParam7, 0.0, 1.0);
    
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    
    // Calculate distance and angle from center
    vec2 offset = uv - center;
    float dist = length(offset);
    float angle = atan(offset.y, offset.x);
    
    // Swirl intensity (0 to 2*PI radians = 360 degrees)
    float swirlAngle = mix(0.0, 6.28318530718, intensity);
    
    // Fixed radius falloff - effect extends to screen edges
    float maxDist = 0.707; // Max distance to corner (diagonal)
    
    // Normalize distance (0 to 1 within effect radius)
    float normalizedDist = dist / maxDist;
    
    // Apply swirl distortion: rotate pixels around center
    // The further from center, the more rotation we apply
    // Use a smooth falloff function
    float swirlFactor = 1.0 - smoothstep(0.0, 1.0, normalizedDist);
    float rotation = swirlFactor * swirlAngle;
    
    // Rotate the offset vector
    float cosRot = cos(rotation);
    float sinRot = sin(rotation);
    vec2 rotatedOffset = vec2(
        offset.x * cosRot - offset.y * sinRot,
        offset.x * sinRot + offset.y * cosRot
    );
    
    // Calculate new UV coordinates
    vec2 distortedUV = center + rotatedOffset;
    
    // Clamp to valid UV range
    distortedUV = clamp(distortedUV, vec2(0.0), vec2(1.0));
    
    fragColor = texture(iChannel0, distortedUV);
}

