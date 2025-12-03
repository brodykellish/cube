// Plane Primitive - standalone shader

// === SDF ===
float sdPlane(vec3 p, vec3 normal, float offset) {
    return dot(p, normal) + offset;
}

// === Raymarching ===
float sceneSDF(vec3 p) {
    return sdPlane(p, vec3(0.0, 1.0, 0.0), 0.0);
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

// === UV Mapping ===
vec2 getPlaneUV(vec3 p) {
    return p.xz;
}

float checkerboard(vec2 uv, float scale) {
    vec2 grid = floor(uv * scale);
    return mod(grid.x + grid.y, 2.0);
}

// === Main Shader ===
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Clamp camera above plane (minimum height = 1.0)
    vec3 ro = iCameraPos;
    ro.y = max(ro.y, 1.0);

    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    float t = raymarch(ro, rd, 50.0);

    vec3 color = vec3(0.02, 0.02, 0.05);

    if (t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        // Get plane UV coordinates
        vec2 surfaceUV = getPlaneUV(p);

        // Generate checkerboard pattern
        float checker = checkerboard(surfaceUV, 2.0);

        // Simple gradient based on distance from origin
        float distFromOrigin = length(p.xz);
        float distFactor = clamp(distFromOrigin / 10.0, 0.0, 1.0);

        vec3 nearColor1 = vec3(0.8, 0.9, 1.0);   // Light blue
        vec3 nearColor2 = vec3(0.2, 0.3, 0.4);   // Dark blue
        vec3 farColor1 = vec3(0.6, 0.4, 0.7);    // Light purple
        vec3 farColor2 = vec3(0.2, 0.1, 0.3);    // Dark purple

        vec3 color1 = mix(nearColor1, farColor1, distFactor);
        vec3 color2 = mix(nearColor2, farColor2, distFactor);

        vec3 baseColor = mix(color1, color2, checker);

        // Apply lighting
        color = simpleLighting(p, rd, normal, baseColor);

        // Distance-based fog
        float fog = 1.0 - exp(-t * 0.05);
        color = mix(color, vec3(0.05, 0.05, 0.1), fog);
    }

    fragColor = vec4(color, 1.0);
}
