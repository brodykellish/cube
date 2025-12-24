//based on shader from coyote => https://www.shadertoy.com/view/ltfGzS

// matrix op
mat3 getRotYMat(float a){return mat3(cos(a),0.,sin(a),0.,1.,0.,-sin(a),0.,cos(a));}
//mat3 getRotZMat(float a){return mat3(cos(a),-sin(a),0.,sin(a),cos(a),0.,0.,0.,1.);}
void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    vec2 s = iResolution.xy;
    vec2 uv = (fragCoord - 0.5 * s) / s.y;
    float t = iTime * 0.2;
    float c, d, m;
    
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    vec3 p = rd;
    vec3 r = vec3(0.);
    vec3 q = vec3(10. + cos(t) * 3., 0., 10. + sin(t) * 3.);
    //p*=getRotZMat(-t);
    p *= getRotYMat(-t);
    
    for (float i = 1.; i > 0.; i -= .01) {
        c = 0.0;
        d = 0.0;
        m = 1.;
        for (int j = 0; j < 3; j++) {
            r = max(r *= r *= r *= r = mod(q * m + 1., 2.) - 1., r.yzx);
            d = max(d, (.29 - length(r) * .6) / m) * .8;
            m *= 1.1;
        }

        q += p * d;
        
        c = i;
	    
        if(d < 1e-5) break;
    }
    
    float k = dot(r, r + .15);
    fragColor.rgb = vec3(1., k, k / c) - .8;
    fragColor.a = 1.0;
}