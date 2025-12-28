// VHS Grid FBM - VHS-style distortion with FBM color mapping
// iParam0: FBM color mapping intensity (0..1)
// iParam1: Grid density (0..1 -> 5..50 grid lines)
// iParam2: Distortion/tearing intensity (0..1)
// iParam3: Screen noise intensity (0..1)

// Simple noise function
float noise(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

// Smooth noise
float smoothNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float a = noise(i);
    float b = noise(i + vec2(1.0, 0.0));
    float c = noise(i + vec2(0.0, 1.0));
    float d = noise(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// FBM (Fractal Brownian Motion) - multiple octaves of noise
float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    
    for (int i = 0; i < 4; i++) {
        value += amplitude * smoothNoise(p * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
    }
    
    return value;
}

// VHS tearing effect - creates horizontal distortion bands
float vhsTear(vec2 uv, float time) {
    float tearFreq = 0.3 + fbm(vec2(time * 0.1, 0.0)) * 0.2;
    float tearY = sin(uv.y * 20.0 + time * 2.0) * 0.5 + 0.5;
    tearY = pow(tearY, 3.0);
    
    float tearAmount = fbm(vec2(uv.y * tearFreq * 10.0, time * 0.5)) * 2.0 - 1.0;
    return tearAmount * tearY;
}

// Scan lines effect
float scanLines(vec2 uv, float density) {
    float scanLineFreq = mix(5.0, 50.0, density);
    float scanLine = sin(uv.y * scanLineFreq * 3.14159) * 0.5 + 0.5;
    scanLine = pow(scanLine, 8.0);
    return 1.0 - scanLine * 0.15;
}

// Screen noise/chromatic aberration
vec3 screenNoise(vec2 uv, float time, float intensity) {
    vec2 noiseUV = uv * vec2(800.0, 600.0) + time * 10.0;
    float n = noise(noiseUV);
    n = n * 2.0 - 1.0;
    
    vec3 noiseColor = vec3(
        noise(noiseUV + vec2(0.0, 0.0)),
        noise(noiseUV + vec2(100.0, 0.0)),
        noise(noiseUV + vec2(200.0, 0.0))
    );
    noiseColor = noiseColor * 2.0 - 1.0;
    
    return noiseColor * intensity * 0.1;
}

// Grid pattern
float gridPattern(vec2 uv, float density) {
    float gridFreq = mix(5.0, 50.0, density);
    vec2 gridUV = uv * gridFreq;
    
    vec2 grid = abs(fract(gridUV - 0.5) - 0.5) / fwidth(gridUV);
    float gridLine = min(grid.x, grid.y);
    gridLine = 1.0 - smoothstep(0.0, 1.0, gridLine);
    
    return gridLine * 0.3;
}

// Color shift for VHS effect
vec3 vhsColorShift(vec3 color, vec2 uv, float time, float intensity) {
    float shift = fbm(vec2(uv.y * 5.0, time * 0.3)) * intensity * 0.02;
    
    vec3 shifted = vec3(
        texture(iChannel0, uv + vec2(shift, 0.0)).r,
        texture(iChannel0, uv).g,
        texture(iChannel0, uv - vec2(shift, 0.0)).b
    );
    
    return mix(color, shifted, intensity);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    float intensity = clamp(iParam7, 0.0, 1.0);
    float fbmIntensity = clamp(iParam0, 0.0, 1.0) * intensity;
    float gridDensity = clamp(iParam1, 0.0, 1.0) * intensity;
    float distortionIntensity = clamp(iParam2, 0.0, 1.0) * intensity;
    float noiseIntensity = clamp(iParam3, 0.0, 1.0) * intensity;
    
    float time = iTime;
    
    // Base color from input
    vec3 color = texture(iChannel0, uv).rgb;
    
    // Apply VHS tearing distortion
    float tear = vhsTear(uv, time) * distortionIntensity;
    vec2 distortedUV = uv;
    distortedUV.x += tear * 0.1;
    distortedUV.y += tear * 0.02;
    
    // Sample with distortion
    color = texture(iChannel0, distortedUV).rgb;
    
    // Apply FBM color mapping
    if (fbmIntensity > 0.0) {
        vec2 fbmUV = uv * 4.0 + time * 0.1;
        float fbmValue = fbm(fbmUV);
        
        // Use FBM to shift colors
        vec3 fbmColor = vec3(
            fbm(fbmUV + vec2(0.0, 0.0)),
            fbm(fbmUV + vec2(10.0, 0.0)),
            fbm(fbmUV + vec2(20.0, 0.0))
        );
        
        // Mix original color with FBM-mapped color
        color = mix(color, fbmColor, fbmIntensity * 0.5);
        
        // Add brightness variation based on FBM
        float brightnessVar = (fbmValue - 0.5) * fbmIntensity * 0.3;
        color += brightnessVar;
    }
    
    // Add grid pattern
    float grid = gridPattern(uv, gridDensity);
    color += grid;
    
    // Apply scan lines
    float scanLine = scanLines(uv, gridDensity);
    color *= scanLine;
    
    // Add screen noise
    vec3 screenNoiseValue = screenNoise(uv, time, noiseIntensity);
    color += screenNoiseValue;
    
    // Apply VHS color shift (chromatic aberration)
    color = vhsColorShift(color, uv, time, distortionIntensity);
    
    // Add horizontal tearing lines
    float tearLine = step(0.98, fract(uv.y * mix(5.0, 50.0, gridDensity) + time * 0.5));
    tearLine *= fbm(vec2(uv.y * 10.0, time)) * distortionIntensity;
    color += vec3(tearLine * 0.5);
    
    // Add vertical glitch lines
    float glitchLine = step(0.995, noise(vec2(uv.x * 100.0, time * 2.0)));
    glitchLine *= distortionIntensity;
    color += vec3(glitchLine * 0.3);
    
    // VHS-style color bleeding
    float bleed = fbm(vec2(uv.y * 3.0, time * 0.2)) * distortionIntensity * 0.1;
    color.r += bleed;
    color.b -= bleed * 0.5;
    
    // Add tape head noise (random horizontal bands)
    float headNoise = step(0.97, fbm(vec2(0.0, uv.y * 2.0 + time * 0.3)));
    headNoise *= distortionIntensity;
    color += vec3(headNoise * 0.2);
    
    // Clamp and output
    color = clamp(color, 0.0, 1.0);
    fragColor = vec4(color, 1.0);
}

