/**************************************************************************/
/*  display_server_offscreen.cpp                                          */
/**************************************************************************/
/*                         This file is part of:                          */
/*                             GODOT ENGINE                               */
/*                        https://godotengine.org                         */
/**************************************************************************/
/* Copyright (c) 2014-present Godot Engine contributors (see AUTHORS.md). */
/* Copyright (c) 2007-2014 Juan Linietsky, Ariel Manzur.                  */
/*                                                                        */
/* Permission is hereby granted, free of charge, to any person obtaining  */
/* a copy of this software and associated documentation files (the        */
/* "Software"), to deal in the Software without restriction, including    */
/* without limitation the rights to use, copy, modify, merge, publish,    */
/* distribute, sublicense, and/or sell copies of the Software, and to     */
/* permit persons to whom the Software is furnished to do so, subject to  */
/* the following conditions:                                              */
/*                                                                        */
/* The above copyright notice and this permission notice shall be         */
/* included in all copies or substantial portions of the Software.        */
/*                                                                        */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,        */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF     */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY   */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,   */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE      */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                 */
/**************************************************************************/

#include "display_server_offscreen.h"

#ifdef VULKAN_ENABLED
#include "drivers/vulkan/rendering_context_driver_vulkan.h"
#endif

#include "servers/rendering/renderer_rd/renderer_compositor_rd.h"
#include "servers/rendering/rendering_device.h"

Vector<String> DisplayServerOffscreen::get_rendering_drivers_func() {
	Vector<String> drivers;
	drivers.push_back("vulkan");
	return drivers;
}

DisplayServer *DisplayServerOffscreen::create_func(const String &p_rendering_driver, DisplayServerEnums::WindowMode p_mode, DisplayServerEnums::VSyncMode p_vsync_mode, uint32_t p_flags, const Vector2i *p_position, const Vector2i &p_resolution, int p_screen, DisplayServerEnums::Context p_context, int64_t p_parent_window, Error &r_error) {
	r_error = ERR_UNAVAILABLE;
#ifdef VULKAN_ENABLED
	if (p_rendering_driver != "vulkan") {
		return nullptr;
	}
	DisplayServerOffscreen *server = memnew(DisplayServerOffscreen());
	if (server->_initialize_rendering() != OK) {
		memdelete(server);
		r_error = ERR_CANT_CREATE;
		return nullptr;
	}
	r_error = OK;
	return server;
#else
	return nullptr;
#endif
}

Error DisplayServerOffscreen::_initialize_rendering() {
#ifdef VULKAN_ENABLED
	context = memnew(RenderingContextDriverVulkan);
	if (context->initialize() != OK) {
		memdelete(context);
		context = nullptr;
		ERR_FAIL_V_MSG(ERR_CANT_CREATE, "Offscreen: no Vulkan device is available.");
	}

	// No window means no surface and no swap chain. Every viewport renders into
	// its own texture, which is what a screenshot reads back.
	device = memnew(RenderingDevice);
	if (device->initialize(context, DisplayServerEnums::INVALID_WINDOW_ID) != OK) {
		memdelete(device);
		device = nullptr;
		memdelete(context);
		context = nullptr;
		ERR_FAIL_V_MSG(ERR_CANT_CREATE, "Offscreen: could not create a rendering device without a surface.");
	}
	RendererCompositorRD::make_current();
	return OK;
#else
	ERR_FAIL_V_MSG(ERR_UNAVAILABLE, "Offscreen: this build has no Vulkan support.");
#endif
}

DisplayServerOffscreen::DisplayServerOffscreen() {
}

DisplayServerOffscreen::~DisplayServerOffscreen() {
	if (device) {
		memdelete(device);
		device = nullptr;
	}
	if (context) {
		memdelete(context);
		context = nullptr;
	}
}
