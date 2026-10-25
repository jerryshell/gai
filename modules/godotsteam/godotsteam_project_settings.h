/***************************************************************************/
/*  godotsteam_project_settings.h                                          */
/***************************************************************************/
/*                         This file is part of:                           */
/*                              GODOTSTEAM                                 */
/*                         https://godotsteam.com                          */
/***************************************************************************/
/* Copyright (c) 2015-Current | GP Garcia, Chris Ridenour,                 */
/*                              and Contributors                           */
/*                                                                         */
/* View all contributors at https://godotsteam.com/contribute/contributors */
/*                                                                         */
/* Permission is hereby granted, free of charge, to any person obtaining   */
/* a copy of this software and associated documentation files (the         */
/* "Software"), to deal in the Software without restriction, including     */
/* without limitation the rights to use, copy, modify, merge, publish,     */
/* distribute, sublicense, and/or sell copies of the Software, and to      */
/* permit persons to whom the Software is furnished to do so, subject to   */
/* the following conditions:                                               */
/*                                                                         */
/* The above copyright notice and this permission notice shall be included */
/* in all copies or substantial portions of the Software.                  */
/*                                                                         */
/* THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,         */
/* EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF      */
/* MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.  */
/* IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY    */
/* CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,    */
/* TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE       */
/* SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.                  */
/***************************************************************************/

#pragma once

#ifdef GDEXTENSION
#include <godot_cpp/classes/object.hpp>
#include <godot_cpp/classes/project_settings.hpp>
#include <godot_cpp/core/class_db.hpp>

using namespace godot;
#else
#include "core/config/project_settings.h"
#include "core/object/class_db.h"
#include "core/object/object.h"
#endif


class SteamProjectSettings : public Object {
	GDCLASS(SteamProjectSettings, Object);


public:
	static SteamProjectSettings *get_singleton(){ return singleton; };
	SteamProjectSettings();
	~SteamProjectSettings();

	int get_app_id();
	int get_app_type();
	bool get_auto_init();
	int get_demo_id();
	bool get_embed_callbacks();
	bool get_enable_debug();
	int get_id_in_use();
	int get_max_channels();
	int get_playtest_id();
	int get_tool_id();
	void set_app_id(int new_app_id);
	void set_app_type(int new_app_type);
	void set_demo_id(int new_demo_id);
	void set_enable_debug(bool is_debug_enabled);
	void set_max_channels(int new_max_channels);
	void set_playtest_id(int new_playtest_id);
	void set_tool_id(int new_tool_id);

	void register_settings();


	int app_id;
	int app_type;
	bool auto_init;
	int demo_id;
	bool embed_callbacks;
	bool enable_debug;
	int id_in_use;
	int max_channels;
	int playtest_id;
	int tool_id;


protected:
	static void _bind_methods();
	static SteamProjectSettings *singleton;
};
