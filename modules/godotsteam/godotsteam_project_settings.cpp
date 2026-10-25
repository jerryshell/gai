/***************************************************************************/
/*  godotsteam_project_settings.cpp                                        */
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

#include "godotsteam_project_settings.h"

#define APP_TYPE_SETTING "steam/initialization/app_data/app_type"
#define APP_ID_SETTING "steam/initialization/app_data/app_id"
#define DEMO_ID_SETTING "steam/initialization/app_data/demo_id"
#define PLAYTEST_ID_SETTING "steam/initialization/app_data/playtest_id"
#define TOOL_ID_SETTING "steam/initialization/app_data/tool_id"
#define STARTUP_INIT_SETTING "steam/initialization/processes/initialize_on_startup"
#define EMBED_CALLBACKS_SETTING "steam/initialization/processes/embed_callbacks"
#define MAX_CHANNELS_SETTING "steam/multiplayer_peer/max_channels"
#define ENABLE_DEBUG_SETTING "steam/settings/enable_debug"

#define OLD_APP_ID_SETTING "steam/initialization/app_id"
#define OLD_STARTUP_INIT_SETTING "steam/initialization/initialize_on_startup"
#define OLD_EMBED_CALLBACKS_SETTING "steam/initialization/embed_callbacks"

#ifndef GLOBAL_GET
#define GLOBAL_GET(m_prop) ProjectSettings::get_singleton()->get_setting_with_override(m_prop)
#endif


SteamProjectSettings *SteamProjectSettings::singleton = nullptr;

SteamProjectSettings::SteamProjectSettings() {
	singleton = this;
}

SteamProjectSettings::~SteamProjectSettings() {
	singleton = nullptr;
}


void SteamProjectSettings::_bind_methods() {
	ClassDB::bind_method(D_METHOD("get_app_id"), &SteamProjectSettings::get_app_id);
	ClassDB::bind_method(D_METHOD("get_app_type"), &SteamProjectSettings::get_app_type);
	ClassDB::bind_method(D_METHOD("get_auto_init"), &SteamProjectSettings::get_auto_init);
	ClassDB::bind_method(D_METHOD("get_demo_id"), &SteamProjectSettings::get_demo_id);
	ClassDB::bind_method(D_METHOD("get_embed_callbacks"), &SteamProjectSettings::get_embed_callbacks);
	ClassDB::bind_method(D_METHOD("get_enable_debug"), &SteamProjectSettings::get_enable_debug);
	ClassDB::bind_method(D_METHOD("get_id_in_use"), &SteamProjectSettings::get_id_in_use);
	ClassDB::bind_method(D_METHOD("get_max_channels"), &SteamProjectSettings::get_max_channels);
	ClassDB::bind_method(D_METHOD("get_playtest_id"), &SteamProjectSettings::get_playtest_id);
	ClassDB::bind_method(D_METHOD("get_tool_id"), &SteamProjectSettings::get_tool_id);
	ClassDB::bind_method(D_METHOD("set_app_id", "new_app_id"), &SteamProjectSettings::set_app_id);
	ClassDB::bind_method(D_METHOD("set_app_type", "new_app_type"), &SteamProjectSettings::set_app_type);
	ClassDB::bind_method(D_METHOD("set_demo_id", "new_demo_id"), &SteamProjectSettings::set_demo_id);
	ClassDB::bind_method(D_METHOD("set_enable_debug", "is_debug_enabled"), &SteamProjectSettings::set_enable_debug);
	ClassDB::bind_method(D_METHOD("set_max_channels", "new_max_channels"), &SteamProjectSettings::set_max_channels);
	ClassDB::bind_method(D_METHOD("set_playtest_id", "new_playtest_id"), &SteamProjectSettings::set_playtest_id);
	ClassDB::bind_method(D_METHOD("set_tool_id", "new_tool_id"), &SteamProjectSettings::set_tool_id);

	ADD_PROPERTY(PropertyInfo(Variant::INT, "app_id"), "set_app_id", "get_app_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "app_type"), "set_app_type", "get_app_type");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "auto_init"), "", "get_auto_init");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "demo_id"), "set_demo_id", "get_demo_id");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "embed_callbacks"), "", "get_embed_callbacks");
	ADD_PROPERTY(PropertyInfo(Variant::BOOL, "enable_debug"), "set_enable_debug", "get_enable_debug");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "max_channels"), "set_max_channels", "get_max_channels");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "playtest_id"), "set_playtest_id", "get_playtest_id");
	ADD_PROPERTY(PropertyInfo(Variant::INT, "tool_id"), "set_tool_id", "get_tool_id");
}


int SteamProjectSettings::get_app_id() {
	return GLOBAL_GET(APP_ID_SETTING);
}

int SteamProjectSettings::get_app_type() {
	return GLOBAL_GET(APP_TYPE_SETTING);
}

bool SteamProjectSettings::get_auto_init() {
	return GLOBAL_GET(STARTUP_INIT_SETTING);
}

int SteamProjectSettings::get_demo_id() {
	return GLOBAL_GET(DEMO_ID_SETTING);
}

bool SteamProjectSettings::get_embed_callbacks() {
	return GLOBAL_GET(EMBED_CALLBACKS_SETTING);
}

bool SteamProjectSettings::get_enable_debug() {
	return GLOBAL_GET(ENABLE_DEBUG_SETTING);
}

int SteamProjectSettings::get_id_in_use() {
	if (get_app_type() == 1) {
		return get_demo_id();
	} else if (get_app_type() == 2) {
		return get_playtest_id();
	} else if (get_app_type() == 3) {
		return get_tool_id();
	} else {
		return get_app_id();
	}
}

int SteamProjectSettings::get_max_channels() {
	return GLOBAL_GET(MAX_CHANNELS_SETTING);
}

int SteamProjectSettings::get_playtest_id() {
	return GLOBAL_GET(PLAYTEST_ID_SETTING);
}

int SteamProjectSettings::get_tool_id() {
	return GLOBAL_GET(TOOL_ID_SETTING);
}

void SteamProjectSettings::register_settings() {
	// Set up our app types and their IDs
	if (!ProjectSettings::get_singleton()->has_setting(APP_TYPE_SETTING)) {
		ProjectSettings::get_singleton()->set(APP_TYPE_SETTING, 0);
	}
#ifdef GDEXTENSION
	Dictionary property_info;
	property_info["name"] = APP_TYPE_SETTING;
	property_info["type"] = Variant::INT;
	property_info["hint"] = PROPERTY_HINT_ENUM;
	property_info["hint_string"] = "App / Game, Demo, Playtest, Tool";
	ProjectSettings::get_singleton()->add_property_info(property_info);
#else
	PropertyInfo property_info(Variant::INT, APP_TYPE_SETTING, PROPERTY_HINT_ENUM, "App / Game, Demo, Playtest, Tool");
	ProjectSettings::get_singleton()->set_custom_property_info(property_info);
#endif
	ProjectSettings::get_singleton()->set_initial_value(APP_TYPE_SETTING, 0);
	ProjectSettings::get_singleton()->set_as_basic(APP_TYPE_SETTING, true);

	if (!ProjectSettings::get_singleton()->has_setting(APP_ID_SETTING)) {
		ProjectSettings::get_singleton()->set(APP_ID_SETTING, 0);
	}
	ProjectSettings::get_singleton()->set_initial_value(APP_ID_SETTING, 0);
	ProjectSettings::get_singleton()->set_as_basic(APP_ID_SETTING, true);

	if (!ProjectSettings::get_singleton()->has_setting(DEMO_ID_SETTING)) {
		ProjectSettings::get_singleton()->set(DEMO_ID_SETTING, 0);
	}
	ProjectSettings::get_singleton()->set_initial_value(DEMO_ID_SETTING, 0);
	ProjectSettings::get_singleton()->set_as_basic(DEMO_ID_SETTING, true);

	if (!ProjectSettings::get_singleton()->has_setting(PLAYTEST_ID_SETTING)) {
		ProjectSettings::get_singleton()->set(PLAYTEST_ID_SETTING, 0);
	}
	ProjectSettings::get_singleton()->set_initial_value(PLAYTEST_ID_SETTING, 0);
	ProjectSettings::get_singleton()->set_as_basic(PLAYTEST_ID_SETTING, true);

	if (!ProjectSettings::get_singleton()->has_setting(TOOL_ID_SETTING)) {
		ProjectSettings::get_singleton()->set(TOOL_ID_SETTING, 0);
	}
	ProjectSettings::get_singleton()->set_initial_value(TOOL_ID_SETTING, 0);
	ProjectSettings::get_singleton()->set_as_basic(TOOL_ID_SETTING, true);

	// Set up our initialization process options
	if (!ProjectSettings::get_singleton()->has_setting(STARTUP_INIT_SETTING)) {
		ProjectSettings::get_singleton()->set(STARTUP_INIT_SETTING, false);
	}
	ProjectSettings::get_singleton()->set_initial_value(STARTUP_INIT_SETTING, false);
	ProjectSettings::get_singleton()->set_as_basic(STARTUP_INIT_SETTING, true);

	if (!ProjectSettings::get_singleton()->has_setting(EMBED_CALLBACKS_SETTING)) {
		ProjectSettings::get_singleton()->set(EMBED_CALLBACKS_SETTING, false);
	}
	ProjectSettings::get_singleton()->set_initial_value(EMBED_CALLBACKS_SETTING, false);
	ProjectSettings::get_singleton()->set_as_basic(EMBED_CALLBACKS_SETTING, true);

	// Set up our MultiplayerPeer stuff
	if (!ProjectSettings::get_singleton()->has_setting(MAX_CHANNELS_SETTING)) {
		ProjectSettings::get_singleton()->set(MAX_CHANNELS_SETTING, 4);
	}
	ProjectSettings::get_singleton()->set_initial_value(MAX_CHANNELS_SETTING, 4);
	ProjectSettings::get_singleton()->set_as_basic(MAX_CHANNELS_SETTING, true);

	// Set up some other settings
	if (!ProjectSettings::get_singleton()->has_setting(ENABLE_DEBUG_SETTING)) {
		ProjectSettings::get_singleton()->set(ENABLE_DEBUG_SETTING, false);
	}
	ProjectSettings::get_singleton()->set_initial_value(ENABLE_DEBUG_SETTING, false);
	ProjectSettings::get_singleton()->set_as_basic(ENABLE_DEBUG_SETTING, true);

	// Port in any pre-GodotSteam v4.20 settings
	if (ProjectSettings::get_singleton()->has_setting(OLD_APP_ID_SETTING)) {
		WARN_PRINT_ONCE("Found older app ID project setting, converting it");
		ProjectSettings::get_singleton()->set_setting(APP_ID_SETTING, ProjectSettings::get_singleton()->get_setting(OLD_APP_ID_SETTING));
		ProjectSettings::get_singleton()->clear(OLD_APP_ID_SETTING);
	}
	if (ProjectSettings::get_singleton()->has_setting(OLD_STARTUP_INIT_SETTING)) {
		WARN_PRINT_ONCE("Found older initialize on startup setting, converting it");
		ProjectSettings::get_singleton()->set_setting(STARTUP_INIT_SETTING, ProjectSettings::get_singleton()->get_setting(OLD_STARTUP_INIT_SETTING));
		ProjectSettings::get_singleton()->clear(OLD_STARTUP_INIT_SETTING);
	}
	if (ProjectSettings::get_singleton()->has_setting(OLD_EMBED_CALLBACKS_SETTING)) {
		WARN_PRINT_ONCE("Found older embed callbacks setting, converting it");
		ProjectSettings::get_singleton()->set_setting(EMBED_CALLBACKS_SETTING, ProjectSettings::get_singleton()->get_setting(OLD_EMBED_CALLBACKS_SETTING));
		ProjectSettings::get_singleton()->clear(OLD_EMBED_CALLBACKS_SETTING);
	}
}

void SteamProjectSettings::set_app_id(int new_app_id) {
	ProjectSettings::get_singleton()->set_setting(APP_ID_SETTING, new_app_id);
}

void SteamProjectSettings::set_app_type(int new_app_type) {
	ProjectSettings::get_singleton()->set_setting(APP_TYPE_SETTING, new_app_type);
}

void SteamProjectSettings::set_demo_id(int new_demo_id) {
	ProjectSettings::get_singleton()->set_setting(DEMO_ID_SETTING, new_demo_id);
}

void SteamProjectSettings::set_enable_debug(bool is_debug_enabled) {
	ProjectSettings::get_singleton()->set_setting(ENABLE_DEBUG_SETTING, is_debug_enabled);
}

void SteamProjectSettings::set_max_channels(int new_max_channels) {
	ProjectSettings::get_singleton()->set_setting(MAX_CHANNELS_SETTING, new_max_channels);
}

void SteamProjectSettings::set_playtest_id(int new_playtest_id) {
	ProjectSettings::get_singleton()->set_setting(PLAYTEST_ID_SETTING, new_playtest_id);
}

void SteamProjectSettings::set_tool_id(int new_tool_id) {
	ProjectSettings::get_singleton()->set_setting(TOOL_ID_SETTING, new_tool_id);
}
