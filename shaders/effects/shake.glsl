// Bass shake effect: rattles the image when iParam1 is activated
// iChannel0: source frame
// iParam1: shake intensity (0..1 -> 0..0.1 UV displacement)

// Noise function from synth2.glsl
float hash1(float x) {
    return fract(sin(x * 11.1753) * 192652.37862);
}

float nse1(float x) {
    float fl = floor(x);
    return mix(hash1(fl), hash1(fl + 1.0), smoothstep(0.0, 1.0, fract(x)));
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float intensity = clamp(iParam1, 0.0, 1.0) * clamp(iParam7, 0.0, 1.0);
    
    // Only apply shake if iParam1 is activated (greater than threshold)
    if (intensity < 0.001) {
        fragColor = texture(iChannel0, uv);
        return;
    }
    
    // Time-based shake using noise function (from synth2.glsl)
    float s = iTime * 50.0;
    vec2 shk = (vec2(nse1(s), nse1(s + 11.0)) * 2.0 - 1.0) * intensity * 0.1;
    
    // Apply shake to UV coordinates
    vec2 shakenUV = uv + shk;
    
    // Clamp to valid UV range to prevent edge artifacts
    shakenUV = clamp(shakenUV, vec2(0.0), vec2(1.0));
    
    fragColor = texture(iChannel0, shakenUV);
}

