// Quantum Plasma Field - Interactive LED Cube Visualization
// A swirling quantum field with plasma-like energy patterns
// iParam0: Energy intensity (0.0-1.0)
// iParam1: Field complexity (0.0-1.0) 
// iParam2: Color temperature (0.0-1.0)
// iParam3: Turbulence level (0.0-1.0)

float hash(float n) {
    return fract(sin(n) * 43758.5453);
}

float noise(vec3 p) {
    vec3 i = floor(p);
    vec3 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    
    float n = i.x + i.y * 57.0 + 113.0 * i.z;
    return mix(mix(mix(hash(n + 0.0), hash(n + 1.0), f.x),
                   mix(hash(n + 57.0), hash(n + 58.0), f.x), f.y),
               mix(mix(hash(n + 113.0), hash(n + 114.0), f.x),
                   mix(hash(n + 170.0), hash(n + 171.0), f.x), f.y), f.z);
}

float fbm(vec3 p) {
    float f = 0.0;
    float w = 0.5;
    for (int i = 0; i < 5; i++) {
        f += w * noise(p);
        p *= 2.0;
        w *= 0.5;
    }
    return f;
}

float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

float sdBox(vec3 p, vec3 b) {
    vec3 d = abs(p) - b;
    return min(max(d.x, max(d.y, d.z)), 0.0) + length(max(d, 0.0));
}

float quantumField(vec3 p) {
    float t = iTime * 0.5;
    float complexity = iParam1 * 3.0 + 0.5;
    float turbulence = iParam3 * 2.0 + 0.5;
    
    // Main quantum field
    vec3 q = p + vec3(sin(t * 0.3), cos(t * 0.2), sin(t * 0.4)) * turbulence;
    float field = fbm(q * complexity + t);
    
    // Add swirling motion
    float angle = atan(p.x, p.z) + t * 0.5;
    float radius = length(p.xz);
    vec3 spiral = vec3(cos(angle) * radius, p.y, sin(angle) * radius);
    field += noise(spiral * 2.0 + t) * 0.5;
    
    // Core sphere
    float core = sdSphere(p, 1.5);
    
    // Modulate sphere with quantum field
    float energy = iParam0 * 2.0 + 0.1;
    return core + field * energy - 0.3;
}

vec3 getNormal(vec3 p) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(
        quantumField(p + e.xyy) - quantumField(p - e.xyy),
        quantumField(p + e.yxy) - quantumField(p - e.yxy),
        quantumField(p + e.yyx) - quantumField(p - e.yyx)
    ));
}

float rayMarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + t * rd;
        float d = quantumField(p);
        if (d < 0.001 || t > 20.0) break;
        t += d * 0.7;
    }
    return t;
}

vec3 getColor(vec3 p, vec3 n, vec3 rd) {
    float temp = iParam2;
    
    // Base plasma colors
    vec3 cold = vec3(0.0, 0.3, 1.0);
    vec3 warm = vec3(1.0, 0.3, 0.0);
    vec3 hot = vec3(1.0, 1.0, 0.2);
    
    vec3 baseColor = mix(mix(cold, warm, temp), hot, temp * temp);
    
    // Energy-based modulation
    float energy = iParam0;
    float field = fbm(p * 3.0 + iTime * 0.5);
    
    // Add quantum fluctuations
    vec3 quantum = vec3(
        sin(field * 10.0 + iTime),
        sin(field * 12.0 + iTime * 1.1),
        sin(field * 14.0 + iTime * 1.2)
    ) * 0.3;
    
    vec3 color = baseColor + quantum * energy;
    
    // Simple lighting
    vec3 light = normalize(vec3(1.0, 1.0, 1.0));
    float ndotl = max(0.0, dot(n, light));
    float fresnel = pow(1.0 - max(0.0, dot(-rd, n)), 2.0);
    
    color *= (0.3 + 0.7 * ndotl);
    color += fresnel * baseColor * 0.5;
    
    return color;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // Camera setup using provided uniforms
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    // Ray marching
    float t = rayMarch(ro, rd);
    
    vec3 color = vec3(0.0);
    
    if (t < 20.0) {
        vec3 p = ro + t * rd;
        vec3 n = getNormal(p);
        color = getColor(p, n, rd);
        
        // Add glow effect
        float glow = 1.0 / (1.0 + t * t * 0.1);
        color += vec3(0.1, 0.2, 0.4) * glow * iParam0;
    }
    
    // Background gradient
    vec3 bg = mix(vec3(0.01, 0.02, 0.05), vec3(0.1, 0.0, 0.2), length(uv));
    color += bg * (1.0 - min(1.0, t / 20.0));
    
    // Tone mapping
    color = color / (1.0 + color);
    color = pow(color, vec3(1.0 / 2.2));
    
    fragColor = vec4(color, 1.0);
}