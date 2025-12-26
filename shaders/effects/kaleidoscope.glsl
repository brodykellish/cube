// Kaleidoscope effect
// iChannel0: source frame
// iParam0: zoom/scale (0..1 -> 1.0..15.0)
// iParam1: rotation speed (0..1 -> 0.0..0.5)
// iParam2: iteration count (0..1 -> 4..64)
// iParam3: offset amount (0..1 -> 0.0..0.5)
void mainImage( out vec4 fragColor, in vec2 fragCoord )
{
	float intensity = clamp(iParam7, 0.0, 1.0);
	if (intensity < 0.001) {
		vec2 uv = fragCoord / iResolution.xy;
		fragColor = texture(iChannel0, uv);
		return;
	}
	float zoom = mix(1.0, 15.0, clamp(iParam0, 0.0, 1.0) * intensity);
	vec2 uv = (fragCoord.xy-.5*iResolution.xy) * zoom / iResolution.y;

    float r = 1.0;
    float rotSpeed = mix(0.0, 0.5, clamp(iParam1, 0.0, 1.0) * intensity);
    float a = iTime * rotSpeed;
    float c = cos(a)*r;
    float s = sin(a)*r;
    
    int iterations = int(mix(4.0, 64.0, clamp(iParam2, 0.0, 1.0) * intensity));
    float offset = mix(0.0, 0.5, clamp(iParam3, 0.0, 1.0) * intensity);
    
    for ( int i=0; i<64; i++ )
    {
    	if (i < iterations) {
    		uv = abs(uv);
    		uv -= offset;
    		uv = uv*c + s*uv.yx*vec2(1,-1);
    	}
    }
        
    fragColor = texture( iChannel0, uv*vec2(1,-1)+.5 );
}