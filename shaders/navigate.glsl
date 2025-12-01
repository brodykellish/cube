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

        // Lighting
        vec3 lightDir = normalize(vec3(1.0, 1.0, 1.0));
        float diff = max(dot(normal, lightDir), 0.0);
        float ambient = 0.3;

        // Color based on position
        vec3 baseColor = 0.5 + 0.5 * sin(p * 2.0 + iTime);

        col = baseColor * (ambient + diff);

        // Fog
        float fog = 1.0 - exp(-t * 0.05);
        col = mix(col, vec3(0.1, 0.1, 0.15), fog);
    } else {
        // Background
        col = vec3(0.1, 0.1, 0.15);
    }

    fragColor = vec4(col, 1.0);
}
