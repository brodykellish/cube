// Hue-spin via RGB->HSB conversion
// iChannel0: source frame
// iParam1: saturation scale (0..1 -> 0..2)
// iParam2: brightness scale (0..1 -> 0..2)
// iParam3: hue speed (0..1 -> 0..2 pi per second)

vec3 rgb2hsb(vec3 c){
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = c.g < c.b ? vec4(c.bg, K.wz) : vec4(c.gb, K.xy);
    vec4 q = c.r < p.x ? vec4(p.xyw, c.r) : vec4(c.r, p.yzx);
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y)/(6.0*d + e)), d/(q.x + e), q.x);
}

vec3 hsb2rgb(vec3 c){
    vec4 K = vec4(1.0, 2.0/3.0, 1.0/3.0, 3.0);
    vec3 p = abs(fract(c.xxx + K.xyz) * 6.0 - K.www);
    return c.z * mix(K.xxx, clamp(p - K.xxx, 0.0, 1.0), c.y);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 tex = texture(iChannel0, uv).rgb;
    vec3 hsb = rgb2hsb(tex);
    float intensity = clamp(iParam7, 0.0, 1.0);
    float speed = mix(0.0, 6.2831853, clamp(iParam3, 0.0, 1.0) * intensity);
    hsb.x = fract(hsb.x + iTime * speed / (2.0 * 3.14159265));
    hsb.y *= mix(1.0, 2.0, clamp(iParam1, 0.0, 1.0) * intensity);
    hsb.z *= mix(1.0, 2.0, clamp(iParam2, 0.0, 1.0) * intensity);
    vec3 rgb = hsb2rgb(hsb);
    fragColor = vec4(rgb, 1.0);
}
