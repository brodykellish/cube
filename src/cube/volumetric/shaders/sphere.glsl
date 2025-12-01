// Simple volumetric sphere shader
// Renders a raymarched sphere at the origin that looks good from all 6 cube faces

// Sphere SDF
float sdSphere(vec3 p, float radius) {
    return length(p) - radius;
}

// Scene distance function
float sceneSDF(vec3 p) {
    // Pulsing sphere at origin
    float pulseSpeed = 2.0;
    float pulseAmount = 0.3;
    float radius = 1.5 + sin(iTime * pulseSpeed) * pulseAmount;

    return sdSphere(p, radius);
}

// Calculate normal at point
vec3 calcNormal(vec3 p) {
    float eps = 0.001;
    vec2 h = vec2(eps, 0.0);
    return normalize(vec3(
        sceneSDF(p + h.xyy) - sceneSDF(p - h.xyy),
        sceneSDF(p + h.yxy) - sceneSDF(p - h.yxy),
        sceneSDF(p + h.yyx) - sceneSDF(p - h.yyx)
    ));
}

// Raymarch the scene
float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;

    for (int i = 0; i < 64; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);

        if (d < 0.001) {
            return t;
        }

        if (t > maxDist) {
            break;
        }

        t += d * 0.9;
    }

    return -1.0;
}

// Simple lighting
vec3 shade(vec3 p, vec3 rd, vec3 normal) {
    // Light position rotates around the scene
    vec3 lightPos = vec3(
        sin(iTime * 0.5) * 3.0,
        2.0,
        cos(iTime * 0.5) * 3.0
    );

    vec3 lightDir = normalize(lightPos - p);

    // Diffuse lighting
    float diff = max(dot(normal, lightDir), 0.0);

    // Specular
    vec3 reflectDir = reflect(-lightDir, normal);
    float spec = pow(max(dot(rd, reflectDir), 0.0), 32.0);

    // Base color (pulsing hue)
    float hue = iTime * 0.2;
    vec3 baseColor = vec3(
        0.5 + 0.5 * sin(hue),
        0.5 + 0.5 * sin(hue + 2.094),
        0.5 + 0.5 * sin(hue + 4.189)
    );

    // Combine lighting
    vec3 ambient = baseColor * 0.2;
    vec3 diffuse = baseColor * diff * 0.7;
    vec3 specular = vec3(1.0) * spec * 0.5;

    return ambient + diffuse + specular;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normalized coordinates
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use camera from shader renderer
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    // Raymarch
    float t = raymarch(ro, rd, 20.0);

    vec3 color = vec3(0.0);

    if (t > 0.0) {
        // Hit something
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        color = shade(p, rd, normal);

        // Fog based on distance
        float fogAmount = 1.0 - exp(-t * 0.1);
        vec3 fogColor = vec3(0.05, 0.05, 0.1);
        color = mix(color, fogColor, fogAmount);
    } else {
        // Background gradient
        float gradient = dot(normalize(rd), vec3(0.0, 1.0, 0.0)) * 0.5 + 0.5;
        color = mix(vec3(0.02, 0.02, 0.05), vec3(0.05, 0.05, 0.15), gradient);
    }

    fragColor = vec4(color, 1.0);
}
