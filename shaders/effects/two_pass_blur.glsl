// Approximated two-pass gaussian blur in a single pass
// iChannel0: source frame
// iParam0: blur radius scale (0..1 -> 0..3.0 texel radius multiplier)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 texel = 1.0 / iResolution.xy;
    float radius = mix(0.0, 3.0, clamp(iParam0, 0.0, 1.0));

    // weights from original two-pass example
    float w[9];
    w[0]=0.10855; w[1]=0.13135; w[2]=0.10406; w[3]=0.07216; w[4]=0.04380; w[5]=0.02328; w[6]=0.01083; w[7]=0.00441; w[8]=0.00157;
    float o[9];
    o[0]=0.66293; o[1]=2.47904; o[2]=4.46232; o[3]=6.44568; o[4]=8.42917; o[5]=10.41281; o[6]=12.39664; o[7]=14.38070; o[8]=16.36501;

    vec3 col = vec3(0.0);
    
    // Sample in cross pattern (horizontal + vertical) approximating two-pass blur
    // Each weight samples a symmetric pair around center
    for(int i=0;i<9;i++){
        vec2 offs = texel * o[i] * radius;
        // Horizontal blur samples (left + right)
        vec3 hSample = texture(iChannel0, uv + vec2(offs.x, 0.0)).rgb + texture(iChannel0, uv - vec2(offs.x, 0.0)).rgb;
        // Vertical blur samples (up + down)  
        vec3 vSample = texture(iChannel0, uv + vec2(0.0, offs.y)).rgb + texture(iChannel0, uv - vec2(0.0, offs.y)).rgb;
        // Combine horizontal and vertical (approximating two-pass)
        col += (hSample + vSample) * w[i];
    }
    
    // Normalize: each weight samples 2 horizontal + 2 vertical = 4 samples total
    // Sum of weights * 4 samples per weight
    float weightSum = (w[0] + w[1] + w[2] + w[3] + w[4] + w[5] + w[6] + w[7] + w[8]) * 4.0;
    fragColor = vec4(col / weightSum, 1.0);
}
