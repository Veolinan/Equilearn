# modules/ui/scroll.py
"""
ScrollHandler — fist-drag gesture shifts the UI zone vertically.

Usage
─────
  handler = ScrollHandler()

  # In your frame loop:
  handler.update(gf)          # pass latest GestureFrame each frame

  # The handler calls L.scroll(delta) automatically.
  # Draw the scroll indicator by calling:
  handler.draw(screen)
"""
import pygame, math, time
from modules.ui.layout import L
from modules.gesture_engine import GestureFrame, GestureState


class ScrollHandler:
    DRAG_SCALE  = 1.8   # how many screen pixels to scroll per wrist-pixel moved
    SNAP_BACK   = False # True = auto-return to centre when fist released
    INDICATOR_W = 6     # width of scroll indicator bar

    def __init__(self):
        self._fist_prev_y  = None   # wrist_y when fist was first detected
        self._dragging     = False
        self._last_delta   = 0
        self._indicator_alpha = 0   # fades in when scrolled

    def update(self, gf: GestureFrame):
        """Call every frame. Mutates L._scroll_offset directly."""
        if gf.is_fist and gf.hand_visible:
            if not self._dragging:
                # Start drag
                self._dragging    = True
                self._fist_prev_y = gf.wrist_y
            else:
                # Continue drag — delta wrist movement → scroll
                delta = int((gf.wrist_y - self._fist_prev_y) * self.DRAG_SCALE)
                if delta != 0:
                    L.scroll(delta)
                    self._last_delta   = delta
                    self._fist_prev_y  = gf.wrist_y
                    self._indicator_alpha = min(255, self._indicator_alpha + 40)
        else:
            self._dragging    = False
            self._fist_prev_y = None
            # Fade out indicator
            self._indicator_alpha = max(0, self._indicator_alpha - 8)

        if self.SNAP_BACK and not self._dragging:
            # Gently return to centre
            L._scroll_offset = int(L._scroll_offset * 0.88)

    def draw(self, screen: pygame.Surface):
        """Draw a subtle scroll position indicator on the right edge."""
        if self._indicator_alpha <= 0 and L._scroll_offset == 0:
            return

        alpha = max(self._indicator_alpha,
                    min(160, abs(L._scroll_offset) * 3))
        if alpha <= 0:
            return

        # Track (full height, right edge)
        track_x = L.sw - self.INDICATOR_W - 4
        track_y = L.margin_y
        track_h = L.sh - L.margin_y * 2

        # Track background
        surf = pygame.Surface((self.INDICATOR_W, track_h), pygame.SRCALPHA)
        pygame.draw.rect(surf, (255, 255, 255, 20),
                         surf.get_rect(), border_radius=self.INDICATOR_W // 2)
        screen.blit(surf, (track_x, track_y))

        # Thumb position (where UI zone is relative to track)
        limit   = int(L.sh * 0.25)
        frac    = (L._scroll_offset + limit) / (2 * limit) if limit > 0 else 0.5
        frac    = max(0.0, min(1.0, frac))
        thumb_h = max(24, track_h // 4)
        thumb_y = track_y + int((track_h - thumb_h) * frac)

        thumb_surf = pygame.Surface((self.INDICATOR_W, thumb_h), pygame.SRCALPHA)
        pygame.draw.rect(thumb_surf, (120, 200, 255, int(alpha)),
                         thumb_surf.get_rect(),
                         border_radius=self.INDICATOR_W // 2)
        screen.blit(thumb_surf, (track_x, thumb_y))

        # "Fist to scroll" hint — only while dragging
        if self._dragging:
            font = pygame.font.Font(None, 22)
            hint = font.render("✊ dragging", True, (120, 200, 255))
            hint.set_alpha(180)
            screen.blit(hint, (track_x - hint.get_width() - 8,
                                track_y + track_h + 4))
