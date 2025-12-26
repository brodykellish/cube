// Psychedelic FBM (Fractal Brownian Motion) effect
// iChannel0: source frame
// iParam0: brightness/intensity (0..1)
// iParam1: color deviation (0..1) - seeds color shifts from input framebuffer
// iParam2: distortion intensity (0..1)

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

// FBM for distortion (more octaves for smoother warping)
vec2 fbmDistort(vec2 p) {
    float x = fbm(p + vec2(iTime * 0.1, 0.0));
    float y = fbm(p + vec2(0.0, iTime * 0.1));
    return vec2(x, y);
}

vec3 rgb2hsb(vec3 c){
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = c.g < c.b ? vec4(c.bg, K.wz) : vec4(c.gb, K.xy);
    vec4 q = c.r < p.x ? vec4(p.xyw, c.r) : vec4(c.r, p.yzx);
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y)/(6.0*d + e)), d/(q.x + e), q.x);
}

vec3 hsb2rgb(vec3 c){
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    float intensity = clamp(iParam7, 0.0, 1.0);
    float brightness = clamp(iParam0, 0.0, 1.0) * intensity;
    float colorDev = clamp(iParam1, 0.0, 1.0) * intensity;
    float distortIntensity = clamp(iParam2, 0.0, 1.0) * intensity;
    
    // Apply FBM distortion to UV coordinates
    vec2 distortedUV = uv;
    if (distortIntensity > 0.0) {
        vec2 distortion = fbmDistort(uv * 3.0 + iTime * 0.2) - 0.5;
        distortedUV += distortion * distortIntensity * 0.1;
    }
    
    // Sample base color from input framebuffer
    vec3 baseColor = texture(iChannel0, distortedUV).rgb;
    
    // Get FBM value for color shifting (seed from base color)
    vec2 colorSeed = uv + baseColor.rg * 2.0;
    float fbmValue = fbm(colorSeed * 4.0 + iTime * 0.15);
    
    // Convert to HSB for color manipulation
    vec3 hsb = rgb2hsb(baseColor);
    
    // Apply color deviation based on FBM and input color
    float hueShift = (fbmValue - 0.5) * colorDev * 0.5;
    hsb.x = fract(hsb.x + hueShift + iTime * 0.1 * colorDev);
    
    // Enhance saturation based on FBM
    float satBoost = 1.0 + fbmValue * colorDev * 0.5;
    hsb.y = min(1.0, hsb.y * satBoost);
    
    // Apply brightness/intensity
    hsb.z *= mix(1.0, 2.0, brightness);
    
    // Convert back to RGB
    vec3 color = hsb2rgb(hsb);
    
    // Add FBM-based brightness variation for psychedelic pulsing
    float pulse = fbm(uv * 2.0 + iTime * 0.3) * 0.2;
    color *= (1.0 + pulse * brightness);
    
    fragColor = vec4(color, 1.0);
}

