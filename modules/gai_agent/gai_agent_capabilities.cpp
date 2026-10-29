/**************************************************************************/
/*  gai_agent_capabilities.cpp                                            */
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

#include "gai_agent_server.h"

#include "core/config/engine.h"
#include "core/config/project_settings.h"
#include "core/input/input.h"
#include "core/input/input_event.h"
#include "core/io/image.h"
#include "core/io/resource.h"
#include "core/io/resource_loader.h"
#include "core/io/resource_saver.h"
#include "core/object/class_db.h"
#include "core/os/keyboard.h"
#include "core/os/os.h"
#include "core/templates/local_vector.h"
#include "core/variant/callable.h"
#include "core/variant/variant_utility.h"
#include "scene/main/node.h"
#include "scene/main/scene_tree.h"
#include "scene/main/viewport.h"
#include "scene/main/window.h"

#ifdef TOOLS_ENABLED
#include "editor/editor_interface.h"
#endif

String GaiAgentServer::_handle(Object *p_object) {
	return String::num_uint64((uint64_t)p_object->get_instance_id());
}

Object *GaiAgentServer::_resolve_handle(const Variant &p_value) {
	if (p_value.get_type() != Variant::STRING && p_value.get_type() != Variant::INT) {
		return nullptr;
	}
	const ObjectID id = (ObjectID)String(p_value).to_int();
	return ObjectDB::get_instance(id);
}

Dictionary GaiAgentServer::_error(const String &p_message) {
	Dictionary error;
	error["$gai_error"] = p_message;
	return error;
}

Dictionary GaiAgentServer::_object_info(Object *p_object) {
	if (p_object == nullptr) {
		return _error("null object");
	}
	Dictionary info;
	info["handle"] = _handle(p_object);
	info["class"] = p_object->get_class();
	if (Node *node = Object::cast_to<Node>(p_object)) {
		info["path"] = String(node->get_path());
	}
	if (Resource *resource = Object::cast_to<Resource>(p_object)) {
		info["resource_path"] = resource->get_path();
	}
	return info;
}

Dictionary GaiAgentServer::_property_dict(const PropertyInfo &p_info) {
	Dictionary info;
	info["name"] = p_info.name;
	info["type"] = p_info.type;
	info["type_name"] = Variant::get_type_name(p_info.type);
	info["hint"] = p_info.hint;
	info["hint_string"] = p_info.hint_string;
	info["class_name"] = p_info.class_name;
	info["usage"] = p_info.usage;
	return info;
}

Dictionary GaiAgentServer::_method_dict(const MethodInfo &p_info) {
	Dictionary info;
	info["name"] = p_info.name;
	info["return_type"] = _property_dict(p_info.return_val);
	Array arguments;
	for (const PropertyInfo &argument : p_info.arguments) {
		arguments.push_back(_property_dict(argument));
	}
	info["arguments"] = arguments;
	info["flags"] = p_info.flags;
	Array defaults;
	for (const Variant &value : p_info.default_arguments) {
		defaults.push_back(_json_value(value));
	}
	info["defaults"] = defaults;
	return info;
}

bool GaiAgentServer::_property_for(Object *p_object, const String &p_name, PropertyInfo &r_info) {
	List<PropertyInfo> properties;
	p_object->get_property_list(&properties);
	for (const PropertyInfo &info : properties) {
		if (info.name == p_name) {
			r_info = info;
			return true;
		}
	}
	return false;
}

Variant GaiAgentServer::_to_variant(const Variant &p_value, Variant::Type p_type, String &r_error) {
	if (p_value.get_type() == Variant::DICTIONARY) {
		const Dictionary dict = p_value;
		if (dict.has("$handle")) {
			Object *object = _resolve_handle(dict["$handle"]);
			if (object == nullptr) {
				r_error = "unknown handle";
				return Variant();
			}
			return Variant(object);
		}
		if (dict.has("$var")) {
			const Variant text = dict["$var"];
			if (text.get_type() != Variant::STRING) {
				r_error = "$var must be a string";
				return Variant();
			}
			const Variant parsed = VariantUtilityFunctions::str_to_var(text);
			if (parsed.get_type() == Variant::NIL && !String(text).is_empty()) {
				r_error = "cannot parse $var";
				return Variant();
			}
			return parsed;
		}
		Dictionary out;
		for (const KeyValue<Variant, Variant> &entry : dict) {
			out[entry.key] = _to_variant(entry.value, Variant::NIL, r_error);
			if (!r_error.is_empty()) {
				return Variant();
			}
		}
		return out;
	}
	if (p_value.get_type() == Variant::ARRAY) {
		const Array array = p_value;
		Array out;
		for (const Variant &value : array) {
			out.push_back(_to_variant(value, Variant::NIL, r_error));
			if (!r_error.is_empty()) {
				return Variant();
			}
		}
		return out;
	}
	if (p_value.get_type() == Variant::STRING && p_type != Variant::NIL && p_type != Variant::STRING) {
		const Variant parsed = VariantUtilityFunctions::str_to_var(p_value);
		if (parsed.get_type() == Variant::NIL && !String(p_value).is_empty()) {
			r_error = "cannot parse value as " + Variant::get_type_name(p_type);
			return Variant();
		}
		return parsed;
	}
	return p_value;
}

Variant GaiAgentServer::_set_property(Object *p_object, const String &p_name, const Variant &p_value) {
	PropertyInfo info;
	if (!_property_for(p_object, p_name, info)) {
		return _error("unknown property: " + p_name);
	}
	String error;
	const Variant value = _to_variant(p_value, info.type, error);
	if (!error.is_empty()) {
		return _error(error);
	}
	if (info.type != Variant::NIL && value.get_type() != info.type) {
		if (!Variant::can_convert_strict(value.get_type(), info.type)) {
			return _error("invalid value for " + p_name);
		}
		if (info.type == Variant::BOOL) {
			return _error("invalid value for " + p_name);
		}
	}
	p_object->set(p_name, value);
	return _json_value(p_object->get(p_name));
}

bool GaiAgentServer::_editor_mode() const {
#ifdef TOOLS_ENABLED
	return OS::get_singleton()->get_environment("GAI_AGENT_EDITOR") == "1" || Engine::get_singleton()->is_editor_hint();
#else
	return false;
#endif
}

Node *GaiAgentServer::_editor_scene_root() {
#ifdef TOOLS_ENABLED
	if (_editor_mode()) {
		EditorInterface *editor = EditorInterface::get_singleton();
		if (editor != nullptr) {
			return editor->get_edited_scene_root();
		}
	}
#endif
	return nullptr;
}

String GaiAgentServer::_editor_refusal(const Dictionary &p_params, const String &p_what) {
	if (_editor_mode() && !(bool)p_params.get("force", false)) {
		return p_what + " is disabled in editor mode; pass force=true to override";
	}
	return "";
}

Variant GaiAgentServer::_rpc_api_methods(const Variant &p_params) {
	(void)p_params;
	const char *names[] = {
		"ping",
		"api.methods",
		"api.singletons",
		"api.autoloads",
		"classdb.classes",
		"classdb.class",
		"classdb.instantiate",
		"object.get",
		"object.set",
		"object.call",
		"object.properties",
		"object.methods",
		"object.signals",
		"object.singleton",
		"object.autoload",
		"object.free",
		"scene.tree",
		"scene.current",
		"scene.change",
		"node.get",
		"node.set",
		"node.create",
		"node.delete",
		"node.reparent",
		"node.add_child",
		"resource.load",
		"resource.save",
		"project.get",
		"project.set",
		"project.save",
		"run.status",
		"run.pause",
		"run.resume",
		"run.step",
		"run.time_scale",
		"run.quit",
		"input.action",
		"input.key",
		"input.mouse",
		"render.screenshot",
		"event.subscribe",
		"event.unsubscribe",
		"event.list",
		"client.list",
	};
	Array methods;
	for (const char *name : names) {
		methods.push_back(String(name));
	}
	Dictionary result;
	result["methods"] = methods;
	result["discovery"] = "classdb.classes, classdb.class, object.*, api.singletons";
	return result;
}

Variant GaiAgentServer::_rpc_api_singletons(const Variant &p_params) {
	(void)p_params;
	List<Engine::Singleton> singletons;
	Engine::get_singleton()->get_singletons(&singletons);
	Array out;
	for (const Engine::Singleton &singleton : singletons) {
		Dictionary item;
		item["name"] = String(singleton.name);
		item["class"] = String(singleton.class_name);
		if (singleton.ptr != nullptr) {
			item["handle"] = _handle(singleton.ptr);
		}
		out.push_back(item);
	}
	Dictionary result;
	result["singletons"] = out;
	return result;
}

Variant GaiAgentServer::_rpc_api_autoloads(const Variant &p_params) {
	(void)p_params;
	Array out;
	Node *root = tree != nullptr ? tree->get_root() : nullptr;
	const HashMap<StringName, ProjectSettings::AutoloadInfo> &autoloads =
			ProjectSettings::get_singleton()->get_autoload_list();
	for (const KeyValue<StringName, ProjectSettings::AutoloadInfo> &entry : autoloads) {
		Dictionary item;
		item["name"] = String(entry.key);
		item["path"] = entry.value.path;
		item["singleton"] = entry.value.is_singleton;
		if (root != nullptr) {
			Node *node = root->get_node_or_null(NodePath(String(entry.key)));
			if (node != nullptr) {
				item["handle"] = _handle(node);
				item["class"] = node->get_class();
			}
		}
		out.push_back(item);
	}
	Dictionary result;
	result["autoloads"] = out;
	return result;
}

Variant GaiAgentServer::_rpc_classdb_classes(const Variant &p_params) {
	(void)p_params;
	LocalVector<StringName> classes;
	ClassDB::get_class_list(classes);
	Array out;
	for (const StringName &name : classes) {
		out.push_back(String(name));
	}
	Dictionary result;
	result["classes"] = out;
	return result;
}

Variant GaiAgentServer::_rpc_classdb_class(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String name = params.get("name", "");
	if (!ClassDB::class_exists(name)) {
		return _error("unknown class: " + name);
	}

	List<PropertyInfo> properties;
	ClassDB::get_property_list(name, &properties, false);
	Array property_list;
	for (const PropertyInfo &property : properties) {
		property_list.push_back(_property_dict(property));
	}

	List<MethodInfo> methods;
	ClassDB::get_method_list(name, &methods, false);
	Array method_list;
	for (const MethodInfo &method : methods) {
		method_list.push_back(_method_dict(method));
	}

	List<MethodInfo> signals;
	ClassDB::get_signal_list(name, &signals, false);
	Array signal_list;
	for (const MethodInfo &signal : signals) {
		signal_list.push_back(_method_dict(signal));
	}

	List<String> constants;
	ClassDB::get_integer_constant_list(name, &constants, false);
	Dictionary constant_values;
	for (const String &constant : constants) {
		constant_values[constant] = ClassDB::get_integer_constant(name, constant);
	}

	List<StringName> enums;
	ClassDB::get_enum_list(name, &enums, false);
	Dictionary enum_values;
	for (const StringName &enum_name : enums) {
		List<StringName> enum_constants;
		ClassDB::get_enum_constants(name, enum_name, &enum_constants, false);
		Dictionary values;
		for (const StringName &constant : enum_constants) {
			values[String(constant)] = ClassDB::get_integer_constant(name, constant);
		}
		enum_values[String(enum_name)] = values;
	}

	Dictionary result;
	result["name"] = name;
	result["properties"] = property_list;
	result["methods"] = method_list;
	result["signals"] = signal_list;
	result["constants"] = constant_values;
	result["enums"] = enum_values;
	return result;
}

Variant GaiAgentServer::_rpc_classdb_instantiate(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String name = params.get("name", "");
	if (!ClassDB::can_instantiate(name)) {
		return _error("cannot instantiate class: " + name);
	}
	Object *object = ClassDB::instantiate(name);
	if (object == nullptr) {
		return _error("instantiate failed: " + name);
	}
	const ObjectID id = object->get_instance_id();
	if (RefCounted *ref_counted = Object::cast_to<RefCounted>(object)) {
		refs[id] = Ref<RefCounted>(ref_counted);
	} else {
		created.insert(id);
	}
	return _object_info(object);
}

Variant GaiAgentServer::_rpc_object_singleton(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String name = params.get("name", "");
	Object *object = Engine::get_singleton()->get_singleton_object(name);
	if (object == nullptr) {
		return _error("unknown singleton: " + name);
	}
	return _object_info(object);
}

Variant GaiAgentServer::_rpc_object_autoload(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String name = params.get("name", "");
	if (name.is_empty()) {
		return _error("name is required");
	}
	if (tree == nullptr || tree->get_root() == nullptr) {
		return _error("no scene tree");
	}
	Node *node = tree->get_root()->get_node_or_null(NodePath(name));
	if (node == nullptr) {
		return _error("unknown autoload: " + name);
	}
	return _object_info(node);
}

Variant GaiAgentServer::_rpc_object_get(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Object *object = _resolve_handle(params.get("handle", Variant()));
	if (object == nullptr) {
		return _error("unknown handle");
	}
	const String property = params.get("property", "");
	PropertyInfo info;
	if (!_property_for(object, property, info)) {
		return _error("unknown property: " + property);
	}
	return _json_value(object->get(property));
}

Variant GaiAgentServer::_rpc_object_set(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Object *object = _resolve_handle(params.get("handle", Variant()));
	if (object == nullptr) {
		return _error("unknown handle");
	}
	if (!params.has("value")) {
		return _error("value is required");
	}
	return _set_property(object, params.get("property", ""), params["value"]);
}

Variant GaiAgentServer::_rpc_object_call(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Object *object = _resolve_handle(params.get("handle", Variant()));
	if (object == nullptr) {
		return _error("unknown handle");
	}
	const String method = params.get("method", "");
	if (method.is_empty()) {
		return _error("method is required");
	}
	const ObjectID id = object->get_instance_id();
	if ((method == "free" || method == "queue_free") && !created.has(id) && !refs.has(id)) {
		return _error("refusing to free an object the bridge did not create");
	}
	Array args;
	if (params.has("args")) {
		if (params["args"].get_type() != Variant::ARRAY) {
			return _error("args must be an array");
		}
		args = params["args"];
	}
	MethodInfo method_info;
	bool has_method = false;
	List<MethodInfo> methods;
	object->get_method_list(&methods);
	for (const MethodInfo &info : methods) {
		if (info.name == method) {
			method_info = info;
			has_method = true;
			break;
		}
	}
	Vector<Variant> values;
	String error;
	for (int i = 0; i < args.size(); i++) {
		const Variant::Type type = has_method && i < method_info.arguments.size() ? method_info.arguments[i].type : Variant::NIL;
		const Variant value = _to_variant(args[i], type, error);
		if (!error.is_empty()) {
			return _error(error);
		}
		values.push_back(value);
	}
	Vector<const Variant *> pointers;
	for (int i = 0; i < values.size(); i++) {
		pointers.push_back(&values[i]);
	}
	Callable::CallError call_error;
	const Variant result = object->callp(method, const_cast<const Variant **>(pointers.ptr()), pointers.size(), call_error);
	if (call_error.error != Callable::CallError::CALL_OK) {
		return _error("call failed: " + method);
	}
	return _json_value(result);
}

Variant GaiAgentServer::_rpc_object_properties(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Object *object = _resolve_handle(params.get("handle", Variant()));
	if (object == nullptr) {
		return _error("unknown handle");
	}
	List<PropertyInfo> properties;
	object->get_property_list(&properties);
	Array out;
	for (const PropertyInfo &property : properties) {
		out.push_back(_property_dict(property));
	}
	Dictionary result;
	result["handle"] = _handle(object);
	result["class"] = object->get_class();
	result["properties"] = out;
	return result;
}

Variant GaiAgentServer::_rpc_object_methods(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Object *object = _resolve_handle(params.get("handle", Variant()));
	if (object == nullptr) {
		return _error("unknown handle");
	}
	List<MethodInfo> methods;
	object->get_method_list(&methods);
	Array out;
	for (const MethodInfo &method : methods) {
		out.push_back(_method_dict(method));
	}
	Dictionary result;
	result["handle"] = _handle(object);
	result["class"] = object->get_class();
	result["methods"] = out;
	return result;
}

Variant GaiAgentServer::_rpc_object_signals(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Object *object = _resolve_handle(params.get("handle", Variant()));
	if (object == nullptr) {
		return _error("unknown handle");
	}
	List<MethodInfo> signals;
	object->get_signal_list(&signals);
	Array out;
	for (const MethodInfo &signal : signals) {
		out.push_back(_method_dict(signal));
	}
	Dictionary result;
	result["handle"] = _handle(object);
	result["class"] = object->get_class();
	result["signals"] = out;
	return result;
}

Variant GaiAgentServer::_rpc_object_free(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Object *object = _resolve_handle(params.get("handle", Variant()));
	if (object == nullptr) {
		return _error("unknown handle");
	}
	const ObjectID id = object->get_instance_id();
	if (!created.has(id) && !refs.has(id)) {
		return _error("refusing to free an object the bridge did not create; use node.delete for a tree node");
	}
	if (Node *node = Object::cast_to<Node>(object)) {
		if (node->is_inside_tree()) {
			node->queue_free();
		} else {
			memdelete(node);
		}
	} else if (Object::cast_to<RefCounted>(object)) {
		refs.erase(id);
	} else {
		memdelete(object);
	}
	created.erase(id);
	return Dictionary{ { "freed", true } };
}

Variant GaiAgentServer::_rpc_scene_current(const Variant &p_params) {
	(void)p_params;
	Dictionary result;
	Node *scene = _editor_scene_root();
	if (scene == nullptr && tree != nullptr) {
		scene = tree->get_current_scene();
	}
	if (scene != nullptr) {
		result["scene"] = _object_info(scene);
	}
	return result;
}

Variant GaiAgentServer::_rpc_scene_change(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String refusal = _editor_refusal(params, "scene.change");
	if (!refusal.is_empty()) {
		return _error(refusal);
	}
	const String path = params.get("path", "");
	if (path.is_empty()) {
		return _error("path is required");
	}
	if (tree == nullptr) {
		return _error("no scene tree");
	}
	const Error error = tree->change_scene_to_file(path);
	if (error != OK) {
		return _error("change scene failed: " + itos(error));
	}
	return Dictionary{ { "changed", path } };
}

Variant GaiAgentServer::_rpc_node_create(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Node *parent = _node_for(params.get("parent", ""));
	if (parent == nullptr) {
		return _error("unknown parent");
	}
	const String type = params.get("type", "Node");
	if (!ClassDB::can_instantiate(type)) {
		return _error("cannot instantiate class: " + type);
	}
	Object *object = ClassDB::instantiate(type);
	Node *node = Object::cast_to<Node>(object);
	if (node == nullptr) {
		if (object != nullptr) {
			memdelete(object);
		}
		return _error("not a Node: " + type);
	}
	const String name = params.get("name", "");
	if (!name.is_empty()) {
		node->set_name(name);
	}
	parent->add_child(node);
	if (parent->get_owner() != nullptr) {
		node->set_owner(parent->get_owner());
	}
	return _object_info(node);
}

Variant GaiAgentServer::_rpc_node_delete(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Node *node = _node_for(params.get("path", ""));
	if (node == nullptr) {
		return _error("unknown node");
	}
	const String path = String(node->get_path());
	node->queue_free();
	return Dictionary{ { "deleted", path } };
}

Variant GaiAgentServer::_rpc_node_reparent(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Node *node = _node_for(params.get("path", ""));
	Node *parent = _node_for(params.get("parent", ""));
	if (node == nullptr || parent == nullptr) {
		return _error("unknown node or parent");
	}
	node->reparent(parent, true);
	return _object_info(node);
}

Variant GaiAgentServer::_rpc_node_add_child(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Node *parent = _node_for(params.get("parent", ""));
	Node *child = Object::cast_to<Node>(_resolve_handle(params.get("child", Variant())));
	if (parent == nullptr || child == nullptr) {
		return _error("unknown parent or child");
	}
	if (child->get_parent() != nullptr) {
		return _error("child already has a parent");
	}
	parent->add_child(child);
	if (parent->get_owner() != nullptr) {
		child->set_owner(parent->get_owner());
	}
	return _object_info(child);
}

Variant GaiAgentServer::_rpc_resource_load(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String path = params.get("path", "");
	if (path.is_empty()) {
		return _error("path is required");
	}
	Error error = OK;
	Ref<Resource> resource = ResourceLoader::load(path, "", ResourceLoader::CACHE_MODE_REUSE, &error);
	if (resource.is_null()) {
		return _error("cannot load resource: " + path);
	}
	const ObjectID id = resource->get_instance_id();
	refs[id] = resource;
	return _object_info(resource.ptr());
}

Variant GaiAgentServer::_rpc_resource_save(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	Resource *resource = Object::cast_to<Resource>(_resolve_handle(params.get("handle", Variant())));
	if (resource == nullptr) {
		return _error("unknown resource");
	}
	const String path = params.get("path", "");
	if (path.is_empty()) {
		return _error("path is required");
	}
	const Error error = ResourceSaver::save(resource, path);
	if (error != OK) {
		return _error("save failed: " + itos(error));
	}
	return Dictionary{ { "saved", path } };
}

Variant GaiAgentServer::_rpc_project_get(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String key = params.get("key", "");
	if (key.is_empty()) {
		return _error("key is required");
	}
	ProjectSettings *settings = ProjectSettings::get_singleton();
	return _json_value(settings->get_setting(key));
}

Variant GaiAgentServer::_rpc_project_set(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String key = params.get("key", "");
	if (key.is_empty() || !params.has("value")) {
		return _error("key and value are required");
	}
	String error;
	const Variant value = _to_variant(params["value"], Variant::NIL, error);
	if (!error.is_empty()) {
		return _error(error);
	}
	ProjectSettings::get_singleton()->set_setting(key, value);
	return _json_value(ProjectSettings::get_singleton()->get_setting(key));
}

Variant GaiAgentServer::_rpc_project_save(const Variant &p_params) {
	(void)p_params;
	const Error error = ProjectSettings::get_singleton()->save();
	if (error != OK) {
		return _error("project save failed: " + itos(error));
	}
	return Dictionary{ { "saved", true } };
}

Variant GaiAgentServer::_rpc_run_status(const Variant &p_params) {
	(void)p_params;
	Dictionary result;
	result["paused"] = tree != nullptr ? tree->is_paused() : true;
	result["time_scale"] = Engine::get_singleton()->get_time_scale();
	result["frames"] = Engine::get_singleton()->get_frames_drawn();
	if (tree != nullptr && tree->get_current_scene() != nullptr) {
		result["scene"] = _object_info(tree->get_current_scene());
	}
	return result;
}

Variant GaiAgentServer::_rpc_run_pause(const Variant &p_params) {
	if (p_params.get_type() == Variant::DICTIONARY) {
		const String refusal = _editor_refusal(p_params, "run.pause");
		if (!refusal.is_empty()) {
			return _error(refusal);
		}
	}
	(void)p_params;
	if (tree == nullptr) {
		return _error("no scene tree");
	}
	tree->set_pause(true);
	return Dictionary{ { "paused", true } };
}

Variant GaiAgentServer::_rpc_run_resume(const Variant &p_params) {
	if (p_params.get_type() == Variant::DICTIONARY) {
		const String refusal = _editor_refusal(p_params, "run.resume");
		if (!refusal.is_empty()) {
			return _error(refusal);
		}
	}
	(void)p_params;
	if (tree == nullptr) {
		return _error("no scene tree");
	}
	tree->set_pause(false);
	return Dictionary{ { "paused", false } };
}

Variant GaiAgentServer::_rpc_run_step(const Variant &p_params) {
	if (p_params.get_type() == Variant::DICTIONARY) {
		const String refusal = _editor_refusal(p_params, "run.step");
		if (!refusal.is_empty()) {
			return _error(refusal);
		}
	}
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const int frames = params.get("frames", 1);
	if (frames < 1 || tree == nullptr) {
		return _error("frames must be positive");
	}
	step_frames = frames;
	step_restore_pause = tree->is_paused();
	tree->set_pause(false);
	return Dictionary{ { "frames", frames }, { "resume_after", step_restore_pause } };
}

Variant GaiAgentServer::_rpc_run_time_scale(const Variant &p_params) {
	if (p_params.get_type() == Variant::DICTIONARY) {
		const String refusal = _editor_refusal(p_params, "run.time_scale");
		if (!refusal.is_empty()) {
			return _error(refusal);
		}
	}
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const double scale = params.get("scale", 1.0);
	if (scale < 0.0) {
		return _error("scale must be non-negative");
	}
	Engine::get_singleton()->set_time_scale(scale);
	return Dictionary{ { "time_scale", scale } };
}

Variant GaiAgentServer::_rpc_run_quit(const Variant &p_params) {
	if (p_params.get_type() == Variant::DICTIONARY) {
		const String refusal = _editor_refusal(p_params, "run.quit");
		if (!refusal.is_empty()) {
			return _error(refusal);
		}
	}
	(void)p_params;
	if (tree == nullptr) {
		return _error("no scene tree");
	}
	tree->quit();
	return Dictionary{ { "quitting", true } };
}

Variant GaiAgentServer::_rpc_input_action(const Variant &p_params) {
	if (p_params.get_type() == Variant::DICTIONARY) {
		const String refusal = _editor_refusal(p_params, "input.action");
		if (!refusal.is_empty()) {
			return _error(refusal);
		}
	}
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String name = params.get("name", "");
	if (name.is_empty()) {
		return _error("name is required");
	}
	const bool pressed = params.get("pressed", true);
	if (pressed) {
		Input::get_singleton()->action_press(name, 1.0);
	} else {
		Input::get_singleton()->action_release(name);
	}
	return Dictionary{ { "action", name }, { "pressed", pressed } };
}

Variant GaiAgentServer::_rpc_input_key(const Variant &p_params) {
	if (p_params.get_type() == Variant::DICTIONARY) {
		const String refusal = _editor_refusal(p_params, "input.key");
		if (!refusal.is_empty()) {
			return _error(refusal);
		}
	}
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const int keycode = params.get("keycode", 0);
	if (keycode <= 0) {
		return _error("keycode is required");
	}
	Ref<InputEventKey> event;
	event.instantiate();
	event->set_keycode((Key)keycode);
	event->set_pressed(params.get("pressed", true));
	Input::get_singleton()->parse_input_event(event);
	return Dictionary{ { "keycode", keycode }, { "pressed", params.get("pressed", true) } };
}

Variant GaiAgentServer::_rpc_input_mouse(const Variant &p_params) {
	if (p_params.get_type() == Variant::DICTIONARY) {
		const String refusal = _editor_refusal(p_params, "input.mouse");
		if (!refusal.is_empty()) {
			return _error(refusal);
		}
	}
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const Vector2 position(params.get("x", 0.0), params.get("y", 0.0));
	const int button = params.get("button", -1);
	if (button >= 0) {
		Ref<InputEventMouseButton> event;
		event.instantiate();
		event->set_position(position);
		event->set_button_index((MouseButton)button);
		event->set_pressed(params.get("pressed", true));
		Input::get_singleton()->parse_input_event(event);
	} else {
		Ref<InputEventMouseMotion> event;
		event.instantiate();
		event->set_position(position);
		Input::get_singleton()->parse_input_event(event);
	}
	return Dictionary{ { "x", position.x }, { "y", position.y }, { "button", button } };
}

Variant GaiAgentServer::_rpc_render_screenshot(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String path = params.get("path", "");
	if (path.is_empty()) {
		return _error("path is required");
	}
	if (tree == nullptr) {
		return _error("no scene tree");
	}
	Window *window = Object::cast_to<Window>(tree->get_root());
	if (window == nullptr) {
		return _error("no window");
	}
	Ref<ViewportTexture> texture = window->get_texture();
	if (texture.is_null()) {
		return _error("no viewport texture; run with a display");
	}
	Ref<Image> image = texture->get_image();
	if (image.is_null() || image->is_empty()) {
		return _error("no rendered image; run with a display");
	}
	const Error error = image->save_png(path);
	if (error != OK) {
		return _error("save failed: " + itos(error));
	}
	return Dictionary{ { "path", path }, { "width", image->get_width() }, { "height", image->get_height() } };
}
