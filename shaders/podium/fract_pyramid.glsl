// https://www.shadertoy.com/view/tsXBzS
// Fractal Pyramid with Camera Controls and MIDI Parameters
// Modified to respect camera parameters and use iParams for simulation control

vec3 palette(float d){
	return mix(vec3(0.2,0.7,0.9),vec3(1.,0.,1.),d);
}

vec2 rotate(vec2 p,float a){
	float c = cos(a);
    float s = sin(a);
    return p*mat2(c,s,-s,c);
}

float map(vec3 p){
    // iParam0 controls the number of fractal iterations (2-12)
    int iterations = int(2.0 + iParam0 * 10.0);
    
    // iParam1 controls time scale/speed (0.05 - 0.8)
    float timeScale = 0.05 + iParam1 * 0.75;
    
    // iParam2 controls rotation phase offset
    float phaseOffset = iParam2 * 6.28318; // 0 to 2*PI
    
    for( int i = 0; i < 12; ++i){
        if(i >= iterations) break;
        
        float t = iTime * timeScale + phaseOffset;
        p.xz = rotate(p.xz, t);
        p.xy = rotate(p.xy, t * 1.89);
        p.xz = abs(p.xz);
        p.xz -= 0.5;
	}
	return dot(sign(p),p)/5.;
}

vec4 rm (vec3 ro, vec3 rd){
    float t = 0.;
    vec3 col = vec3(0.);
    float d;
    
    // iParam3 controls color intensity/brightness (0.2 - 2.0)
    float colorIntensity = 0.2 + iParam3 * 1.8;
    
    for(float i = 0.; i < 64.; i++){
		vec3 p = ro + rd * t;
        d = map(p) * 0.5;
        if(d < 0.02){
            break;
        }
        if(d > 100.){
        	break;
        }
        // Apply color intensity parameter to the palette
        col += palette(length(p) * 0.1) * colorIntensity / (400.0 * d);
        t += d;
    }
    return vec4(col, 1.0 / (d * 100.0));
}

void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
    vec2 uv = (fragCoord - (iResolution.xy/2.0))/iResolution.x;
    
    // Use camera parameters to properly construct ray origin and direction
    vec3 ro = iCameraPos;
    vec3 rd = normalize(iCameraForward + uv.x * iCameraRight + uv.y * iCameraUp);
    
    vec4 col = rm(ro, rd);
    
    fragColor = col;
}