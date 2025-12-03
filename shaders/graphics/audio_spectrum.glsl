// Audio Spectrum Visualizer - 3D Radial Topographic Map
// Visualizes audio frequency spectrum as a radial heightmap
// Radius = frequency, Height = amplitude
// Use --audio flag to specify input audio/video file

// Get audio spectrum amplitude at a given frequency (0-1 range)
// with smooth interpolation between bins
float getAmplitude(float freq) {
    // Use texture filtering to smoothly interpolate between frequency bins
    // GL_LINEAR filtering in texture setup handles this automatically
    vec4 sample = texture(iChannel0, vec2(freq, 0.5));
    return sample.r; // Red channel contains amplitude
}

// Get very smooth amplitude with wide spatial averaging
float getAmplitudeSmooth(float freq) {
    // Use wider kernel for much smoother result
    float kernelSize = 0.08; // 8% on each side

    // 7-tap filter for maximum smoothness
    float amp0 = getAmplitude(freq);
    float amp1 = getAmplitude(clamp(freq - kernelSize, 0.0, 1.0));
    float amp2 = getAmplitude(clamp(freq + kernelSize, 0.0, 1.0));
    float amp3 = getAmplitude(clamp(freq - kernelSize * 2.0, 0.0, 1.0));
    float amp4 = getAmplitude(clamp(freq + kernelSize * 2.0, 0.0, 1.0));
    float amp5 = getAmplitude(clamp(freq - kernelSize * 3.0, 0.0, 1.0));
    float amp6 = getAmplitude(clamp(freq + kernelSize * 3.0, 0.0, 1.0));

    // Gaussian-like weighted average for smooth falloff
    return amp0 * 0.3 +
           (amp1 + amp2) * 0.2 +
           (amp3 + amp4) * 0.1 +
           (amp5 + amp6) * 0.05;
}

// Distance function for the audio spectrum heightmap
float mapSpectrum(vec3 p) {
    // Convert to cylindrical coordinates
    float radius = length(p.xz);
    float angle = atan(p.z, p.x);

    // Map radius to frequency (0 = center, 1 = outer edge)
    // Smaller divisor = larger buckets (each frequency spans more radius)
    float freq = clamp(radius / 2.5, 0.0, 0.99);

    // Get smoothed amplitude from audio spectrum
    float amplitude = getAmplitudeSmooth(freq);

    // Apply gentle exponential scaling for smooth, dramatic variation
    // Higher exponent (closer to 1.0) = more linear = spread variation across spectrum
    amplitude = pow(amplitude, 0.85) * 1.3;

    // Height based on scaled amplitude
    float height = amplitude * 7.0;

    // Distance to surface
    return p.y - height;
}

// Raymarching function
float raymarch(vec3 ro, vec3 rd) {
    float t = 0.0;
    for (int i = 0; i < 120; i++) {
        vec3 p = ro + rd * t;
        float d = mapSpectrum(p);

        if (d < 0.01 || t > 50.0) break;

        t += d * 0.3; // Smaller step for smoother surface and no tearing
    }
    return t;
}

// Calculate normal using gradient with larger epsilon for smoother normals
vec3 calcNormal(vec3 p) {
    vec2 e = vec2(0.02, 0.0); // Larger epsilon = smoother normals
    return normalize(vec3(
        mapSpectrum(p + e.xyy) - mapSpectrum(p - e.xyy),
        mapSpectrum(p + e.yxy) - mapSpectrum(p - e.yxy),
        mapSpectrum(p + e.yyx) - mapSpectrum(p - e.yyx)
    ));
}

void mainImage(out vec4 fragColor, vec2 fragCoord) {
    // Normalized pixel coordinates
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;

    // Use precomputed camera vectors for smooth rotation
    vec3 cameraPos = iCameraPos;
    vec3 right = iCameraRight;
    vec3 up = iCameraUp;
    vec3 forward = iCameraForward;

    // Ray direction
    vec3 rd = normalize(uv.x * right + uv.y * up + 1.5 * forward);

    // Raymarch the spectrum
    float t = raymarch(cameraPos, rd);

    // Color the scene
    vec3 col = vec3(0.0);

    if (t < 50.0) {
        vec3 p = cameraPos + rd * t;
        vec3 normal = calcNormal(p);

        // Lighting
        vec3 lightDir = normalize(vec3(1.0, 1.0, 1.0));
        float diff = max(dot(normal, lightDir), 0.0);
        float ambient = 0.3;

        // Color based on height and frequency
        float radius = length(p.xz);
        float freq = clamp(radius / 10.0, 0.0, 0.99);
        float amplitude = getAmplitude(freq);

        // Colorful gradient based on frequency (low = red, mid = green, high = blue)
        vec3 baseColor = vec3(
            1.0 - freq,           // Red for low frequencies
            sin(freq * 3.14159),  // Green for mid frequencies
            freq                  // Blue for high frequencies
        );

        // Modulate color by amplitude
        baseColor *= (0.5 + amplitude * 1.5);

        // Add beat pulse highlight
        baseColor += vec3(1.0, 1.0, 1.0) * iBeatPulse * 0.3 * amplitude;

        // Apply lighting
        col = baseColor * (ambient + diff * 0.7);

        // Add specular highlight
        vec3 viewDir = normalize(cameraPos - p);
        vec3 reflectDir = reflect(-lightDir, normal);
        float spec = pow(max(dot(viewDir, reflectDir), 0.0), 32.0);
        col += vec3(1.0) * spec * 0.5;

        // Fog
        float fog = 1.0 - exp(-t * 0.03);
        col = mix(col, vec3(0.05, 0.05, 0.1), fog);

        // Add glow for high amplitudes
        if (amplitude > 0.5) {
            col += baseColor * (amplitude - 0.5) * 0.3;
        }
    } else {
        // Background - dark gradient
        col = vec3(0.05, 0.05, 0.1) * (1.0 - length(uv) * 0.3);
    }

    fragColor = vec4(col, 1.0);
}
