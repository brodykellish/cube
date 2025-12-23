// Configurable 3x3 convolution
// iChannel0: source frame
// iParam0: kernel selector (0=emboss, 0.33=sharpen, 0.66=edge, 1=gaussian)
// iParam1: kernel intensity mix (0..1)

const float PI = 3.14159265359;

vec3 sample9(sampler2D t, vec2 uv, vec2 texel, mat3 k){
    vec3 c = vec3(0.0);
    c += texture(t, uv + texel * vec2(-1.0, -1.0)).rgb * k[0][0];
    c += texture(t, uv + texel * vec2(0.0, -1.0)).rgb * k[0][1];
    c += texture(t, uv + texel * vec2(1.0, -1.0)).rgb * k[0][2];
    c += texture(t, uv + texel * vec2(-1.0, 0.0)).rgb * k[1][0];
    c += texture(t, uv).rgb * k[1][1];
    c += texture(t, uv + texel * vec2(1.0, 0.0)).rgb * k[1][2];
    c += texture(t, uv + texel * vec2(-1.0, 1.0)).rgb * k[2][0];
    c += texture(t, uv + texel * vec2(0.0, 1.0)).rgb * k[2][1];
    c += texture(t, uv + texel * vec2(1.0, 1.0)).rgb * k[2][2];
    return c;
}

void mainImage(out vec4 fragColor, in vec2 fragCoord) {
    vec2 uv = fragCoord / iResolution.xy;
    vec2 texel = 1.0 / iResolution.xy;
    float sel = clamp(iParam0, 0.0, 1.0);
    mat3 k;
    float norm = 1.0;
    if(sel < 0.33){
        k = mat3(-2, -1, 0,
                 -1,  1, 1,
                  0,  1, 2);
        norm = 1.0;
    } else if(sel < 0.66){
        k = mat3(-1, 0, -1,
                  0, 5, 0,
                 -1, 0, -1);
        norm = 1.0;
    } else if(sel < 0.99){
        k = mat3(-1, -1, -1,
                 -1,  8, -1,
                 -1, -1, -1);
        norm = 1.0;
    } else {
        k = mat3(1,2,1,
                 2,4,2,
                 1,2,1);
        norm = 16.0;
    }
    vec3 col = sample9(iChannel0, uv, texel, k) / norm;
    float mixAmt = clamp(iParam1, 0.0, 1.0);
    vec3 base = texture(iChannel0, uv).rgb;
    fragColor = vec4(mix(base, col, mixAmt), 1.0);
}
