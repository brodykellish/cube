// Triangular prism at origin with color and size controls
// iParam0 = color hue (0.0-1.0 for full hue spectrum)
// iParam1 = prism size (0.1-2.0 scale factor)
// Camera controls: use arrow keys or WASD to navigate around the prism

// Distance function for a triangular prism
float sdTriangularPrism(vec3 p, vec2 h) {
    vec3 q = abs(p);
    return max(q.z - h.y, max(q.x * 0.866025 + p.y * 0.5, -p.y) - h.x * 0.5);
}

// HSV to RGB conversion
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

// Scene distance function
float map(vec3 p) {
    // Scale the prism based on iParam1 (0.1 to 2.0)
    float scale = mix(0.1, 2.0, iParam1);
    
    // Create triangular prism with height and width based on scale
    float prism = sdTriangularPrism(p / scale, vec2(1.0, 0.5)) * scale;
    
    return prism;
}

// Calculate surface normal
vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(
        map(p + e.xyy) - map(p - e.xyy),
        map(p + e.yxy) - map(p - e.yxy),
        map(p + e.yyx) - map(p - e.yyx)
    ));
}

// Raymarching function
float raymarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        if (d < 0.001 || t > 20.0) break;
        t += d;
    }
    return t;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normalized pixel coordinates
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    // Camera setup using provided uniforms
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    // Raymarch the scene
    float t = raymarch(ro, rd);
    
    // Initialize color
    vec3 col = vec3(0.05, 0.05, 0.1); // Dark blue background
    
    if (t < 20.0) {
        // Hit the prism
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);
        
        // Convert iParam0 to HSV color (full hue range)
        float hue = iParam0;
        vec3 baseColor = hsv2rgb(vec3(hue, 0.8, 0.9));
        
        // Simple lighting
        vec3 lightDir = normalize(vec3(1.0, 1.0, -1.0));
        float diff = max(dot(normal, lightDir), 0.0);
        float ambient = 0.3;
        
        // Calculate specular
        vec3 viewDir = -rd;
        vec3 reflectDir = reflect(-lightDir, normal);
        float spec = pow(max(dot(viewDir, reflectDir), 0.0), 32.0);
        
        // Combine lighting
        col = baseColor * (ambient + diff * 0.7) + vec3(1.0) * spec * 0.5;
        
        // Add some rim lighting
        float rim = 1.0 - max(dot(normal, viewDir), 0.0);
        col += baseColor * rim * rim * 0.3;
    }
    
    // Apply gamma correction
    col = pow(col, vec3(0.4545));
    
    fragColor = vec4(col, 1.0);
}