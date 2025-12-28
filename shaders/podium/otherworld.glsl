#define PSD (abs(texture(iChannel0, vec2(.5)).r)*abs(texture(iChannel0, vec2(.5)).r))

// HG_SDF rotate function
#define r(p, a) {p = cos(a)*p + sin(a)*vec2(p.y,-p.x);}

// Cabbibo's HSV
vec3 hsv(float h, float s, float v) {return mix( vec3( 1.0 ), clamp( ( abs( fract(h + vec3( 3.0, 2.0, 1.0 ) / 3.0 ) * 6.0 - 3.0 ) - 1.0 ), 0.0, 1.0 ), s ) * v;}

void mainImage( out vec4 c, in vec2 w )
{
	vec2 uv = (w - 0.5 * iResolution.xy) / iResolution.y;
    
    float intensity = clamp(iParam7, 0.0, 1.0);
    // iParam5 controls camera motion speed (0.1x to 2.0x)
    float speed = 0.1 + iParam5 * 1.9 * intensity;
    
    // Use feedback channel (iChannel1) to accumulate phase for smooth speed changes
    // This prevents camera position jumps when speed parameter changes
    // Store phase data in a corner pixel (normalized UV coordinates)
    vec2 phaseUV = vec2(0.5 / iResolution.xy);
    vec4 feedback = texture(iChannel1, phaseUV);
    float prevPhase = feedback.r;
    float prevTime = feedback.g;
    
    // Check if we're rendering the feedback storage pixel (bottom-left corner)
    vec2 fragCoordNorm = w / iResolution.xy;
    bool isFeedbackPixel = (fragCoordNorm.x < 0.001 && fragCoordNorm.y < 0.001);
    
    // Compute phase increment based on current speed and time delta
    // Use a small default delta if no previous time (first frame or no feedback)
    float timeDelta = (prevTime > 0.001) ? max(iTime - prevTime, 0.0) : 0.016;
    float phaseIncrement = speed * timeDelta;
    
    // Accumulate phase continuously to prevent jumps when speed changes
    // If no previous data, initialize from current time and speed
    float currentPhase = (prevTime > 0.001) ? prevPhase + phaseIncrement : iTime * speed;
    
    // Store current phase and time in feedback pixel
    if (isFeedbackPixel) {
        c = vec4(currentPhase, iTime, 0.0, 1.0);
        return;
    }
    
    // Use accumulated phase for smooth animation
    float T = currentPhase;
    
    // Use camera parameters for proper 3D navigation
    vec3 ro = iCameraPos;
    vec3 rd = normalize(uv.x * iCameraRight + uv.y * iCameraUp + iCameraForward);
    
    vec3 p;
    float d = 0., m; // Distance for march
    for (float i = 1.; i > 0.; i-=0.02)
    {
        p = ro + rd * d;
        r(p.zy, T);
        r(p.zx, T);
        m = length(cos(abs(p)+sin(abs(p))+T))-(PSD + .5); // Distance function
        d += m;
        c = vec4(hsv(T, 1.,1.)*i*i, 1.);
        if (m < 0.02) break;
    }
    
}