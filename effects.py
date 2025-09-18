import cv2
import numpy as np

class VideoEffect:
    """Base class for all video effects."""
    def __init__(self, name):
        self.name = name

    def apply(self, frame):
        """Applies the effect to a single frame. This method should be overridden by subclasses."""
        raise NotImplementedError

class NoEffect(VideoEffect):
    def __init__(self):
        super().__init__("No Effect")

    def apply(self, frame):
        return frame

class Rotate180(VideoEffect):
    def __init__(self):
        super().__init__("Rotate 180°")

    def apply(self, frame):
        return cv2.rotate(frame, cv2.ROTATE_180)

class ChromaticAberration(VideoEffect):
    def __init__(self):
        super().__init__("Chromatic Aberration")
        self.jitter_amount = 20

    def apply(self, frame):
        b, g, r = cv2.split(frame)
        
        x_shift_r, y_shift_r = np.random.randint(-self.jitter_amount, self.jitter_amount + 1, 2)
        x_shift_b, y_shift_b = np.random.randint(-self.jitter_amount, self.jitter_amount + 1, 2)

        rows, cols = frame.shape[:2]
        
        M_r = np.float32([[1, 0, x_shift_r], [0, 1, y_shift_r]])
        M_b = np.float32([[1, 0, x_shift_b], [0, 1, y_shift_b]])

        r_shifted = cv2.warpAffine(r, M_r, (cols, rows))
        b_shifted = cv2.warpAffine(b, M_b, (cols, rows))

        return cv2.merge([b_shifted, g, r_shifted])

class HueShift(VideoEffect):
    def __init__(self):
        super().__init__("Hue Shift")
        self.hue_shift = 0

    def apply(self, frame):
        hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        
        self.hue_shift = (self.hue_shift + 3) % 180
        h = cv2.add(h, self.hue_shift)
        h[h > 179] -= 180
        
        final_hsv = cv2.merge([h, s, v])
        # Corrected typo from COLOR_HSV_BGR to COLOR_HSV2BGR
        return cv2.cvtColor(final_hsv, cv2.COLOR_HSV2BGR)

class WaveWarp(VideoEffect):
    def __init__(self):
        super().__init__("Wave Warp")
        self.frame_count = 0

    def apply(self, frame):
        rows, cols = frame.shape[:2]
        map_x, map_y = np.meshgrid(np.arange(cols), np.arange(rows))
        
        amplitude = 40
        frequency = 0.02
        
        offset = np.sin(map_y * frequency + self.frame_count * 0.1) * amplitude
        map_x = map_x.astype(np.float32) + offset.astype(np.float32)
        map_y = map_y.astype(np.float32)
        
        self.frame_count += 1
        return cv2.remap(frame, map_x, map_y, interpolation=cv2.INTER_LINEAR)

class Kaleidoscope(VideoEffect):
    def __init__(self):
        super().__init__("Kaleidoscope")

    def apply(self, frame):
        h, w = frame.shape[:2]
        center_x, center_y = w // 2, h // 2
        
        quadrant = frame[0:center_y, 0:center_x]
        
        top_right = cv2.flip(quadrant, 1)
        bottom_left = cv2.flip(quadrant, 0)
        bottom_right = cv2.flip(quadrant, -1)
        
        top_half = np.hstack([quadrant, top_right])
        bottom_half = np.hstack([bottom_left, bottom_right])
        
        return np.vstack([top_half, bottom_half])

class GlitchLines(VideoEffect):
    def __init__(self):
        super().__init__("Glitch Lines")

    def apply(self, frame):
        h, w = frame.shape[:2]
        glitched_frame = frame.copy()
        
        for _ in range(np.random.randint(5, 15)):
            line_y = np.random.randint(0, h)
            line_height = np.random.randint(5, 25)
            shift = np.random.randint(-100, 100)
            
            if line_y + line_height > h:
                line_height = h - line_y
                
            line = glitched_frame[line_y:line_y + line_height, :]
            glitched_frame[line_y:line_y + line_height, :] = np.roll(line, shift, axis=1)
            
        return glitched_frame

class Strobe(VideoEffect):
    def __init__(self):
        super().__init__("Strobe")
        self.on = True

    def apply(self, frame):
        self.on = not self.on
        if self.on:
            return frame
        else:
            return np.zeros_like(frame)

class FractalZoom(VideoEffect):
    def __init__(self):
        super().__init__("Fractal Zoom")

    def apply(self, frame):
        h, w = frame.shape[:2]
        
        # Choose a random pronounced zoom factor each frame
        zoom_factor = np.random.uniform(1.2, 2.5)
        
        # Jitter the zoom center for a more chaotic effect
        center_x = w // 2 + np.random.randint(-w // 8, w // 8)
        center_y = h // 2 + np.random.randint(-h // 8, h // 8)
        
        crop_w = int(w / zoom_factor)
        crop_h = int(h / zoom_factor)
        
        x1 = center_x - crop_w // 2
        y1 = center_y - crop_h // 2
        
        # Ensure the crop coordinates are within the frame boundaries
        x1 = np.clip(x1, 0, w - crop_w)
        y1 = np.clip(y1, 0, h - crop_h)
        
        # Ensure the cropped dimensions are valid
        if crop_w > 0 and crop_h > 0:
            cropped = frame[y1:y1 + crop_h, x1:x1 + crop_w]
            return cv2.resize(cropped, (w, h), interpolation=cv2.INTER_LINEAR)
        else:
            return frame

class Bloom(VideoEffect):
    def __init__(self):
        super().__init__("Bloom")

    def apply(self, frame):
        blurred = cv2.GaussianBlur(frame, (0, 0), sigmaX=30)
        return cv2.addWeighted(frame, 1.0, blurred, 0.7, 0)

class Negative(VideoEffect):
    def __init__(self):
        super().__init__("Negative")

    def apply(self, frame):
        return cv2.bitwise_not(frame)

