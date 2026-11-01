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

## Rendering works, through the offscreen display server

`--headless` still installs `RasterizerDummy` in `Main::setup()` and never
creates a rendering context: under plain `--headless`,
`get_viewport().get_texture().get_image()` returns null.

`--display-driver offscreen --rendering-driver vulkan` is the renderer without a
window. It creates a Vulkan device with no surface and no swap chain, so the
root viewport never attaches to a screen and every viewport renders into its own
texture, which is exactly what a screenshot reads. On a machine with no GPU,
Mesa's `lavapipe` (`lvp_icd.json`) provides the device.

`bin/gai shot` tries this first and prints `shot: rendered with offscreen`. When
the engine has no offscreen driver it falls back to a private Xvfb on a free
display, which it starts and stops itself. `bin/gai doctor` reports both.

## How the offscreen display server is built

The renderer choice belongs to the display server, so this is a display server
rather than a switch:

1. `DisplayServerOffscreen` extends the headless one, so it inherits the window
   size, the input dispatch and every window stub. It adds a rendering context.
2. The context is `RenderingContextDriverVulkan` itself. It already separates
   instance and device creation from surfaces; only the X11 subclass creates
   one, and the base class builds a device without it.
3. `RenderingDevice::initialize(context, INVALID_WINDOW_ID)` skips the surface
   lookup. With no main window the device is not the main instance, so no swap
   chain is created.
4. `RenderingDevice::screen_prepare_for_drawing` stays quiet for that case:
   there is nothing to present, and the frame is already in its texture.

`gai shot` renders through it with no display at all; Xvfb is only a fallback for
an engine that predates the driver.
