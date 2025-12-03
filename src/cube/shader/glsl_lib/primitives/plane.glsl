// Infinite Plane (with camera height restriction)
{INCLUDE_UTILITIES}

float sceneSDF(vec3 p) {{
    // Infinite ground plane at world origin (y = 0)
    float plane = sdPlane(p, vec3(0.0, 1.0, 0.0), 0.0);

    // Add debug axes if enabled (always at world origin)
    if (iDebugAxes > 0.5) {{
        float camDist = length(iCameraPos);
        float axesScale = camDist;
        float axes = sdDebugAxes(p, axesScale);  // Axes at world origin
        return min(plane, axes);
    }}

    return plane;
}}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {{
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Clamp camera above plane (minimum height = 1.0)
    vec3 ro = iCameraPos;
    ro.y = max(ro.y, 1.0);

    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);

    float t = raymarch(ro, rd, 50.0);

    vec3 color = vec3(0.02, 0.02, 0.05);

    if (t > 0.0) {{
        vec3 p = ro + rd * t;
        vec3 normal = calcNormal(p);

        // Get plane UV coordinates
        vec2 uv = getPlaneUV(p);

        // Generate checkerboard pattern
        float checker = checkerboard(uv, 2.0); // 2x2 unit grid

        // For plane, use Z position for gradient since Y is always 0
        float depthFactor = 1.0 - exp(-abs(p.z) * 0.1); // Depth-based gradient

        // Create gradient colors based on distance
        vec3 nearColor1 = vec3(0.9, 0.9, 0.5);   // Light yellow
        vec3 nearColor2 = vec3(0.4, 0.4, 0.2);   // Dark olive
        vec3 farColor1 = vec3(0.6, 0.4, 0.8);    // Light purple
        vec3 farColor2 = vec3(0.2, 0.1, 0.3);    // Dark purple

        // Interpolate colors based on depth
        vec3 color1 = mix(nearColor1, farColor1, depthFactor);
        vec3 color2 = mix(nearColor2, farColor2, depthFactor);

        vec3 baseColor = mix(color1, color2, checker);

        // Apply lighting
        color = simpleLighting(p, rd, normal, baseColor);

        // Stronger distance fog for infinite plane
        float fog = 1.0 - exp(-t * 0.05);
        color = mix(color, vec3(0.1, 0.1, 0.15), fog);
    }} else {{
        // Sky gradient
        float gradient = dot(rd, vec3(0.0, 1.0, 0.0)) * 0.5 + 0.5;
        color = mix(vec3(0.1, 0.1, 0.2), vec3(0.3, 0.4, 0.6), gradient);
    }}

    fragColor = vec4(color, 1.0);
}}