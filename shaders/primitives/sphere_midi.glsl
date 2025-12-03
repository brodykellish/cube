// Sphere Primitive with MIDI parameter control
// Demonstrates MIDI parameter usage
//
// MIDI Controls:
//   iParam0 (n/m): Sphere radius (0.5 - 5.0)
//   iParam1 (,/.): Rotation speed (0.0 - 5.0)
//   iParam2 ([/]): Color hue shift (0.0 - 1.0)
//   iParam3 (;/'): Fog density (0.0 - 0.3)

// === SDF ===
float sdSphere(vec3 p, float radius) {
    return length(p) - radius;
}

// === Raymarching ===
float sceneSDF(vec3 p) {
    // Radius controlled by iParam0
    float radius = mix(0.5, 5.0, iParam0);
    return sdSphere(p, radius);
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
    // Light position rotation speed controlled by iParam1
    float speed = mix(0.0, 5.0, iParam1);
    vec3 lightPos = vec3(4.0 * sin(iTime * speed), 3.0, 4.0 * cos(iTime * speed));
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
vec2 getSphereUV(vec3 p) {
    vec3 n = normalize(p);
    float theta = atan(n.z, n.x);
    float phi = asin(n.y);

    vec2 uv;
    uv.x = (theta + 3.14159265) / (2.0 * 3.14159265);
    uv.y = (phi + 1.5707963) / 3.14159265;

    return uv;
}

float checkerboard(vec2 uv, float scale) {
    vec2 grid = floor(uv * scale);
    return mod(grid.x + grid.y, 2.0);
}

// === Color Utilities ===
vec3 hueShift(vec3 color, float shift) {
    // Simple hue shift by rotating in RGB space
    float angle = shift * 6.28318;
    float s = sin(angle);
    float c = cos(angle);

    mat3 rotMat = mat3(
        c, -s, 0.0,
        s, c, 0.0,
        0.0, 0.0, 1.0
    );

    return rotMat * color;
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

        // Sphere coloring with checkerboard
        vec2 surfaceUV = getSphereUV(p);
        float checker = checkerboard(surfaceUV, 16.0);
        float heightFactor = (p.y + 1.5) / 3.0;

        vec3 topColor1 = vec3(0.9, 0.4, 0.5);   // Light pink
        vec3 topColor2 = vec3(0.3, 0.1, 0.2);   // Dark red
        vec3 bottomColor1 = vec3(0.4, 0.7, 0.9); // Light blue
        vec3 bottomColor2 = vec3(0.1, 0.2, 0.3); // Dark blue

        vec3 color1 = mix(bottomColor1, topColor1, heightFactor);
        vec3 color2 = mix(bottomColor2, topColor2, heightFactor);

        vec3 baseColor = mix(color1, color2, checker);

        // Apply hue shift controlled by iParam2
        baseColor = hueShift(baseColor, iParam2);

        // Apply lighting
        color = simpleLighting(p, rd, normal, baseColor);

        // Fog density controlled by iParam3
        float fogDensity = mix(0.0, 0.3, iParam3);
        float fog = 1.0 - exp(-t * fogDensity);
        color = mix(color, vec3(0.05, 0.05, 0.1), fog);
    }

    fragColor = vec4(color, 1.0);
}
