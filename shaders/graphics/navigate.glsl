// Navigate - Interactive 3D Scene with Keyboard Controls with Enhanced Lighting
// Use Arrow Keys/WASD to move forward/back/left/right
// Use PageUp/PageDown or E/C to move up/down

// Distance to a sphere
float sdSphere(vec3 p, float radius) {
    return length(p) - radius;
}

// Distance to the scene
float map(vec3 p) {
    float d = 1e10;

    // Create a grid of spheres
    for (float x = -3.0; x <= 3.0; x += 2.0) {
        for (float y = -3.0; y <= 3.0; y += 2.0) {
            for (float z = -3.0; z <= 3.0; z += 2.0) {
                vec3 spherePos = vec3(x, y, z);
                float sphere = sdSphere(p - spherePos, 0.5);
                d = min(d, sphere);
            }
        }
    }

    return d;
}

// Calculate normal using tetrahedron technique
vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.001, 0.0);
    return normalize(vec3(
        map(p + e.xyy) - map(p - e.xyy),
        map(p + e.yxy) - map(p - e.yxy),
        map(p + e.yyx) - map(p - e.yyx)
    ));
}

// Raymarching
float raymareh(vec3 ro, vec3 rd) {
    float t = 0.0;
    for (int i = 0; i < 100; i++) {
        vec3 p = ro + rd * t;
        float d = map(p);
        if (d < 0.001 || t > 50.0) break;
        t += d;
    }
    return t;
}

// Enhanced lighting function with multiple colored point lights - BRIGHTENED
vec3 calculateLighting(vec3 p, vec3 normal, vec3 viewDir, vec3 baseColor) {
    vec3 finalColor = vec3(0.0);
    
    // Ambient light - increased from 0.15 to 0.4 for brighter base illumination
    vec3 ambient = baseColor * 0.4;
    finalColor += ambient;
    
    // Multiple animated point lights with different colors - increased brightness
    
    // Light 1: Warm orange light orbiting horizontally - brightened
    vec3 light1Pos = vec3(6.0 * cos(iTime * 0.7), 3.0, 6.0 * sin(iTime * 0.7));
    vec3 light1Color = vec3(1.5, 0.6, 0.15);  // Brighter warm orange
    vec3 light1Dir = normalize(light1Pos - p);
    float light1Dist = length(light1Pos - p);
    float light1Attenuation = 1.0 / (1.0 + 0.08 * light1Dist + 0.015 * light1Dist * light1Dist); // Reduced attenuation
    
    float diff1 = max(dot(normal, light1Dir), 0.0);
    vec3 halfDir1 = normalize(light1Dir + viewDir);
    float spec1 = pow(max(dot(normal, halfDir1), 0.0), 32.0);
    
    finalColor += light1Color * light1Attenuation * (diff1 * baseColor + spec1 * 0.8);
    
    // Light 2: Cool blue light moving vertically - brightened
    vec3 light2Pos = vec3(-4.0, 4.0 * sin(iTime * 0.9), 4.0);
    vec3 light2Color = vec3(0.15, 0.8, 1.5);  // Brighter cool blue
    vec3 light2Dir = normalize(light2Pos - p);
    float light2Dist = length(light2Pos - p);
    float light2Attenuation = 1.0 / (1.0 + 0.08 * light2Dist + 0.015 * light2Dist * light2Dist); // Reduced attenuation
    
    float diff2 = max(dot(normal, light2Dir), 0.0);
    vec3 halfDir2 = normalize(light2Dir + viewDir);
    float spec2 = pow(max(dot(normal, halfDir2), 0.0), 32.0);
    
    finalColor += light2Color * light2Attenuation * (diff2 * baseColor + spec2 * 0.8);
    
    // Light 3: Green light moving in a figure-8 pattern - brightened
    vec3 light3Pos = vec3(3.0 * sin(iTime * 1.2), 2.0 * cos(iTime * 2.4), 3.0 * cos(iTime * 1.2));
    vec3 light3Color = vec3(0.3, 1.5, 0.45);  // Brighter green
    vec3 light3Dir = normalize(light3Pos - p);
    float light3Dist = length(light3Pos - p);
    float light3Attenuation = 1.0 / (1.0 + 0.08 * light3Dist + 0.015 * light3Dist * light3Dist); // Reduced attenuation
    
    float diff3 = max(dot(normal, light3Dir), 0.0);
    vec3 halfDir3 = normalize(light3Dir + viewDir);
    float spec3 = pow(max(dot(normal, halfDir3), 0.0), 32.0);
    
    finalColor += light3Color * light3Attenuation * (diff3 * baseColor + spec3 * 0.8);
    
    // Light 4: Purple light oscillating back and forth - brightened
    vec3 light4Pos = vec3(5.0 * sin(iTime * 0.6), -2.0, 2.0 * cos(iTime * 1.8));
    vec3 light4Color = vec3(1.2, 0.3, 1.5);  // Brighter purple/magenta
    vec3 light4Dir = normalize(light4Pos - p);
    float light4Dist = length(light4Pos - p);
    float light4Attenuation = 1.0 / (1.0 + 0.08 * light4Dist + 0.015 * light4Dist * light4Dist); // Reduced attenuation
    
    float diff4 = max(dot(normal, light4Dir), 0.0);
    vec3 halfDir4 = normalize(light4Dir + viewDir);
    float spec4 = pow(max(dot(normal, halfDir4), 0.0), 32.0);
    
    finalColor += light4Color * light4Attenuation * (diff4 * baseColor + spec4 * 0.8);
    
    // Light 5: Yellow accent light with slow movement - brightened
    vec3 light5Pos = vec3(2.0 * cos(iTime * 0.3), 5.0, 2.0 * sin(iTime * 0.5));
    vec3 light5Color = vec3(1.5, 1.35, 0.3);  // Brighter yellow
    vec3 light5Dir = normalize(light5Pos - p);
    float light5Dist = length(light5Pos - p);
    float light5Attenuation = 1.0 / (1.0 + 0.08 * light5Dist + 0.015 * light5Dist * light5Dist); // Reduced attenuation
    
    float diff5 = max(dot(normal, light5Dir), 0.0);
    vec3 halfDir5 = normalize(light5Dir + viewDir);
    float spec5 = pow(max(dot(normal, halfDir5), 0.0), 32.0);
    
    finalColor += light5Color * light5Attenuation * (diff5 * baseColor + spec5 * 0.8);
    
    return finalColor;
}

void mainImage(out vec4 fragColor, vec2 fragCoord) {
    // Normalized pixel coordinates
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Camera position and orientation are precomputed in Python
    // This ensures smooth, discontinuity-free rotation at all angles!
    vec3 cameraPos = iCameraPos;
    vec3 right = iCameraRight;
    vec3 up = iCameraUp;
    vec3 forward = iCameraForward;

    // Ray direction - directly use precomputed camera basis
    vec3 rd = normalize(uv.x * right + uv.y * up + 1.5 * forward);

    // Raymarch
    float t = raymareh(cameraPos, rd);

    // Color the scene
    vec3 col = vec3(0.0);

    if (t < 50.0) {
        vec3 p = cameraPos + rd * t;
        vec3 normal = calcNormal(p);
        vec3 viewDir = -rd;

        // Base material color with subtle variation based on position - slightly brighter
        vec3 baseColor = 0.7 + 0.25 * sin(p * 2.0 + iTime * 0.3);
        baseColor = mix(vec3(0.9), baseColor, 0.4); // Brighter base material

        // Apply enhanced multi-light lighting
        col = calculateLighting(p, normal, viewDir, baseColor);

        // Atmospheric fog with subtle color tinting - reduced fog effect for brightness
        float fog = 1.0 - exp(-t * 0.02); // Reduced fog density from 0.04 to 0.02
        vec3 fogColor = vec3(0.05, 0.08, 0.15);  // Brighter fog color
        col = mix(col, fogColor, fog);
    } else {
        // Background with subtle gradient - brighter background
        float gradient = length(uv) * 0.3;
        col = vec3(0.03, 0.05, 0.1) * gradient; // Brighter background
    }

    fragColor = vec4(col, 1.0);
}