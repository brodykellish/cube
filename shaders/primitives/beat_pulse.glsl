// Beat Pulse - Sphere that pulses in sync with tap tempo
// Tap Pad 8 to set the BPM, sphere will pulse with the beat
// Controls:
// - iParam0: Pulse amplitude (0.0-1.0)
// - iParam1: Color hue (0.0-1.0)
// - iParam2: Sphere size (0.0-1.0, mapped to 0.5-2.0)
// - iParam3: Unused

// Ray-sphere intersection
float sphereIntersect(vec3 ro, vec3 rd, vec3 center, float radius) {
    vec3 oc = ro - center;
    float b = dot(oc, rd);
    float c = dot(oc, oc) - radius * radius;
    float discriminant = b * b - c;
    
    if (discriminant < 0.0) {
        return -1.0;
    }
    
    return -b - sqrt(discriminant);
}

// HSV to RGB conversion
vec3 hsv2rgb(vec3 c) {
    vec4 K = vec4(1.0, 2.0 / 3.0, 1.0 / 3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Camera setup using standard camera uniforms
    vec3 ro = iCameraPos;
    vec3 forward = iCameraForward;
    vec3 right = iCameraRight;
    vec3 up = iCameraUp;

    vec3 rd = normalize(forward + uv.x * right + uv.y * up);

    // Get beat trigger from MIDI system
    float pulse = iBeatTrigger;

    // If no tempo detected, show dim static sphere
    if (iBPM == 0.0) {
        float baseSize = mix(0.5, 2.0, iParam2);
        float t = sphereIntersect(ro, rd, vec3(0.0, 0.0, 0.0), baseSize);
        if (t > 0.0) {
            fragColor = vec4(0.2, 0.2, 0.3, 1.0);  // Dim sphere
        } else {
            fragColor = vec4(0.0);  // Black background
        }
        return;
    }

    // Pulse amplitude control
    float pulseAmplitude = iParam0;
    float radiusModulation = 1.0 + pulse * pulseAmplitude * 0.5;

    // Base sphere size from iParam2
    float baseSize = mix(0.5, 2.0, iParam2);
    float sphereRadius = baseSize * radiusModulation;

    // Ray-sphere intersection
    float t = sphereIntersect(ro, rd, vec3(0.0, 0.0, 0.0), sphereRadius);

    vec3 color = vec3(0.0);

    if (t > 0.0) {
        vec3 p = ro + rd * t;
        vec3 normal = normalize(p); // For sphere at origin, position IS normal

        // Lighting
        vec3 lightDir = normalize(vec3(1.0, 1.0, 1.0));
        float diffuse = max(dot(normal, lightDir), 0.0);
        float ambient = 0.3;

        // Color that shifts with beat and iParam1
        float hue = iParam1;
        float saturation = 0.8;
        float value = 0.5 + pulse * pulseAmplitude * 0.3;

        vec3 baseColor = hsv2rgb(vec3(hue, saturation, value));

        color = baseColor * (ambient + diffuse * 0.7);

        // Rim light on beat
        float rim = 1.0 - max(dot(normal, -rd), 0.0);
        rim = pow(rim, 3.0);
        color += rim * pulse * pulseAmplitude * vec3(1.0, 0.8, 0.6) * 0.3;
    } else {
        // Background - subtle pulse
        float bg = pulse * pulseAmplitude * 0.05;
        color = vec3(bg);
    }

    // Add glow
    float glow = pulse * pulseAmplitude * 0.05;
    color += vec3(glow, glow * 0.5, 0.0);

    fragColor = vec4(color, 1.0);
}