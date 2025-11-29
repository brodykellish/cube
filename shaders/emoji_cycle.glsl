// Emoji Cycle - Animated emoji that cycles between happy and sad states
// Features:
// - Circular face with animated expression
// - Happy state: Smiling mouth (upward curve)
// - Sad state: Frowning mouth (downward curve) with falling tear
// - Smooth transitions using iTime
// - Interactive camera navigation with iCameraPos, iCameraRight, iCameraUp, iCameraForward

// SDF for circle
float sdCircle(vec2 p, float r) {
    return length(p) - r;
}

// SDF for line segment
float sdSegment(vec2 p, vec2 a, vec2 b, float thickness) {
    vec2 pa = p - a;
    vec2 ba = b - a;
    float h = clamp(dot(pa, ba) / dot(ba, ba), 0.0, 1.0);
    return length(pa - ba * h) - thickness;
}

// Smooth minimum for blending shapes
float smin(float a, float b, float k) {
    float h = clamp(0.5 + 0.5 * (b - a) / k, 0.0, 1.0);
    return mix(b, a, h) - k * h * (1.0 - h);
}

// Create a smile curve using multiple segments
float sdSmile(vec2 p, float curvature, float width) {
    float d = 1e10;
    int segments = 10;

    for (int i = 0; i < segments; i++) {
        float t1 = float(i) / float(segments);
        float t2 = float(i + 1) / float(segments);

        // Map to -1 to 1 range
        float x1 = (t1 - 0.5) * 2.0 * width;
        float x2 = (t2 - 0.5) * 2.0 * width;

        // Apply curvature (positive = smile, negative = frown)
        float y1 = curvature * (1.0 - 4.0 * (t1 - 0.5) * (t1 - 0.5));
        float y2 = curvature * (1.0 - 4.0 * (t2 - 0.5) * (t2 - 0.5));

        vec2 a = vec2(x1, y1);
        vec2 b = vec2(x2, y2);

        d = min(d, sdSegment(p, a, b, 0.05));  // Increased thickness from 0.02
    }

    return d;
}

void mainImage(out vec4 fragColor, vec2 fragCoord) {
    // Normalize coordinates to -1 to 1
    vec2 uv = (fragCoord - 0.5 * iResolution.xy) / min(iResolution.x, iResolution.y);

    // Cycle parameters
    float cycle = 7.0; // Total cycle duration in seconds
    float t = mod(iTime, cycle) / cycle; // 0-1 over the cycle

    // State transitions: 0-0.45 happy, 0.45-0.55 transition, 0.55-1.0 sad
    float happyAmount = smoothstep(0.55, 0.45, t);
    float sadAmount = smoothstep(0.45, 0.55, t);

    // Face position and size - small enough to avoid any clipping
    vec2 faceCenter = vec2(0.0, 0.0);  // Centered on screen
    float faceRadius = 0.42;  // Small enough to fit with margin for mouth extending down

    // Background color - changes with emotion (darker for better contrast)
    vec3 bgColor = mix(
        vec3(0.0, 0.0, 0.1),  // Very dark blue for sad
        vec3(0.1, 0.05, 0.0),  // Very dark warm for happy
        happyAmount
    );

    // Start with background
    vec3 col = bgColor;

    // Draw face (bright yellow circle)
    float faceDist = sdCircle(uv - faceCenter, faceRadius);
    vec3 faceColor = mix(
        vec3(1.0, 1.0, 0.0),  // Vivid yellow for happy
        vec3(1.0, 0.9, 0.0),  // Bright yellow for sad
        sadAmount
    );

    if (faceDist < 0.0) {
        col = faceColor;

        // Add slight shading for depth
        float shade = 1.0 - smoothstep(-0.02, 0.0, faceDist);
        col *= 0.9 + 0.1 * shade;
    }

    // Add face outline (proportional to face size)
    if (abs(faceDist) < 0.022) {  // Scaled for smaller face
        col = vec3(0.1, 0.08, 0.0);
    }

    // Eyes - scaled to smaller face
    float eyeY = 0.11;
    float eyeSpacing = 0.15;
    vec2 leftEye = faceCenter + vec2(-eyeSpacing, eyeY);
    vec2 rightEye = faceCenter + vec2(eyeSpacing, eyeY);
    float eyeRadius = 0.06;

    // Draw left eye
    float leftEyeDist = sdCircle(uv - leftEye, eyeRadius);
    if (leftEyeDist < 0.0) {
        col = vec3(0.0); // Black eyes
    }

    // Draw right eye
    float rightEyeDist = sdCircle(uv - rightEye, eyeRadius);
    if (rightEyeDist < 0.0) {
        col = vec3(0.0); // Black eyes
    }

    // Pupils that look mostly side to side with limited vertical movement
    // Use simple pseudo-random movement based on time
    float lookTime = iTime * 0.35;  // Increased speed for more motion
    float lookChangeTime = floor(lookTime);  // Changes every ~3 seconds

    // Pseudo-random values using sine (favor horizontal movement)
    float randomX = sin(lookChangeTime * 12.9898);  // Full range horizontal
    float randomY = cos(lookChangeTime * 78.233) * 0.35;  // Slightly more vertical movement

    // Smooth transition between look directions
    float lookBlend = fract(lookTime);
    lookBlend = smoothstep(0.0, 0.3, lookBlend) * (1.0 - smoothstep(0.7, 1.0, lookBlend));

    float pupilRadius = eyeRadius * 0.4;

    // Maximum distance pupil can move from center (eye radius minus pupil radius minus small margin)
    float maxPupilOffset = eyeRadius - pupilRadius - 0.008;

    // Calculate pupil offset with more range
    vec2 lookDir = vec2(randomX, randomY) * lookBlend * maxPupilOffset * 0.8;  // Increased from 0.6 to 0.8
    // Further constrain to ensure it stays well within the eye
    float lookDirLength = length(lookDir);
    if (lookDirLength > maxPupilOffset) {
        lookDir = lookDir * (maxPupilOffset / lookDirLength);
    }

    // Left pupil
    vec2 leftPupilPos = leftEye + lookDir;
    float leftPupilDist = sdCircle(uv - leftPupilPos, pupilRadius);
    if (leftPupilDist < 0.0 && leftEyeDist < 0.0) {
        col = vec3(0.15, 0.3, 0.6); // Dark blue pupils
    }

    // Right pupil
    vec2 rightPupilPos = rightEye + lookDir;
    float rightPupilDist = sdCircle(uv - rightPupilPos, pupilRadius);
    if (rightPupilDist < 0.0 && rightEyeDist < 0.0) {
        col = vec3(0.15, 0.3, 0.6); // Dark blue pupils
    }

    // Add white highlights to pupils for more life
    float highlightSize = pupilRadius * 0.4;
    vec2 highlightOffset = vec2(-0.009, 0.009);  // Scaled for smaller pupils

    float leftHighlight = sdCircle(uv - leftPupilPos - highlightOffset, highlightSize);
    if (leftHighlight < 0.0 && leftPupilDist < 0.0) {
        col = vec3(1.0); // White highlight
    }

    float rightHighlight = sdCircle(uv - rightPupilPos - highlightOffset, highlightSize);
    if (rightHighlight < 0.0 && rightPupilDist < 0.0) {
        col = vec3(1.0); // White highlight
    }

    // Mouth - blend between smile and frown (scaled to smaller face)
    vec2 mouthPos = faceCenter + vec2(0.0, -0.17);
    float smileCurve = mix(-0.12, 0.14, happyAmount); // Negative = frown, positive = smile
    float mouthDist = sdSmile(uv - mouthPos, smileCurve, 0.21);  // Mouth width

    if (mouthDist < 0.0) {
        col = vec3(0.0); // Black mouth
    }

    // Tear drop (only visible in sad state) - scaled up
    if (sadAmount > 0.1) {
        // Tear animation only during sad phase
        // Calculate time within the sad phase (starts at t=0.55, ends at t=1.0)
        float sadPhaseStart = 0.55;
        float sadPhaseDuration = 0.45; // 45% of cycle
        float timeInSadPhase = max(0.0, t - sadPhaseStart) / sadPhaseDuration;

        // Tear falls over ~2 seconds, repeats during sad phase
        float tearCycle = mod(timeInSadPhase * cycle, 2.5); // Tear cycle duration
        float tearFall = smoothstep(0.0, 1.0, tearCycle / 2.5) * 0.45;  // Scaled for smaller face

        vec2 tearPos = leftEye + vec2(0.045, -0.09 - tearFall);  // Scaled for smaller face
        float tearSize = 0.03 * (1.0 - tearFall * 0.3); // Scaled for smaller face

        float tearDist = sdCircle(uv - tearPos, tearSize);

        // Add teardrop shape (elongate vertically)
        vec2 tearUV = uv - tearPos;
        tearDist = min(tearDist, length(vec2(tearUV.x, tearUV.y * 1.5)) - tearSize);

        if (tearDist < 0.0) {
            // Bright blue tear
            vec3 tearColor = vec3(0.3, 0.7, 1.0);  // Brighter cyan-blue
            col = mix(col, tearColor, 0.8 * sadAmount);
        }

        // Tear highlight (scaled for smaller tear)
        vec2 tearHighlightPos = tearPos + vec2(-0.008, 0.008);  // Scaled for smaller face
        float tearHighlightDist = sdCircle(uv - tearHighlightPos, tearSize * 0.35);
        if (tearHighlightDist < 0.0) {
            col = mix(col, vec3(1.0, 1.0, 1.0), 0.7 * sadAmount);  // Brighter highlight
        }
    }

    // Reduce vignette for brighter overall image
    float vignette = 1.0 - length(uv) * 0.15;  // Reduced from 0.3
    col *= vignette;

    // Brighten significantly for LED display
    col = pow(col, vec3(0.7));  // Increased from 0.8
    col *= 1.5;  // Increased from 1.2
    col = clamp(col, 0.0, 1.0);

    fragColor = vec4(col, 1.0);
}
