// Bloom effect: extracts bright areas, blurs them, and adds back to base
// iChannel0: base image
// iParam0: bloom strength (0..1 -> 0..1.5x additive)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 texel = 1.0 / iResolution.xy;
    
    float strength = clamp(iParam0, 0.0, 1.0) * clamp(iParam7, 0.0, 1.0);
    
    // Sample base color
    vec3 base = texture(iChannel0, uv).rgb;
    
    // Blur the image (simple 9-sample blur)
    float blurRadius = mix(2.0, 8.0, strength);
    vec2 offset = texel * blurRadius;
    
    vec3 blurSum = base;
    blurSum += texture(iChannel0, uv + vec2(-offset.x, -offset.y)).rgb;
    blurSum += texture(iChannel0, uv + vec2(0.0, -offset.y)).rgb;
    blurSum += texture(iChannel0, uv + vec2(offset.x, -offset.y)).rgb;
    blurSum += texture(iChannel0, uv + vec2(-offset.x, 0.0)).rgb;
    blurSum += texture(iChannel0, uv + vec2(offset.x, 0.0)).rgb;
    blurSum += texture(iChannel0, uv + vec2(-offset.x, offset.y)).rgb;
    blurSum += texture(iChannel0, uv + vec2(0.0, offset.y)).rgb;
    blurSum += texture(iChannel0, uv + vec2(offset.x, offset.y)).rgb;
    
    vec3 blurred = blurSum / 9.0;
    
    // Extract bright areas from blurred image and add to base
    float blurLuma = dot(blurred, vec3(0.299, 0.587, 0.114));
    vec3 bloom = blurred * smoothstep(0.3, 0.6, blurLuma);
    
    // Add bloom to base (additive blending)
    float bloomAmount = mix(0.0, 1.5, strength);
    vec3 color = base + bloom * bloomAmount;
    
    fragColor = vec4(color, 1.0);
}
