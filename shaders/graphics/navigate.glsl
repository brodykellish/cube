// Navigate - Interactive 3D Scene with Keyboard Controls
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

        // Base color - lighter, more pastel tones
        vec3 baseColor = 0.6 + 0.3 * sin(p * 1.5 + iTime * 0.5);
        baseColor = mix(vec3(0.85), baseColor, 0.5);

        // Two main lights for testing
        vec3 light1Dir = normalize(vec3(1.0, 0.8, 0.6));
        vec3 light1Color = vec3(1.0, 0.5, 0.3);  // Warm orange

        vec3 light2Dir = normalize(vec3(-0.6, 1.0, 0.3));
        vec3 light2Color = vec3(0.3, 0.6, 1.0);  // Cool blue

        // Simple diffuse lighting
        float diff1 = max(dot(normal, light1Dir), 0.0);
        float diff2 = max(dot(normal, light2Dir), 0.0);

        // Add specular highlights carefully
        vec3 halfDir1 = normalize(light1Dir + viewDir);
        vec3 halfDir2 = normalize(light2Dir + viewDir);
        float specDot1 = max(dot(normal, halfDir1), 0.0);
        float specDot2 = max(dot(normal, halfDir2), 0.0);

        // Use smaller exponent to avoid numerical issues
        float spec1 = specDot1 * specDot1 * specDot1 * specDot1;  // ^4 instead of pow()
        float spec2 = specDot2 * specDot2 * specDot2 * specDot2;

        vec3 lighting = light1Color * (diff1 * baseColor + spec1 * 0.3) +
                        light2Color * (diff2 * baseColor + spec2 * 0.3);

        col = vec3(0.05) * baseColor + lighting;

        // Fog - fade to black
        float fog = 1.0 - exp(-t * 0.05);
        col = mix(col, vec3(0.0), fog);
    } else {
        // Background - fully black
        col = vec3(0.0);
    }

    fragColor = vec4(col, 1.0);
}
