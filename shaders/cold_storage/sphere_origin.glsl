// Atomic Nucleus with Electrons - Interactive atomic model with MIDI controls

// === SDF ===
float sdSphere(vec3 p, float radius) {
    return length(p) - radius;
}

// === Raymarching ===
float sceneSDF(vec3 p) {
    // iParam1 controls nucleus size (0.2 to 2.0)
    float nucleusSize = 0.2 + iParam1 * 1.8;
    float particleRadius = nucleusSize * 0.3;
    
    float minDist = 1000.0;
    
    // Nucleus particles (4 protons + 3 neutrons in cluster formation)
    vec3 nucleusPositions[7];
    nucleusPositions[0] = vec3(0.0, 0.0, 0.0);  // Center
    nucleusPositions[1] = vec3(nucleusSize * 0.8, 0.0, 0.0);
    nucleusPositions[2] = vec3(-nucleusSize * 0.4, nucleusSize * 0.7, 0.0);
    nucleusPositions[3] = vec3(-nucleusSize * 0.4, -nucleusSize * 0.7, 0.0);
    nucleusPositions[4] = vec3(0.0, 0.0, nucleusSize * 0.8);
    nucleusPositions[5] = vec3(nucleusSize * 0.6, nucleusSize * 0.4, -nucleusSize * 0.6);
    nucleusPositions[6] = vec3(-nucleusSize * 0.6, 0.0, nucleusSize * 0.6);
    
    // Add nucleus particles to scene
    for (int i = 0; i < 7; i++) {
        float dist = sdSphere(p - nucleusPositions[i], particleRadius);
        minDist = min(minDist, dist);
    }
    
    // Electrons orbiting the nucleus
    // iParam0 controls electron speed (0.1 to 3.0)
    float electronSpeed = 0.1 + iParam0 * 2.9;
    float electronRadius = nucleusSize * 0.15;
    float orbitRadius = nucleusSize * 3.0;
    
    // 5 electrons in different orbital planes
    for (int i = 0; i < 5; i++) {
        float angle = iTime * electronSpeed + float(i) * 1.256; // Offset each electron
        float tilt = float(i) * 0.6; // Different orbital planes
        
        vec3 electronPos = vec3(
            orbitRadius * cos(angle) * cos(tilt),
            orbitRadius * sin(angle),
            orbitRadius * cos(angle) * sin(tilt)
        );
        
        float dist = sdSphere(p - electronPos, electronRadius);
        minDist = min(minDist, dist);
    }
    
    return minDist;
}

// Determine material based on position
int getMaterial(vec3 p) {
    float nucleusSize = 0.2 + iParam1 * 1.8;
    float particleRadius = nucleusSize * 0.3;
    
    // Check nucleus particles first (protons and neutrons)
    vec3 nucleusPositions[7];
    nucleusPositions[0] = vec3(0.0, 0.0, 0.0);
    nucleusPositions[1] = vec3(nucleusSize * 0.8, 0.0, 0.0);
    nucleusPositions[2] = vec3(-nucleusSize * 0.4, nucleusSize * 0.7, 0.0);
    nucleusPositions[3] = vec3(-nucleusSize * 0.4, -nucleusSize * 0.7, 0.0);
    nucleusPositions[4] = vec3(0.0, 0.0, nucleusSize * 0.8);
    nucleusPositions[5] = vec3(nucleusSize * 0.6, nucleusSize * 0.4, -nucleusSize * 0.6);
    nucleusPositions[6] = vec3(-nucleusSize * 0.6, 0.0, nucleusSize * 0.6);
    
    for (int i = 0; i < 7; i++) {
        if (length(p - nucleusPositions[i]) < particleRadius + 0.1) {
            // First 4 are protons (red), rest are neutrons (gray)
            return (i < 4) ? 1 : 2; // 1=proton, 2=neutron
        }
    }
    
    // Check electrons
    float electronSpeed = 0.1 + iParam0 * 2.9;
    float electronRadius = nucleusSize * 0.15;
    float orbitRadius = nucleusSize * 3.0;
    
    for (int i = 0; i < 5; i++) {
        float angle = iTime * electronSpeed + float(i) * 1.256;
        float tilt = float(i) * 0.6;
        
        vec3 electronPos = vec3(
            orbitRadius * cos(angle) * cos(tilt),
            orbitRadius * sin(angle),
            orbitRadius * cos(angle) * sin(tilt)
        );
        
        if (length(p - electronPos) < electronRadius + 0.1) {
            return 3; // 3=electron
        }
    }
    
    return 0; // Background
}

float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;
    for (int i = 0; i < 128; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);
        if (d < 0.001) return t;
        if (t > maxDist) break;
        t += d * 0.7;
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

// === Lighting ===
vec3 simpleLighting(vec3 p, vec3 rd, vec3 normal, vec3 color) {
    vec3 lightPos = vec3(5.0 * sin(iTime * 0.3), 4.0, 5.0 * cos(iTime * 0.3));
    vec3 lightDir = normalize(lightPos - p);

    float diff = max(dot(normal, lightDir), 0.0);
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(-rd, reflectDir), 0.0), 32.0);

    vec3 ambient = color * 0.3;
    vec3 diffuse = color * diff * 0.8;
    vec3 specular = vec3(1.0) * spec * 0.4;

    return ambient + diffuse + specular;
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use camera uniforms for proper 3D navigation
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    float t = raymarch(ro, rd, 30.0);

    vec3 color = vec3(0.0, 0.0, 0.0); // Black background

    if (t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);
        
        // Determine material and color
        int material = getMaterial(p);
        vec3 materialColor;
        
        if (material == 1) {
            // Protons - red with some brightness control from iParam2
            materialColor = vec3(0.8 + iParam2 * 0.2, 0.1, 0.1);
        } else if (material == 2) {
            // Neutrons - gray with some brightness control from iParam3
            materialColor = vec3(0.4 + iParam3 * 0.4, 0.4 + iParam3 * 0.4, 0.4 + iParam3 * 0.4);
        } else if (material == 3) {
            // Electrons - blue, glowing
            materialColor = vec3(0.1, 0.3, 0.9);
            // Add glow effect for electrons
            materialColor += vec3(0.0, 0.2, 0.6) * (1.0 + sin(iTime * 3.0) * 0.3);
        } else {
            materialColor = vec3(0.5, 0.5, 0.5); // Default
        }
        
        color = simpleLighting(p, rd, normal, materialColor);
        
        // Extra glow for electrons
        if (material == 3) {
            color *= 1.5;
        }
    }

    fragColor = vec4(color, 1.0);
}