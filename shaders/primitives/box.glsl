// Box Primitive - multiple boxes in a line with count and spacing control with enhanced lighting

// === SDF ===
float sdBox(vec3 p, vec3 size) {
    vec3 q = abs(p) - size;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

// === Raymarching ===
float sceneSDF(vec3 p) {
    // Number of boxes controlled by iParam3 (1 to 100)
    int numBoxes = int(1.0 + iParam3 * 99.0);
    
    // Box size
    float boxScale = 0.5;
    vec3 size = vec3(0.8, 1.0, 0.8) * boxScale;
    
    // Spacing between boxes controlled by iParam2 (0 to 12 units)
    float spacing = iParam2 * 12.0;
    
    float minDist = 1000.0;
    
    // Generate boxes in a line along X axis
    for (int i = 0; i < 100; i++) {
        if (i >= numBoxes) break;
        
        // Calculate position for this box
        float offset = float(i) * spacing;
        // Center the line of boxes
        float centerOffset = float(numBoxes - 1) * spacing * 0.5;
        vec3 boxPos = vec3(offset - centerOffset, 0.0, 0.0);
        
        // Transform point to box local space
        vec3 localP = p - boxPos;
        
        // Calculate distance to this box
        float boxDist = sdBox(localP, size);
        
        // Keep minimum distance
        minDist = min(minDist, boxDist);
    }
    
    return minDist;
}

float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;
    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);
        if (d < 0.001) return t;
        if (t > maxDist) break;
        t += d * 0.9;
    }
    return -1.0;
}

vec3 calcNormal(vec3 p) {
    float eps = 0.001;
    vec2 h = vec2(eps, 0.0);
    return normalize(vec3(
        sceneSDF(p + h.xyy) - sceneSDF(p - h.xyy),
        sceneSDF(p + h.yxy) - sceneSDF(p - h.yxy),
        sceneSDF(p + h.yyx) - sceneSDF(p - h.yyx)
    ));
}

// === Enhanced Lighting ===
vec3 enhancedLighting(vec3 p, vec3 rd, vec3 normal, vec3 color) {
    // Main rotating light
    vec3 lightPos1 = vec3(4.0 * sin(iTime * 0.5), 3.0, 4.0 * cos(iTime * 0.5));
    vec3 lightDir1 = normalize(lightPos1 - p);
    
    // Additional fixed lights for better illumination
    vec3 lightPos2 = vec3(-5.0, 4.0, 2.0);
    vec3 lightDir2 = normalize(lightPos2 - p);
    
    vec3 lightPos3 = vec3(2.0, -3.0, -4.0);
    vec3 lightDir3 = normalize(lightPos3 - p);
    
    // Key light (main rotating)
    float diff1 = max(dot(normal, lightDir1), 0.0);
    vec3 reflectDir1 = reflect(-lightDir1, normal);
    float spec1 = pow(max(dot(-rd, reflectDir1), 0.0), 32.0);
    
    // Fill light (left side)
    float diff2 = max(dot(normal, lightDir2), 0.0);
    vec3 reflectDir2 = reflect(-lightDir2, normal);
    float spec2 = pow(max(dot(-rd, reflectDir2), 0.0), 16.0);
    
    // Rim light (bottom)
    float diff3 = max(dot(normal, lightDir3), 0.0);
    
    // Enhanced ambient lighting
    vec3 ambient = color * 0.4;  // Increased from 0.2
    
    // Multiple light contributions
    vec3 diffuse = color * (diff1 * 0.8 + diff2 * 0.5 + diff3 * 0.3);
    vec3 specular = vec3(1.0) * (spec1 * 0.7 + spec2 * 0.3);
    
    return ambient + diffuse + specular;
}

// === UV Mapping ===
vec2 getBoxUV(vec3 p, vec3 normal) {
    vec2 uv;
    if (abs(normal.y) > 0.9) {
        uv = p.xz;
    } else if (abs(normal.x) > 0.9) {
        uv = p.zy;
    } else {
        uv = p.xy;
    }
    return uv;
}

float checkerboard(vec2 uv, float scale) {
    vec2 grid = floor(uv * scale);
    return mod(grid.x + grid.y, 2.0);
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    float t = raymarch(ro, rd, 50.0);

    // Keep background black
    vec3 color = vec3(0.0, 0.0, 0.0);

    if (t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        // Brighter base color controlled by RGB parameters 0-1
        vec3 baseColor = vec3(iParam0, iParam1, 0.5) * 1.5;  // Increased brightness

        // Apply enhanced lighting
        color = enhancedLighting(p, rd, normal, baseColor);

        // Reduced fog effect to keep boxes brighter
        float fog = 1.0 - exp(-t * 0.05);  // Reduced from 0.1
        color = mix(color, vec3(0.0, 0.0, 0.0), fog * 0.3);  // Much less fog influence
    }

    fragColor = vec4(color, 1.0);
}