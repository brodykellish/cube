// Displacement map: offset a second texture using the luminance of the first
// iChannel0: displacement source (e.g., webcam)
// iChannel1: image to displace
// iParam0: displacement amount (0..1 -> 0..0.05 UV)
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    float intensity = clamp(iParam7, 0.0, 1.0);
    if (intensity < 0.001) {
        fragColor = texture(iChannel1, uv);
        return;
    }
    vec3 dispSample = texture(iChannel0, uv).rgb;
    float disp = dot(dispSample, vec3(0.3333)) * 2.0 - 1.0;
    float amt = mix(0.0, 0.05, clamp(iParam0, 0.0, 1.0) * intensity);
    vec2 displacedUV = uv + disp * amt;
    vec3 color = texture(iChannel1, displacedUV).rgb;
    fragColor = vec4(color, 1.0);
}
