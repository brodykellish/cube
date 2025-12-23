// Discard pixels above a luminance threshold
// iChannel0: source frame
// iParam0: threshold (0..1), default 0.5. Pixels brighter than threshold are discarded.
void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec4 cam = texture(iChannel0, uv);
    float avg = dot(cam.rgb, vec3(0.33333));
    float th = clamp(iParam0, 0.0, 1.0);
    if (avg > th) {
        discard;
    }
    fragColor = cam;
}
