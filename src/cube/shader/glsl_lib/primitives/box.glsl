// Box Primitive
{INCLUDE_UTILITIES}

float sceneSDF(vec3 p) {{
    // Static box centered at world origin
    vec3 size = vec3(1.0, 1.5, 1.0);
    float box = sdBox(p, size);

    // Add debug axes if enabled (always at world origin)
    if (iDebugAxes > 0.5) {{
        float camDist = length(iCameraPos);
        float axesScale = camDist;
        float axes = sdDebugAxes(p, axesScale);  // Axes at world origin
        return min(box, axes);
    }}

    return box;
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

        // Check if we hit axes or box
        vec3 baseColor;
        if (iDebugAxes > 0.5) {{
            float camDist = length(ro);
            float axesScale = camDist;
            float axesDist = sdDebugAxes(p, axesScale);

            if (axesDist < 0.001) {{
                // We hit the axes - color them appropriately
                baseColor = getAxisColor(p, axesScale);
            }} else {{
                // We hit the box - use normal box coloring
                vec2 uv = getBoxUV(p, normal);
                float checker = checkerboard(uv, 4.0);
                float heightFactor = (p.y + 1.5) / 3.0;

                vec3 topColor1 = vec3(0.9, 0.7, 0.3);   // Light yellow
                vec3 topColor2 = vec3(0.4, 0.3, 0.1);   // Dark brown
                vec3 bottomColor1 = vec3(0.5, 0.9, 0.7); // Light teal
                vec3 bottomColor2 = vec3(0.1, 0.3, 0.2); // Dark green

                vec3 color1 = mix(bottomColor1, topColor1, heightFactor);
                vec3 color2 = mix(bottomColor2, topColor2, heightFactor);

                baseColor = mix(color1, color2, checker);
            }}
        }} else {{
            // Debug axes disabled - use normal box coloring
            vec2 uv = getBoxUV(p, normal);
            float checker = checkerboard(uv, 4.0);
            float heightFactor = (p.y + 1.5) / 3.0;

            vec3 topColor1 = vec3(0.9, 0.7, 0.3);   // Light yellow
            vec3 topColor2 = vec3(0.4, 0.3, 0.1);   // Dark brown
            vec3 bottomColor1 = vec3(0.5, 0.9, 0.7); // Light teal
            vec3 bottomColor2 = vec3(0.1, 0.3, 0.2); // Dark green

            vec3 color1 = mix(bottomColor1, topColor1, heightFactor);
            vec3 color2 = mix(bottomColor2, topColor2, heightFactor);

            baseColor = mix(color1, color2, checker);
        }}

        // Apply lighting
        color = simpleLighting(p, rd, normal, baseColor);

        // Simple fog
        float fog = 1.0 - exp(-t * 0.1);
        color = mix(color, vec3(0.05, 0.05, 0.1), fog);
    }}

    fragColor = vec4(color, 1.0);
}}