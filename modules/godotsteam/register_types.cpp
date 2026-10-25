/***************************************************************************/
/*  register_types.cpp                                                     */
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

#include "register_types.h"

#ifdef GDEXTENSION
#include <gdextension_interface.h>
#include <godot_cpp/classes/engine.hpp>
#include <godot_cpp/core/class_db.hpp>
#include <godot_cpp/core/defs.hpp>
#include <godot_cpp/godot.hpp>

using namespace godot;
#else
#include "core/config/engine.h"
#include "core/object/class_db.h"
#endif

#include "godotsteam_project_settings.h"
#include "godotsteam.h"
#include "godotsteam_multiplayer_peer.h"


static Steam *SteamPtr = nullptr;
static SteamProjectSettings *SteamProjectSettingsPtr = nullptr;


void initialize_godotsteam_module(ModuleInitializationLevel level) {
	if (level == MODULE_INITIALIZATION_LEVEL_CORE) {
		GDREGISTER_CLASS(Steam);
		GDREGISTER_CLASS(SteamProjectSettings);
		SteamPtr = memnew(Steam);
		SteamProjectSettingsPtr = memnew(SteamProjectSettings);
#ifdef GDEXTENSION
		Engine::get_singleton()->register_singleton("Steam", SteamPtr);
		Engine::get_singleton()->register_singleton("SteamProjectSettings", SteamProjectSettingsPtr);
#else
		Engine::get_singleton()->add_singleton(Engine::Singleton("Steam", SteamPtr));
		Engine::get_singleton()->add_singleton(Engine::Singleton("SteamProjectSettings", SteamProjectSettingsPtr));
#endif
		SteamProjectSettingsPtr->register_settings();

		if (Engine::get_singleton()->is_editor_hint()) {
			return;
		}
		if (!SteamProjectSettingsPtr->get_auto_init()) {
			return;
		}
		SteamPtr->steamInitEx();
	}

	if (level == MODULE_INITIALIZATION_LEVEL_SCENE) {
		GDREGISTER_CLASS(SteamPacketPeer);
		GDREGISTER_CLASS(SteamMultiplayerPeer);

		if (SteamProjectSettingsPtr->get_auto_init() && SteamProjectSettingsPtr->get_embed_callbacks()) {
		 	if (Engine::get_singleton()->is_editor_hint()) {
				return;
			}
			callable_mp_static(&Steam::static_embed_callbacks).call_deferred();
		}
	}
}


void uninitialize_godotsteam_module(ModuleInitializationLevel level) {
	if (level == MODULE_INITIALIZATION_LEVEL_CORE) {
#ifdef GDEXTENSION
		Engine::get_singleton()->unregister_singleton("Steam");
		Engine::get_singleton()->unregister_singleton("SteamProjectSettings");
#else
		Engine::get_singleton()->remove_singleton("Steam");
		Engine::get_singleton()->remove_singleton("SteamProjectSettings");
#endif
		memdelete(SteamPtr);
		memdelete(SteamProjectSettingsPtr);
		SteamPtr = nullptr;
		SteamProjectSettingsPtr = nullptr;
	}
}


#ifdef GDEXTENSION
extern "C" {
GDExtensionBool GDE_EXPORT godotsteam_init(GDExtensionInterfaceGetProcAddress p_interface, const GDExtensionClassLibraryPtr p_library, GDExtensionInitialization *r_initialization) {
	godot::GDExtensionBinding::InitObject init_obj(p_interface, p_library, r_initialization);
	init_obj.register_initializer(initialize_godotsteam_module);
	init_obj.register_terminator(uninitialize_godotsteam_module);
	init_obj.set_minimum_library_initialization_level(MODULE_INITIALIZATION_LEVEL_CORE);
	return init_obj.init();
}
}
#endif
