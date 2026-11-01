# Headless

What works without a display, what does not, and why.

## Input works

The headless display server keeps a window size (default 640x360, following
`window_set_size`) and reports it for the window and the screen. The root Window
maps input through that size, so with it in place GUI hover and clicks work:

```gdscript
var event := InputEventMouseMotion.new()
event.position = button.get_global_rect().get_center()
Input.parse_input_event(event)          # gui_get_hovered_control() now answers
```

Control rects are canvas coordinates. Input events travel in window pixels and
the viewport scales them by its final transform, so multiply by
`get_viewport().get_final_transform()` before sending, or a non-1.0 content
scale puts every click in the wrong place.

## Rendering does not

`--headless` installs `RasterizerDummy` in `Main::setup()` and the headless
display server never creates a rendering context. `get_viewport().get_texture()
.get_image()` therefore returns null: there are no pixels to read.

`bin/gai shot` renders anyway by starting its own Xvfb on a free display,
running the engine there, capturing PNGs and stopping the server again. `$DISPLAY`
is used when it points at a live socket. `bin/gai doctor` says which of the two
applies.

## What native offscreen rendering would take

The renderer choice belongs to the display server, not to a flag, so this is a
new display server rather than a switch:

1. `DisplayServerOffscreen` with the window and input surface of the headless
   one, plus a rendering context. X11 does the equivalent in
   `display_server_x11.cpp`.
2. A context driver that creates a Vulkan instance and device without a surface.
   `RenderingContextDriverVulkan` already separates that work from the surface;
   only the X11 subclass creates one.
3. No swapchain: `RendererCompositorRD::blit_render_targets_to_screen` requires
   one, and it is only reached when a viewport is attached to a screen. A window
   that is never attached renders into its own texture, which is what
   `get_image()` reads.
4. `lavapipe` (Mesa's software Vulkan) makes the result testable on a machine
   with no GPU; it is present here as `lvp_icd.json`.

Until that exists, `gai shot` is the supported way to look at a frame, and the
Xvfb dependency is gai's to manage rather than the caller's.
