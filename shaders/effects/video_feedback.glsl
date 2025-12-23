// Video feedback with slight zoom and hue-driven offset
// iChannel0: live frame
// iChannel1: feedback buffer (previous output) optional
// iParam0: feedback zoom (0..1 -> 1.0..0.92 scale)
// iParam1: hue offset scale (0..1 -> 0..0.005 UV)

vec3 rgb2hsb(vec3 c){
    vec4 K = vec4(0.0, -1.0/3.0, 2.0/3.0, -1.0);
    vec4 p = c.g < c.b ? vec4(c.bg, K.wz) : vec4(c.gb, K.xy);
    vec4 q = c.r < p.x ? vec4(p.xyw, c.r) : vec4(c.r, p.yzx);
    float d = q.x - min(q.w, q.y);
    float e = 1.0e-10;
    return vec3(abs(q.z + (q.w - q.y)/(6.0*d + e)), d/(q.x + e), q.x);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec3 cam = texture(iChannel0, uv).rgb;
    vec3 tex = cam;
    float zoom = mix(1.0, 0.92, clamp(iParam0, 0.0, 1.0));
    vec2 fbUV = (uv - 0.5) * zoom + 0.5;
    vec3 hsb = rgb2hsb(cam);
    float angleX = cos(hsb.x * 6.2831853);
    float angleY = sin(hsb.x * 6.2831853);
    float offsetScale = mix(0.0, 0.005, clamp(iParam1, 0.0, 1.0));
    vec2 offset = vec2(angleX, angleY) * offsetScale;
    vec3 fb = texture(iChannel1, fbUV + offset).rgb;
    tex = mix(tex, fb + cam * 0.8, 0.9);
    tex = mix(tex, 1.0 - tex.gbr, step(1.0, tex.r));
    fragColor = vec4(tex, 1.0);
}
