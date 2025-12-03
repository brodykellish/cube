// Pyramid Primitive - standalone shader

// === SDF ===
float sdPyramid(vec3 p, float h) {
    float m2 = h * h + 0.25;

    // Symmetry
    p.xz = abs(p.xz);
    p.xz = (p.z > p.x) ? p.zx : p.xz;
    p.xz -= 0.5;

    // Project into face plane (2D)
    vec3 q = vec3(p.z, h * p.y - 0.5 * p.x, h * p.x + 0.5 * p.y);

    float s = max(-q.x, 0.0);
    float t = clamp((q.y - 0.5 * p.z) / (m2 + 0.25), 0.0, 1.0);

    float a = m2 * (q.x + s) * (q.x + s) + q.y * q.y;
    float b = m2 * (q.x + 0.5 * t) * (q.x + 0.5 * t) + (q.y - m2 * t) * (q.y - m2 * t);

    float d2 = min(q.y, -q.x * m2 - q.y * 0.5) > 0.0 ? 0.0 : min(a, b);

    // Recover 3D and scale, and add sign
    return sqrt((d2 + q.z * q.z) / m2) * sign(max(q.z, -p.y));
}

float sceneSDF(vec3 p) {
    // iParam3 controls height ratio (0=flat, 1=height equals base area)
    // Base has side length 2.0, so area = 4.0
    // Height = iParam3 * 4.0 for proper ratio
    float baseArea = 4.0;
    float height = iParam3 * baseArea;
    // Clamp to avoid degenerate pyramid
    height = max(height, 0.01);

    return sdPyramid(p, height);
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

// === Lighting ===
vec3 simpleLighting(vec3 p, vec3 rd, vec3 normal, vec3 color) {
    vec3 lightPos = vec3(4.0 * sin(iTime * 0.5), 3.0, 4.0 * cos(iTime * 0.5));
    vec3 lightDir = normalize(lightPos - p);

    float diff = max(dot(normal, lightDir), 0.0);
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(-rd, reflectDir), 0.0), 32.0);

    vec3 ambient = color * 0.2;
    vec3 diffuse = color * diff * 0.7;
    vec3 specular = vec3(1.0) * spec * 0.5;

    return ambient + diffuse + specular;
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use precomputed camera vectors for smooth rotation
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    float t = raymarch(ro, rd, 20.0);

    vec3 color = vec3(0.02, 0.02, 0.05);

    if (t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        // MIDI-controlled RGB color
        // iParam0 = red, iParam1 = green, iParam2 = blue
        // All params are already normalized to 0.0-1.0
        vec3 baseColor = vec3(iParam0, iParam1, iParam2);

        // Ensure color isn't completely black
        baseColor = max(baseColor, vec3(0.1));

        // Apply lighting
        color = simpleLighting(p, rd, normal, baseColor);

        // Simple fog
        float fog = 1.0 - exp(-t * 0.1);
        color = mix(color, vec3(0.05, 0.05, 0.1), fog);
    }

    fragColor = vec4(color, 1.0);
}
