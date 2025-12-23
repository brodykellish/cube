// Delay effect: RGB channel split with spatial offset (simulates temporal delay)
// iChannel0: source frame
// iParam0: delay amount (0..1 -> 0..0.1 UV offset)
// iParam1: mix mode (0=RGB split, 1=average of offset samples)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 texel = 1.0 / iResolution.xy;
    
    float delayAmt = mix(0.0, 0.1, clamp(iParam0, 0.0, 1.0));
    float mixMode = clamp(iParam1, 0.0, 1.0);
    
    // Create three "delayed" samples with different offsets
    vec2 offset1 = vec2(delayAmt * 0.5, 0.0);
    vec2 offset2 = vec2(delayAmt, 0.0);
    vec2 offset3 = vec2(delayAmt * 1.5, 0.0);
    
    vec3 a = texture(iChannel0, uv).rgb;
    vec3 b = texture(iChannel0, uv + offset1).rgb;
    vec3 c = texture(iChannel0, uv + offset2).rgb;
    
    // RGB split mode: use one channel from each sample
    vec3 split = vec3(a.r, b.g, c.b);
    
    // Average mode: blend all three samples
    vec3 avg = (a + b + c) / 3.0;
    
    // Mix between split and average
    vec3 color = mix(split, avg, mixMode);
    
    fragColor = vec4(color, 1.0);
}
