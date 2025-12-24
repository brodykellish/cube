// Matrix rain effect
// Classic digital rain visualization with falling characters
// Additively combines with previous shader node output

vec3 shade(vec2 uv, float t) {
    vec2 p = vec2(uv.x, -uv.y) * vec2(40., 25.);
    vec2 g = floor(p), f = fract(p);
    float col = g.x;
    float spd = .4 + fract(sin(col * 67.) * 4e4) * .4;
    float y = fract(t * spd - g.y * .05);
    float idx = g.y + floor(t * spd * 20.);
    float c = step(.3, fract(sin(idx * col * 99.) * 4e4)) * smoothstep(1., .1, y);
    float head = smoothstep(.1, .0, y);
    float r = fract(sin(idx * col * 37.) * 4e4);
    float ch = step(abs(f.x - .5), .3) * step(abs(f.y - .2 - r * .6), .06);
    ch += step(abs(f.y - .5), .3) * step(abs(f.x - .2 - r * .6), .06);
    return vec3(c * .2, c * .85 + head, c * .3) * max(.15, ch);
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    
    // Previous node's output
    vec3 base = texture(iChannel0, uv).rgb;
    
    // Generate matrix rain effect
    vec3 matrix = shade(uv, iTime);
    
    // Additively combine
    vec3 col = base + matrix;
    
    fragColor = vec4(col, 1.0);
}

