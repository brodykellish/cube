// Volumetric rotating torus shader
// Creates a colorful torus that rotates slowly, perfect for volumetric cube

// Rotation matrix around Y axis
mat2 rot2D(float angle) {
    float s = sin(angle);
    float c = cos(angle);
    return mat2(c, -s, s, c);
}

// Torus SDF
float sdTorus(vec3 p, vec2 t) {
    vec2 q = vec2(length(p.xz) - t.x, p.y);
    return length(q) - t.y;
}

// Scene distance function
float sceneSDF(vec3 p) {
    // Rotate the torus slowly
    vec3 rotatedP = p;
    rotatedP.xz = rot2D(iTime * 0.3) * rotatedP.xz;
    rotatedP.xy = rot2D(iTime * 0.2) * rotatedP.xy;

    // Torus parameters (major radius, minor radius)
    vec2 torusParams = vec2(1.5, 0.5);

    return sdTorus(rotatedP, torusParams);
}

// Calculate normal
vec3 calcNormal(vec3 p) {
    float eps = 0.001;
    vec2 h = vec2(eps, 0.0);
    return normalize(vec3(
        sceneSDF(p + h.xyy) - sceneSDF(p - h.xyy),
        sceneSDF(p + h.yxy) - sceneSDF(p - h.yxy),
        sceneSDF(p + h.yyx) - sceneSDF(p - h.yyx)
    ));
}

// Raymarch
float raymarch(vec3 ro, vec3 rd, float maxDist) {
    float t = 0.0;

    for (int i = 0; i < 80; i++) {
        vec3 p = ro + rd * t;
        float d = sceneSDF(p);

        if (d < 0.001) {
            return t;
        }

        if (t > maxDist) {
            break;
        }

        t += d * 0.8;
    }

    return -1.0;
}

// Enhanced lighting with multiple lights
vec3 shade(vec3 p, vec3 rd, vec3 normal) {
    // Two rotating lights
    vec3 light1Pos = vec3(
        sin(iTime * 0.7) * 4.0,
        2.0,
        cos(iTime * 0.7) * 4.0
    );

    vec3 light2Pos = vec3(
        cos(iTime * 0.5) * 4.0,
        -2.0,
        sin(iTime * 0.5) * 4.0
    );

    // Light 1 (warm)
    vec3 light1Dir = normalize(light1Pos - p);
    float diff1 = max(dot(normal, light1Dir), 0.0);
    vec3 light1Color = vec3(1.0, 0.8, 0.6);

    // Light 2 (cool)
    vec3 light2Dir = normalize(light2Pos - p);
    float diff2 = max(dot(normal, light2Dir), 0.0);
    vec3 light2Color = vec3(0.6, 0.8, 1.0);

    // Specular highlights
    vec3 reflectDir1 = reflect(-light1Dir, normal);
    float spec1 = pow(max(dot(-rd, reflectDir1), 0.0), 32.0);

    vec3 reflectDir2 = reflect(-light2Dir, normal);
    float spec2 = pow(max(dot(-rd, reflectDir2), 0.0), 32.0);

    // Rainbow color based on position
    vec3 baseColor = vec3(
        0.5 + 0.5 * sin(p.x * 2.0 + iTime),
        0.5 + 0.5 * sin(p.y * 2.0 + iTime + 2.0),
        0.5 + 0.5 * sin(p.z * 2.0 + iTime + 4.0)
    );

    // Combine lighting
    vec3 ambient = baseColor * 0.15;
    vec3 diffuse = baseColor * (diff1 * light1Color + diff2 * light2Color) * 0.6;
    vec3 specular = (light1Color * spec1 + light2Color * spec2) * 0.4;

    // Rim lighting
    float rim = 1.0 - max(dot(normal, -rd), 0.0);
    rim = pow(rim, 3.0);
    vec3 rimColor = vec3(0.5, 0.7, 1.0) * rim * 0.3;

    return ambient + diffuse + specular + rimColor;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    // Normalized coordinates
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use camera from renderer
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    // Raymarch
    float t = raymarch(ro, rd, 20.0);

    vec3 color = vec3(0.0);

    if (t > 0.0) {
        // Hit the torus
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        color = shade(p, rd, normal);

        // Distance fog
        float fogAmount = 1.0 - exp(-t * 0.08);
        vec3 fogColor = vec3(0.02, 0.02, 0.08);
        color = mix(color, fogColor, fogAmount);
    } else {
        // Dark space background
        vec3 bgColor = vec3(0.01, 0.01, 0.05);

        // Add some stars
        float stars = pow(sin(fragCoord.x * 1000.0) * sin(fragCoord.y * 1000.0), 50.0);
        bgColor += vec3(stars) * 0.5;

        color = bgColor;
    }

    fragColor = vec4(color, 1.0);
}
