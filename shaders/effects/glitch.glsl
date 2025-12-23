// VHS glitch effect
// iChannel0: source frame
// iParam0: glitch intensity (0..1)

// Simple hash function for pseudo-random values
float hash(float n) {
    return fract(sin(n) * 43758.5453);
}

float hash2(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float intensity = clamp(iParam0, 0.0, 1.0);
    
    // Time-based glitch triggers
    float glitchTime = floor(iTime * 8.0);
    float glitchHash = hash(glitchTime);
    
    // VHS tape tracking wobble (horizontal displacement varies by scanline)
    float wobbleFreq = 0.5 + hash(glitchTime) * 2.0;
    float wobble = sin(uv.y * 20.0 + iTime * wobbleFreq) * intensity * mix(0.0, 0.03, hash(glitchTime + 1.0));
    
    // Horizontal scanline bands that shift (tape tracking errors)
    float bandY = floor(uv.y * 15.0);
    float bandHash = hash(bandY + glitchTime);
    float bandShift = 0.0;
    if (bandHash > 1.0 - intensity * 0.5) {
        bandShift = (hash(bandY + glitchTime + 10.0) - 0.5) * intensity * mix(0.0, 0.08, bandHash);
    }
    
    // Chromatic aberration / color bleeding (VHS color separation)
    vec2 texel = 1.0 / iResolution.xy;
    float chromaShift = intensity * mix(0.0, 0.015, hash(glitchTime + 2.0));
    vec3 color;
    color.r = texture(iChannel0, uv + vec2(wobble + bandShift + chromaShift, 0.0)).r;
    color.g = texture(iChannel0, uv + vec2(wobble + bandShift, 0.0)).g;
    color.b = texture(iChannel0, uv + vec2(wobble + bandShift - chromaShift, 0.0)).b;
    
    // VHS noise/static (grainy texture)
    float noise = hash2(fragCoord + glitchTime);
    color += (noise - 0.5) * intensity * mix(0.0, 0.08, hash(glitchTime + 3.0));
    
    // Horizontal scanlines (VHS tape lines)
    float scanline = sin(uv.y * iResolution.y * 3.14159);
    float scanlineIntensity = mix(0.0, 0.15, intensity * hash(glitchTime + 4.0));
    color *= 1.0 - scanlineIntensity * abs(scanline);
    
    // Color saturation shifts (tape degradation)
    float saturationShift = 1.0 + (hash(glitchTime + 5.0) - 0.5) * intensity * 0.3;
    float gray = dot(color, vec3(0.299, 0.587, 0.114));
    color = mix(vec3(gray), color, saturationShift);
    
    // Occasional horizontal bands of corruption (tape damage)
    float corruptionBand = hash(floor(uv.y * 8.0) + glitchTime);
    if (corruptionBand > 1.0 - intensity * 0.2) {
        float corruptAmount = hash(corruptionBand + glitchTime);
        color = mix(color, vec3(hash2(uv + glitchTime)), corruptAmount * intensity * 0.4);
    }
    
    fragColor = vec4(color, 1.0);
}

