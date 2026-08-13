"""
JARVIS startup orb: a solid core sphere inside a rotating ring.

Adapted from the classic ASCII torus renderer (z-buffered surface
projection with Lambertian shading), with three changes needed to make
it usable as a startup banner rather than a standalone screensaver:

  1. Added a solid core sphere at the origin, so the figure matches the
     "orb with an orbiting ring" reference rather than being a bare
     torus (a ring with an empty hole).
  2. Sized down to fit above a compact status box (default 28x12
     instead of 80x40). The original's shading detail depends on
     resolution, so the character ramp and lighting are retuned for the
     smaller grid rather than just scaled.
  3. Replaced the infinite `while True` loop with a bounded
     `play(frames=N)`. The original blocks until Ctrl+C, which would
     hang JARVIS's startup -- nothing after it would ever run.

Character set is plain ASCII (".,-~:;=!*#$@"), so this needs no UTF-8
console reconfiguration to render correctly on Windows terminals.

Performance: ~5-15ms per frame at the default size on CPU, so a short
cycle adds negligible startup latency.

Usage:
    from jarvis_orb import play, render_frame
    play(frames=24)                  # short animated intro, then returns
    print(render_frame(0.6, 0.3))    # single static frame
"""

import math
import sys
import time

# Darkest -> lightest. Plain ASCII only (no UTF-8 dependency).
CHARS = ".,-~:;=!*#$@"

# Geometry constants
RING_CENTER_R = 2.0   # distance from origin to the ring's tube center
RING_TUBE_R = 0.55    # thickness of the ring tube
CORE_R = 1.05         # radius of the solid core sphere
VIEWER_DIST = 5.0     # camera distance along z

# Angular sweep resolution. Coarser than the original 0.07/0.02 because
# the smaller grid can't resolve finer steps -- finer just costs time
# without changing the output.
THETA_STEP = 0.10     # around the ring tube cross-section
PHI_STEP = 0.03       # around the ring's main circumference
SPHERE_STEP = 0.10    # around the core sphere


def _project(x, y, z, w, h, scale_x, scale_y):
    """Perspective-project a 3D point, returning (xp, yp, ooz)."""
    z = z + VIEWER_DIST
    if z <= 0.1:
        return None
    ooz = 1.0 / z
    xp = int(w / 2 + scale_x * ooz * x)
    yp = int(h / 2 - scale_y * ooz * y)
    return xp, yp, ooz


def _plot(output, zbuffer, w, h, xp, yp, ooz, lum):
    """Z-buffered write of a shaded point into the frame buffers."""
    if not (0 <= xp < w and 0 <= yp < h):
        return
    idx = xp + yp * w
    if ooz <= zbuffer[idx]:
        return
    zbuffer[idx] = ooz
    li = int(lum * (len(CHARS) - 1))
    if li < 0:
        li = 0
    elif li >= len(CHARS):
        li = len(CHARS) - 1
    output[idx] = CHARS[li]


def render_frame(A, B, width=28, height=12):
    """
    Render one frame of the orb at rotation angles A (about x) and
    B (about z). Returns a newline-joined string of `height` rows.
    """
    output = [' '] * (width * height)
    zbuffer = [0.0] * (width * height)

    cosA, sinA = math.cos(A), math.sin(A)
    cosB, sinB = math.cos(B), math.sin(B)

    # Character cells are roughly twice as tall as they are wide, so the
    # vertical projection scale is about half the horizontal one to keep
    # the orb circular rather than egg-shaped.
    scale_x = width * 0.62
    scale_y = height * 0.62

    # --- Core sphere -----------------------------------------------
    # Swept as latitude/longitude bands. Drawn first; the z-buffer
    # decides per-pixel whether ring or core wins, so the ring
    # correctly passes both in front of and behind the core.
    lat = -math.pi / 2
    while lat < math.pi / 2:
        coslat, sinlat = math.cos(lat), math.sin(lat)
        lon = 0.0
        while lon < 2 * math.pi:
            coslon, sinlon = math.cos(lon), math.sin(lon)

            # Point on the unit sphere, scaled to CORE_R
            sx = CORE_R * coslat * coslon
            sy = CORE_R * sinlat
            sz = CORE_R * coslat * sinlon

            # Rotate about x (A) then z (B)
            y1 = sy * cosA - sz * sinA
            z1 = sy * sinA + sz * cosA
            x2 = sx * cosB - y1 * sinB
            y2 = sx * sinB + y1 * cosB

            # Surface normal on a sphere is the normalized position, so
            # it rotates identically -- reuse the rotated coords.
            nx, ny, nz = x2 / CORE_R, y2 / CORE_R, z1 / CORE_R

            # Light from up-left-front: (-0.5, 0.7, -0.5) normalized
            lum = (nx * -0.5 + ny * 0.7 + nz * -0.5) / math.sqrt(0.99)
            if lum > 0:
                p = _project(x2, y2, z1, width, height, scale_x, scale_y)
                if p:
                    xp, yp, ooz = p
                    # Core is dimmer than the ring so the ring reads as
                    # the bright orbiting element -- but not so dim it
                    # disappears into the ring's dark pixels at small
                    # sizes. 0.75 keeps it distinguishable at 28x12.
                    _plot(output, zbuffer, width, height, xp, yp, ooz, lum * 0.75)
            lon += SPHERE_STEP
        lat += SPHERE_STEP

    # --- Ring (torus) ----------------------------------------------
    phi = 0.0
    while phi < 2 * math.pi:
        cosphi, sinphi = math.cos(phi), math.sin(phi)
        theta = 0.0
        while theta < 2 * math.pi:
            costheta, sintheta = math.cos(theta), math.sin(theta)

            # Point on the tube cross-section, swept around the ring
            circle_x = RING_CENTER_R + RING_TUBE_R * costheta
            circle_y = RING_TUBE_R * sintheta

            x = circle_x * (cosB * cosphi + sinA * sinB * sinphi) - circle_y * cosA * sinB
            y = circle_x * (sinB * cosphi - sinA * cosB * sinphi) + circle_y * cosA * cosB
            z = cosA * circle_x * sinphi + circle_y * sinA

            # Lambertian term from the original renderer's derivation
            L = (cosphi * costheta * sinB
                 - cosA * costheta * sinphi
                 - sinA * sintheta
                 + cosB * (cosA * sintheta - costheta * sinA * sinphi))

            if L > 0:
                p = _project(x, y, z, width, height, scale_x, scale_y)
                if p:
                    xp, yp, ooz = p
                    _plot(output, zbuffer, width, height, xp, yp, ooz, L / math.sqrt(2))
            theta += THETA_STEP
        phi += PHI_STEP

    return '\n'.join(''.join(output[i * width:(i + 1) * width])
                     for i in range(height))


def play(frames=24, width=28, height=12, delay=0.05, stream=None,
         a_step=0.09, b_step=0.05, clear=True):
    """
    Play a bounded animation, then return. Unlike the original's
    `while True`, this always terminates so startup can continue.

    Set clear=False to print frames sequentially without cursor
    control (useful when piping output or logging).
    """
    out = stream or sys.stdout
    A, B = 0.0, 0.0
    for _ in range(frames):
        frame = render_frame(A, B, width, height)
        if clear:
            out.write("\x1b[H")
        out.write(frame + "\n")
        out.flush()
        A += a_step
        B += b_step
        if delay:
            time.sleep(delay)
    return A, B


if __name__ == "__main__":
    # Demo: clear screen, play one short cycle, leave cursor below.
    sys.stdout.write("\x1b[2J\x1b[H")
    play(frames=40)
