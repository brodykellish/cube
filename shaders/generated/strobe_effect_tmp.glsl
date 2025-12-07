// Strobe Effect - Flashing white light with frequency control
// iParam0 = strobe frequency (0.0 = slow, 1.0 = fast)
// iParam1 = strobe intensity (brightness)
// iParam2 = background darkness (0.0 = black, 1.0 = lighter)
// iParam3 = strobe shape (0.0 = hard cut, 1.0 = smooth pulse)

// === SDF ===
float sdSphere(vec3 p, float r) {
    return length(p) - r;
}

float sdBox(vec3 p, vec3 b) {
    vec3 q = abs(p) - b;
    return length(max(q, 0.0)) + min(max(q.x, max(q.y, q.z)), 0.0);
}

float sceneSDF(vec3 p) {
    // Central sphere for reference
    float sphere = sdSphere(p, 1.0);
    
    // Floor plane
    float floor = p.y + 2.0;
    
    return min(sphere, floor);
}

// === Raymarching ===
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

// === Strobe Function ===
float calculateStrobe(float time, float frequency, float shape) {
    // Map frequency: 0.0 = 0.5Hz, 1.0 = 20Hz
    float strobeFreq = mix(0.5, 20.0, frequency);
    
    // Calculate strobe phase
    float phase = time * strobeFreq;
    float cycle = fract(phase);
    
    if (shape < 0.5) {
        // Hard strobe - sharp on/off
        float cutoff = mix(0.1, 0.9, shape * 2.0);
        return cycle < cutoff ? 1.0 : 0.0;
    } else {
        // Smooth pulse
        float smoothness = (shape - 0.5) * 2.0;
        float pulse = sin(cycle * 6.28318530718) * 0.5 + 0.5;
        return mix(cycle < 0.5 ? 1.0 : 0.0, pulse, smoothness);
    }
}

// === Lighting ===
vec3 simpleLighting(vec3 p, vec3 rd, vec3 normal, vec3 color, float strobeIntensity) {
    vec3 lightPos = vec3(0.0, 5.0, 0.0);
    vec3 lightDir = normalize(lightPos - p);
    
    float diff = max(dot(normal, lightDir), 0.0);
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(-rd, reflectDir), 0.0), 32.0);
    
    // Strobe affects all lighting components
    vec3 ambient = color * 0.1 * strobeIntensity;
    vec3 diffuse = color * diff * 0.8 * strobeIntensity;
    vec3 specular = vec3(1.0) * spec * 0.6 * strobeIntensity;
    
    return ambient + diffuse + specular;
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
    
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    // Calculate strobe value
    float strobeValue = calculateStrobe(iTime, iParam0, iParam3);
    float strobeIntensity = mix(1.0, strobeValue, iParam1);
    
    // Background darkness control
    float bgLevel = mix(0.0, 0.3, iParam2);
    vec3 backgroundColor = vec3(bgLevel) * strobeIntensity;
    
    float t = raymarch(ro, rd, 50.0);
    
    vec3 color = backgroundColor;
    
    if (t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);
        
        // Different colors for different objects
        vec3 objectColor;
        if (p.y > -1.5) {
            // Sphere - bright color that responds to strobe
            objectColor = vec3(0.8, 0.4, 0.9);
        } else {
            // Floor - checkerboard pattern
            vec2 floorUV = p.xz;
            float checker = mod(floor(floorUV.x * 2.0) + floor(floorUV.z * 2.0), 2.0);
            objectColor = mix(vec3(0.3, 0.3, 0.3), vec3(0.7, 0.7, 0.7), checker);
        }
        
        color = simpleLighting(p, rd, normal, objectColor, strobeIntensity);
        
        // Add extra glow during strobe peaks
        if (strobeValue > 0.8) {
            color += vec3(0.3) * (strobeValue - 0.8) * 5.0 * iParam1;
        }
    }
    
    // Screen flash overlay for maximum strobe effect
    float screenFlash = strobeValue * iParam1;
    color = mix(color, vec3(1.0), screenFlash * 0.7);
    
    // Ensure minimum visibility even when strobe is off
    color = max(color, backgroundColor * 0.1);
    
    fragColor = vec4(color, 1.0);
}