// VHS Distortion Effect - Adds VHS-style distortion to shader output
// iChannel0: source frame
// iParam0: Distortion intensity (0..1) - overall effect strength
// iParam1: Chromatic aberration amount (0..1) - color separation
// iParam2: Scan line density (0..1) - scan line frequency
// iParam3: Noise/static intensity (0..1) - screen noise amount

// Simple hash function for pseudo-random values
float hash(float n) {
    return fract(sin(n) * 43758.5453);
}

float hash2(vec2 p) {
    return fract(sin(dot(p, vec2(12.9898, 78.233))) * 43758.5453);
}

// Smooth noise
float smoothNoise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float a = hash2(i);
    float b = hash2(i + vec2(1.0, 0.0));
    float c = hash2(i + vec2(0.0, 1.0));
    float d = hash2(i + vec2(1.0, 1.0));
    
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
}

// FBM for smoother distortion
float fbm(vec2 p) {
    float value = 0.0;
    float amplitude = 0.5;
    float frequency = 1.0;
    
    for (int i = 0; i < 3; i++) {
        value += amplitude * smoothNoise(p * frequency);
        frequency *= 2.0;
        amplitude *= 0.5;
    }
    
    return value;
}

// VHS tracking wobble - horizontal displacement that varies by scanline
float vhsWobble(vec2 uv, float time, float intensity) {
    float wobbleFreq = 15.0 + fbm(vec2(time * 0.1, 0.0)) * 5.0;
    float wobble = sin(uv.y * wobbleFreq + time * 2.0) * intensity;
    wobble += sin(uv.y * wobbleFreq * 2.3 + time * 3.0) * intensity * 0.5;
    return wobble * 0.02;
}

// VHS tearing - horizontal distortion bands
float vhsTear(vec2 uv, float time, float intensity) {
    float tearFreq = 0.3 + fbm(vec2(time * 0.1, 0.0)) * 0.2;
    float tearY = sin(uv.y * 20.0 + time * 2.0) * 0.5 + 0.5;
    tearY = pow(tearY, 3.0);
    
    float tearAmount = fbm(vec2(uv.y * tearFreq * 10.0, time * 0.5)) * 2.0 - 1.0;
    return tearAmount * tearY * intensity * 0.05;
}

// Scan lines effect
float scanLines(vec2 uv, float density) {
    float scanLineFreq = mix(200.0, 600.0, density);
    float scanLine = sin(uv.y * scanLineFreq * 3.14159) * 0.5 + 0.5;
    scanLine = pow(scanLine, 8.0);
    return 1.0 - scanLine * 0.2;
}

// Screen noise/static
vec3 screenNoise(vec2 uv, float time, float intensity) {
    vec2 noiseUV = uv * iResolution.xy + time * 10.0;
    float n = hash2(noiseUV);
    n = n * 2.0 - 1.0;
    
    vec3 noiseColor = vec3(
        hash2(noiseUV + vec2(0.0, 0.0)),
        hash2(noiseUV + vec2(100.0, 0.0)),
        hash2(noiseUV + vec2(200.0, 0.0))
    );
    noiseColor = noiseColor * 2.0 - 1.0;
    
    return noiseColor * intensity * 0.15;
}

// Color bleeding effect
vec3 colorBleed(vec3 color, vec2 uv, float time, float intensity) {
    float bleed = fbm(vec2(uv.y * 3.0, time * 0.2)) * intensity;
    color.r += bleed * 0.15;
    color.b -= bleed * 0.1;
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 texel = 1.0 / iResolution.xy;
    
    float intensity = clamp(iParam7, 0.0, 1.0);
    float distortionIntensity = clamp(iParam0, 0.0, 1.0) * intensity;
    float chromaIntensity = clamp(iParam1, 0.0, 1.0) * intensity;
    float scanLineDensity = clamp(iParam2, 0.0, 1.0) * intensity;
    float noiseIntensity = clamp(iParam3, 0.0, 1.0) * intensity;
    
    float time = iTime;
    
    // VHS tracking wobble
    float wobble = vhsWobble(uv, time, distortionIntensity);
    
    // VHS tearing distortion
    float tear = vhsTear(uv, time, distortionIntensity);
    
    // Combined horizontal distortion
    float horizontalDistortion = wobble + tear;
    
    // Chromatic aberration - RGB channel separation
    vec2 chromaOffset = vec2(chromaIntensity * 0.015, 0.0);
    vec3 color;
    color.r = texture(iChannel0, uv + vec2(horizontalDistortion + chromaOffset.x, 0.0)).r;
    color.g = texture(iChannel0, uv + vec2(horizontalDistortion, 0.0)).g;
    color.b = texture(iChannel0, uv + vec2(horizontalDistortion - chromaOffset.x, 0.0)).b;
    
    // Vertical distortion (less common but adds realism)
    float verticalDistortion = fbm(vec2(uv.x * 5.0, time * 0.3)) * distortionIntensity * 0.01;
    color = mix(color, texture(iChannel0, uv + vec2(0.0, verticalDistortion)).rgb, 0.3);
    
    // Apply scan lines
    float scanLine = scanLines(uv, scanLineDensity);
    color *= scanLine;
    
    // Add screen noise/static
    vec3 noise = screenNoise(uv, time, noiseIntensity);
    color += noise;
    
    // Color bleeding
    color = colorBleed(color, uv, time, distortionIntensity);
    
    // Horizontal tearing lines (bright lines that appear occasionally)
    float tearLine = step(0.98, fract(uv.y * mix(200.0, 600.0, scanLineDensity) + time * 0.5));
    tearLine *= fbm(vec2(uv.y * 10.0, time)) * distortionIntensity;
    color += vec3(tearLine * 0.4);
    
    // Vertical glitch lines
    float glitchTime = floor(time * 8.0);
    float glitchHash = hash(glitchTime);
    if (glitchHash > 1.0 - distortionIntensity * 0.3) {
        float glitchLine = step(0.995, hash2(vec2(uv.x * 100.0, glitchTime)));
        glitchLine *= distortionIntensity;
        color += vec3(glitchLine * 0.25);
    }
    
    // Tape head noise (random horizontal bands)
    float headNoise = step(0.97, fbm(vec2(0.0, uv.y * 2.0 + time * 0.3)));
    headNoise *= distortionIntensity;
    color += vec3(headNoise * 0.15);
    
    // Saturation shifts (tape degradation)
    float saturationShift = 1.0 + (fbm(vec2(uv.y * 5.0, time * 0.1)) - 0.5) * distortionIntensity * 0.2;
    float gray = dot(color, vec3(0.299, 0.587, 0.114));
    color = mix(vec3(gray), color, saturationShift);
    
    // Occasional horizontal bands of corruption (tape damage)
    float corruptionBand = hash(floor(uv.y * 8.0) + glitchTime);
    if (corruptionBand > 1.0 - distortionIntensity * 0.15) {
        float corruptAmount = hash(corruptionBand + glitchTime);
        color = mix(color, vec3(hash2(uv + glitchTime)), corruptAmount * distortionIntensity * 0.3);
    }
    
    // Brightness flicker (VHS tape flutter)
    float flicker = 1.0 + (fbm(vec2(time * 5.0, 0.0)) - 0.5) * distortionIntensity * 0.1;
    color *= flicker;
    
    // Clamp and output
    color = clamp(color, 0.0, 1.0);
    fragColor = vec4(color, 1.0);
}

