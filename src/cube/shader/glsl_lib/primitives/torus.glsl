// Torus Primitive
{INCLUDE_UTILITIES}

float sceneSDF(vec3 p) {{
    // Static torus centered at world origin
    vec2 radii = vec2(1.5, 0.5);
    float torus = sdTorus(p, radii);

    // Add debug axes if enabled (always at world origin)
    if (iDebugAxes > 0.5) {{
        float camDist = length(iCameraPos);
        float axesScale = camDist;
        float axes = sdDebugAxes(p, axesScale);  // Axes at world origin
        return min(torus, axes);
    }}

    return torus;
}}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {{
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    float t = raymarch(ro, rd, 20.0);

    vec3 color = vec3(0.02, 0.02, 0.05);

    if (t > 0.0) {{
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        // Get torus UV coordinates (major radius = 1.5)
        vec2 uv = getTorusUV(p, 1.5);

        // Generate checkerboard pattern
        float checker = checkerboard(uv, 12.0); // 12x12 grid on torus

        // Colors change based on vertical position
        // Torus can range from -0.5 to 0.5 in Y (minor radius)
        float heightFactor = (p.y + 2.0) / 4.0; // Normalize to 0-1 range

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
    }}

    fragColor = vec4(color, 1.0);
}}