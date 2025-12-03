// Torus Primitive - standalone shader

// === SDF ===
float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}

// === Raymarching ===
float sceneSDF(vec3 p) {
    vec2 radii = vec2(1.5, 0.5);
    return sdTorus(p, radii);
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
vec2 getTorusUV(vec3 p, float majorRadius) {
    float theta = atan(p.z, p.x);
    vec2 majorPoint = vec2(cos(theta), sin(theta)) * majorRadius;
    vec3 toSurface = p - vec3(majorPoint.x, 0.0, majorPoint.y);
    float phi = atan(toSurface.y, length(toSurface.xz) - majorRadius);

    vec2 uv;
    uv.x = (theta + 3.14159265) / (2.0 * 3.14159265);
    uv.y = (phi + 3.14159265) / (2.0 * 3.14159265);

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

    float t = raymarch(ro, rd, 20.0);

    vec3 color = vec3(0.02, 0.02, 0.05);

    if (t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        // Get torus UV coordinates
        vec2 surfaceUV = getTorusUV(p, 1.5);

        // Generate checkerboard pattern
        float checker = checkerboard(surfaceUV, 12.0);

        // Colors change based on vertical position
        float heightFactor = (p.y + 2.0) / 4.0;

        // Create gradient colors
        vec3 topColor1 = vec3(0.9, 0.6, 0.2);    // Light orange
        vec3 topColor2 = vec3(0.4, 0.2, 0.1);    // Dark brown
        vec3 bottomColor1 = vec3(0.2, 0.9, 0.5); // Light green
        vec3 bottomColor2 = vec3(0.1, 0.3, 0.2); // Dark forest green

        // Interpolate colors based on height
        vec3 color1 = mix(bottomColor1, topColor1, heightFactor);
        vec3 color2 = mix(bottomColor2, topColor2, heightFactor);

        vec3 baseColor = mix(color1, color2, checker);

        // Apply lighting
        color = simpleLighting(p, rd, normal, baseColor);

        // Simple fog
        float fog = 1.0 - exp(-t * 0.1);
        color = mix(color, vec3(0.05, 0.05, 0.1), fog);
    }

    fragColor = vec4(color, 1.0);
}
