// Sphere Template (Python String Formatting Approach)
// Uses {{PLACEHOLDER}} syntax for Python format() injection

{INCLUDE_SDF_PRIMITIVES}

{INCLUDE_RAYMARCH}

{INCLUDE_LIGHTING}

// Scene definition
float sceneSDF(vec3 p) {{
    // Pulsing sphere
    float pulseSpeed = {PULSE_SPEED};
    float pulseAmount = {PULSE_AMOUNT};
    float radius = {BASE_RADIUS} + sin(iTime * pulseSpeed) * pulseAmount;

    return sdSphere(p, radius);
}}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {{
    // Normalized coordinates
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Camera from uniforms
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    // Raymarch
    float t = raymarch(ro, rd, 20.0);

    vec3 color = vec3(0.0);

    if (t > 0.0) {{
        // Hit something
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        // Rotating light
        vec3 lightPos = vec3(
            sin(iTime * 0.5) * 3.0,
            2.0,
            cos(iTime * 0.5) * 3.0
        );

        // Base color (customizable)
        vec3 baseColor = vec3({COLOR_R}, {COLOR_G}, {COLOR_B});

        // Apply lighting
        color = phongLighting(p, rd, normal, lightPos, baseColor);

        // Fog
        float fogAmount = 1.0 - exp(-t * 0.1);
        vec3 fogColor = vec3(0.05, 0.05, 0.1);
        color = mix(color, fogColor, fogAmount);
    }} else {{
        // Background gradient
        float gradient = dot(normalize(rd), vec3(0.0, 1.0, 0.0)) * 0.5 + 0.5;
        color = mix(vec3(0.02, 0.02, 0.05), vec3(0.05, 0.05, 0.15), gradient);
    }}

    fragColor = vec4(color, 1.0);
}}
