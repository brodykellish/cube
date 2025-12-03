// https://www.shadertoy.com/view/tcSfRc
#define T (iTime)

vec4 blood(vec2 u, vec3 camPos) {
    float i=0.,a=0.,d=0.,s=0.,t=.4*iTime;
    vec3  p;
    vec4 o = vec4(0);

    // Add camera influence to the effect
    float camInfluence = length(camPos) * 0.1;

    for(o*=i; i++<64.;
        d += s = .01 + abs(s) * .4,
        o.r+=d/s)
        for (p = vec3(u * d, d + t) + camPos * 0.2,  // Offset by camera position
            s = min(cos(p.z), 6. - length(p.xy)),
            a = .8; a < 16.; a += a)
            p += cos(t+p.yzx)*.2,
            s += abs(dot(sin(t+.2*p.z+p * a + camInfluence), .6+p-p)) / a;
    return o * 2e1;
}

vec4 fire(vec2 u, vec3 camPos) {
    float i=0., d=0., s=0., n=0.;
    vec3 p;
    vec4 o = vec4(0);

    // Camera influence on fire movement
    float camTwist = dot(camPos, vec3(0.1, 0.2, 0.3));

    for(; i++<1e2; ) {
        p = vec3(u * d, d) + camPos * 0.15;  // Offset by camera position
        p += cos(p.z+T+p.yzx*.5 + camTwist)*.6;
        s = 6.-length(p.xy);
        p.xy *= mat2(cos(.3*T+camTwist*0.5+vec4(0,33,11,0)));
        for (n = 1.6; n < 32.; n += n )
            s -= abs(dot(sin( p.z + T + p*n ), vec3(1.12))) / n;
        d += s = .01 + abs(s)*.1;
        o += 1. / s;
    }
    return (vec4(5,2,1,1) * o * o / d);
}

void mainImage(out vec4 o, in vec2 u) {
    float s=.1,d=0.,i=0.;
    vec3  p = iResolution;
    u = (u-p.xy/2.)/p.y;

    // Transform UV based on camera orientation
    vec2 camUV = u;
    camUV += iCameraPos.xy * 0.05;  // Shift based on camera X/Y
    camUV *= 1.0 + length(iCameraPos) * 0.02;  // Scale based on camera distance

    o = mix(fire(camUV, iCameraPos), blood(camUV, iCameraPos), .9);
    o = tanh(o  / 5e5 );

    // Add subtle pulsing based on camera Z position
    o *= 1.0 + sin(iCameraPos.z * 0.5 + iTime) * 0.1;
}
