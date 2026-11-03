/**************************************************************************/
/*  gai_agent_server.cpp                                                  */
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

#include "core/io/dir_access.h"
#include "core/io/file_access.h"
#include "core/io/ip_address.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/object/message_queue.h"
#include "core/object/script_language.h"
#include "core/os/os.h"
#include "core/os/time.h"
#include "core/string/print_string.h"
#include "core/templates/hashfuncs.h"
#include "core/variant/variant_utility.h"
#include "core/version.h"
#include "scene/main/node.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"

#include <signal.h>

#include <cstring>

#if defined(UNIX_ENABLED) && !defined(WEB_ENABLED)
#define GAI_CRASH_RECORD_ENABLED
#include <fcntl.h>
#include <unistd.h>
#endif

namespace {

#ifdef GAI_CRASH_RECORD_ENABLED

// A fatal signal the engine cannot recover from still tells the agent what it
// was doing. The prefix is formatted before the call, so the handler only
// writes bytes, with no allocation and no lock.
struct GaiCrashRecord {
	char path[4096] = { 0 };
	char prefix[1024] = { 0 };
	int prefix_length = 0;
	volatile sig_atomic_t armed = 0;
	bool installed = false;
};

GaiCrashRecord gai_crash;

void gai_crash_text(char *p_buffer, int &r_length, int p_capacity, const char *p_text) {
	while (*p_text != '\0' && r_length < p_capacity - 1) {
		p_buffer[r_length++] = *p_text++;
	}
}

void gai_crash_number(char *p_buffer, int &r_length, int p_capacity, uint64_t p_value) {
	char digits[20];
	int count = 0;
	do {
		digits[count++] = (char)('0' + (int)(p_value % 10));
		p_value /= 10;
	} while (p_value > 0 && count < 20);
	while (count > 0 && r_length < p_capacity - 1) {
		p_buffer[r_length++] = digits[--count];
	}
}

void gai_crash_json_string(char *p_buffer, int &r_length, int p_capacity, const String &p_text) {
	gai_crash_text(p_buffer, r_length, p_capacity, "\"");
	const CharString utf8 = p_text.utf8();
	for (int index = 0; index < utf8.length() && r_length < p_capacity - 3; index++) {
		const char character = utf8[index];
		if (character == '"' || character == '\\') {
			p_buffer[r_length++] = '\\';
			p_buffer[r_length++] = character;
		} else if ((unsigned char)character >= 0x20) {
			p_buffer[r_length++] = character;
		}
	}
	gai_crash_text(p_buffer, r_length, p_capacity, "\"");
}

const char *gai_crash_signal_name(int p_signal) {
	switch (p_signal) {
#ifdef SIGSEGV
		case SIGSEGV:
			return "SIGSEGV";
#endif
#ifdef SIGBUS
		case SIGBUS:
			return "SIGBUS";
#endif
#ifdef SIGFPE
		case SIGFPE:
			return "SIGFPE";
#endif
#ifdef SIGILL
		case SIGILL:
			return "SIGILL";
#endif
		default:
			return "signal";
	}
}

void gai_crash_handler(int p_signal) {
	if (gai_crash.armed && gai_crash.path[0] != '\0') {
		const int fd = open(gai_crash.path, O_WRONLY | O_CREAT | O_TRUNC, 0644);
		if (fd >= 0) {
			char buffer[1200];
			int length = 0;
			const int capacity = (int)sizeof(buffer);
			const int prefix_length = MIN(gai_crash.prefix_length, capacity - 96);
			memcpy(buffer, gai_crash.prefix, prefix_length);
			length = prefix_length;
			gai_crash_text(buffer, length, capacity, ",\"signal\":\"");
			gai_crash_text(buffer, length, capacity, gai_crash_signal_name(p_signal));
			gai_crash_text(buffer, length, capacity, "\",\"signal_num\":");
			gai_crash_number(buffer, length, capacity, (uint64_t)p_signal);
			gai_crash_text(buffer, length, capacity, "}\n");
			const ssize_t written = write(fd, buffer, (size_t)length);
			(void)written;
			close(fd);
		}
	}
	// Hand the signal back so Godot's own handler and the core dump still run.
	signal(p_signal, SIG_DFL);
	raise(p_signal);
}

#endif // GAI_CRASH_RECORD_ENABLED

} //namespace

class GaiAgentEventCallable : public CallableCustom {
	GaiAgentServer *server = nullptr;
	String binding_key;

	static bool _compare_equal(const CallableCustom *p_a, const CallableCustom *p_b) {
		return p_a == p_b;
	}

	static bool _compare_less(const CallableCustom *p_a, const CallableCustom *p_b) {
		return p_a < p_b;
	}

public:
	GaiAgentEventCallable(GaiAgentServer *p_server, const String &p_binding_key) :
			server(p_server), binding_key(p_binding_key) {}

	uint32_t hash() const override {
		return binding_key.hash();
	}

	String get_as_text() const override {
		return "gai:event";
	}

	CompareEqualFunc get_compare_equal_func() const override {
		return _compare_equal;
	}

	CompareLessFunc get_compare_less_func() const override {
		return _compare_less;
	}

	bool is_valid() const override {
		return true;
	}

	ObjectID get_object() const override {
		return ObjectID();
	}

	void call(const Variant **p_arguments, int p_argcount, Variant &r_return_value, Callable::CallError &r_call_error) const override {
		Array arguments;
		for (int i = 0; i < p_argcount; i++) {
			arguments.push_back(*p_arguments[i]);
		}
		server->_queue_event(binding_key, arguments);
		r_call_error.error = Callable::CallError::CALL_OK;
	}
};

namespace {

// One table decides what a role may call. A method that is not here needs an
// admin, so a new method is closed until someone classifies it.
const GaiAccessRule GAI_ACCESS_RULES[] = {
	{ "ping", GaiAccess::READ },
	{ "api.methods", GaiAccess::READ },
	{ "api.singletons", GaiAccess::READ },
	{ "api.autoloads", GaiAccess::READ },
	{ "classdb.classes", GaiAccess::READ },
	{ "classdb.class", GaiAccess::READ },
	{ "classdb.instantiate", GaiAccess::READ },
	{ "script.classes", GaiAccess::READ },
	{ "script.class", GaiAccess::READ },
	{ "object.get", GaiAccess::READ },
	{ "object.properties", GaiAccess::READ },
	{ "object.methods", GaiAccess::READ },
	{ "object.signals", GaiAccess::READ },
	{ "object.singleton", GaiAccess::READ },
	{ "object.autoload", GaiAccess::READ },
	{ "scene.tree", GaiAccess::READ },
	{ "scene.current", GaiAccess::READ },
	{ "node.get", GaiAccess::READ },
	{ "resource.load", GaiAccess::READ },
	{ "project.get", GaiAccess::READ },
	{ "run.status", GaiAccess::READ },
	{ "event.subscribe", GaiAccess::READ },
	{ "event.unsubscribe", GaiAccess::READ },
	{ "event.list", GaiAccess::READ },
	{ "client.list", GaiAccess::READ },
	{ "object.set", GaiAccess::WRITE },
	{ "object.call", GaiAccess::WRITE },
	{ "object.free", GaiAccess::WRITE },
	{ "node.set", GaiAccess::WRITE },
	{ "node.create", GaiAccess::WRITE },
	{ "node.delete", GaiAccess::WRITE },
	{ "node.reparent", GaiAccess::WRITE },
	{ "node.add_child", GaiAccess::WRITE },
	{ "resource.save", GaiAccess::WRITE },
	{ "project.set", GaiAccess::WRITE },
	{ "project.save", GaiAccess::WRITE },
	{ "run.pause", GaiAccess::WRITE },
	{ "run.resume", GaiAccess::WRITE },
	{ "run.step", GaiAccess::WRITE },
	{ "run.time_scale", GaiAccess::WRITE },
	{ "input.action", GaiAccess::WRITE },
	{ "input.key", GaiAccess::WRITE },
	{ "input.mouse", GaiAccess::WRITE },
	{ "render.screenshot", GaiAccess::WRITE },
	{ "scene.change", GaiAccess::ADMIN },
	{ "run.quit", GaiAccess::ADMIN },
};

const char *gai_access_name(GaiAccess p_access) {
	switch (p_access) {
		case GaiAccess::READ:
			return "read";
		case GaiAccess::WRITE:
			return "write";
		default:
			return "admin";
	}
}

} //namespace

GaiAgentServer::GaiAgentServer() {
	rpc.set_method("ping", callable_mp(this, &GaiAgentServer::_rpc_ping));
	rpc.set_method("api.methods", callable_mp(this, &GaiAgentServer::_rpc_api_methods));
	rpc.set_method("api.singletons", callable_mp(this, &GaiAgentServer::_rpc_api_singletons));
	rpc.set_method("api.autoloads", callable_mp(this, &GaiAgentServer::_rpc_api_autoloads));
	rpc.set_method("classdb.classes", callable_mp(this, &GaiAgentServer::_rpc_classdb_classes));
	rpc.set_method("classdb.class", callable_mp(this, &GaiAgentServer::_rpc_classdb_class));
	rpc.set_method("classdb.instantiate", callable_mp(this, &GaiAgentServer::_rpc_classdb_instantiate));
	rpc.set_method("script.classes", callable_mp(this, &GaiAgentServer::_rpc_script_classes));
	rpc.set_method("script.class", callable_mp(this, &GaiAgentServer::_rpc_script_class));
	rpc.set_method("object.get", callable_mp(this, &GaiAgentServer::_rpc_object_get));
	rpc.set_method("object.set", callable_mp(this, &GaiAgentServer::_rpc_object_set));
	rpc.set_method("object.call", callable_mp(this, &GaiAgentServer::_rpc_object_call));
	rpc.set_method("object.properties", callable_mp(this, &GaiAgentServer::_rpc_object_properties));
	rpc.set_method("object.methods", callable_mp(this, &GaiAgentServer::_rpc_object_methods));
	rpc.set_method("object.signals", callable_mp(this, &GaiAgentServer::_rpc_object_signals));
	rpc.set_method("object.singleton", callable_mp(this, &GaiAgentServer::_rpc_object_singleton));
	rpc.set_method("object.autoload", callable_mp(this, &GaiAgentServer::_rpc_object_autoload));
	rpc.set_method("object.free", callable_mp(this, &GaiAgentServer::_rpc_object_free));
	rpc.set_method("scene.tree", callable_mp(this, &GaiAgentServer::_rpc_scene_tree));
	rpc.set_method("scene.current", callable_mp(this, &GaiAgentServer::_rpc_scene_current));
	rpc.set_method("scene.change", callable_mp(this, &GaiAgentServer::_rpc_scene_change));
	rpc.set_method("node.get", callable_mp(this, &GaiAgentServer::_rpc_node_get));
	rpc.set_method("node.set", callable_mp(this, &GaiAgentServer::_rpc_node_set));
	rpc.set_method("node.create", callable_mp(this, &GaiAgentServer::_rpc_node_create));
	rpc.set_method("node.delete", callable_mp(this, &GaiAgentServer::_rpc_node_delete));
	rpc.set_method("node.reparent", callable_mp(this, &GaiAgentServer::_rpc_node_reparent));
	rpc.set_method("node.add_child", callable_mp(this, &GaiAgentServer::_rpc_node_add_child));
	rpc.set_method("resource.load", callable_mp(this, &GaiAgentServer::_rpc_resource_load));
	rpc.set_method("resource.save", callable_mp(this, &GaiAgentServer::_rpc_resource_save));
	rpc.set_method("project.get", callable_mp(this, &GaiAgentServer::_rpc_project_get));
	rpc.set_method("project.set", callable_mp(this, &GaiAgentServer::_rpc_project_set));
	rpc.set_method("project.save", callable_mp(this, &GaiAgentServer::_rpc_project_save));
	rpc.set_method("run.status", callable_mp(this, &GaiAgentServer::_rpc_run_status));
	rpc.set_method("run.pause", callable_mp(this, &GaiAgentServer::_rpc_run_pause));
	rpc.set_method("run.resume", callable_mp(this, &GaiAgentServer::_rpc_run_resume));
	rpc.set_method("run.step", callable_mp(this, &GaiAgentServer::_rpc_run_step));
	rpc.set_method("run.time_scale", callable_mp(this, &GaiAgentServer::_rpc_run_time_scale));
	rpc.set_method("run.quit", callable_mp(this, &GaiAgentServer::_rpc_run_quit));
	rpc.set_method("input.action", callable_mp(this, &GaiAgentServer::_rpc_input_action));
	rpc.set_method("input.key", callable_mp(this, &GaiAgentServer::_rpc_input_key));
	rpc.set_method("input.mouse", callable_mp(this, &GaiAgentServer::_rpc_input_mouse));
	rpc.set_method("render.screenshot", callable_mp(this, &GaiAgentServer::_rpc_render_screenshot));
	rpc.set_method("event.subscribe", callable_mp(this, &GaiAgentServer::_rpc_event_subscribe));
	rpc.set_method("event.unsubscribe", callable_mp(this, &GaiAgentServer::_rpc_event_unsubscribe));
	rpc.set_method("event.list", callable_mp(this, &GaiAgentServer::_rpc_event_list));
	rpc.set_method("client.list", callable_mp(this, &GaiAgentServer::_rpc_client_list));
}

GaiAgentServer::~GaiAgentServer() {
	stop();
}

void GaiAgentServer::start() {
	if (server.is_valid()) {
		return;
	}
	if (tree == nullptr) {
		tree = SceneTree::get_singleton();
		if (tree == nullptr) {
			MessageQueue::get_main_singleton()->push_callable(callable_mp(this, &GaiAgentServer::start));
			return;
		}
	}
	token = OS::get_singleton()->get_environment("GAI_AGENT_TOKEN");
	const String port_string = OS::get_singleton()->get_environment("GAI_AGENT_PORT");
	if (token.is_empty() || port_string.is_empty()) {
		return;
	}
	port = port_string.to_int();
	if (port <= 0 || port > 65535) {
		print_error("gai_agent: invalid GAI_AGENT_PORT");
		return;
	}

	server.instantiate();
	if (server->listen((uint16_t)port, IPAddress("127.0.0.1")) != OK) {
		print_error("gai_agent: cannot listen on 127.0.0.1:" + itos(port));
		server = Ref<TCPServer>();
		return;
	}
	const String configured_role = OS::get_singleton()->get_environment("GAI_AGENT_ROLE");
	if (!configured_role.is_empty()) {
		role = configured_role;
	}
	if (role == "read-only") {
		role_access = GaiAccess::READ;
	} else if (role == "write") {
		role_access = GaiAccess::WRITE;
	} else if (role != "admin") {
		print_error("gai_agent: unknown role '" + role + "'; use admin, write, or read-only");
		server = Ref<TCPServer>();
		return;
	}
	String audit_file = OS::get_singleton()->get_environment("GAI_AUDIT_LOG");
	if (audit_file.is_empty()) {
		audit_file = OS::get_singleton()->get_data_path().path_join("gai").path_join("audit.jsonl");
	}
	DirAccess::make_dir_recursive_absolute(audit_file.get_base_dir());
	audit = FileAccess::open(audit_file, FileAccess::WRITE_READ);
	if (audit.is_null()) {
		print_error("gai_agent: cannot open the audit log at " + audit_file);
	}
	audit_path = audit_file;
	print_line("GAI_AGENT_ROLE " + role);
	tree->connect("process_frame", callable_mp(this, &GaiAgentServer::poll));
	print_line("GAI_AGENT_LISTENING " + itos(port));
	_install_crash_record();
}

void GaiAgentServer::stop() {
	if (tree != nullptr) {
		const Callable callback = callable_mp(this, &GaiAgentServer::poll);
		if (tree->is_connected("process_frame", callback)) {
			tree->disconnect("process_frame", callback);
		}
		tree = nullptr;
	}
	if (server.is_valid()) {
		server->stop();
		server = Ref<TCPServer>();
	}
	_drop_clients();
	for (ObjectID id : created) {
		Object *object = ObjectDB::get_instance(id);
		if (object == nullptr) {
			continue;
		}
		if (Node *node = Object::cast_to<Node>(object)) {
			if (!node->is_inside_tree()) {
				memdelete(node);
			}
		} else {
			memdelete(object);
		}
	}
	created.clear();
	refs.clear();
	_remove_crash_record();
}

namespace {
constexpr int GAI_MAX_CLIENTS = 8;
constexpr int GAI_MAX_SUBSCRIPTIONS = 64;
constexpr int GAI_MAX_OUTPUT_BYTES = 4 * 1024 * 1024;
constexpr uint64_t GAI_IDLE_TIMEOUT_MS = 10 * 60 * 1000;
constexpr int GAI_MAX_BATCH = 64;
constexpr uint64_t GAI_BATCH_DEADLINE_MS = 10000;
constexpr int GAI_MAX_EVENT_HISTORY = 512;
constexpr int GAI_MAX_REPLAY = 128;
} //namespace

void GaiAgentServer::_drop_clients() {
	Vector<int> ids;
	for (const KeyValue<int, Client *> &entry : clients) {
		ids.push_back(entry.key);
	}
	for (int id : ids) {
		Client **found = clients.getptr(id);
		if (found != nullptr) {
			_drop_client(*found);
		}
	}
	clients.clear();
	current_client = nullptr;
}

void GaiAgentServer::_drop_client(Client *p_client) {
	if (p_client == nullptr) {
		return;
	}
	_disconnect_subscriptions(p_client);
	if (p_client->peer.is_valid()) {
		p_client->peer->disconnect_from_host();
	}
	if (current_client == p_client) {
		current_client = nullptr;
	}
	clients.erase(p_client->id);
	memdelete(p_client);
}

void GaiAgentServer::_disconnect_subscriptions(Client *p_client) {
	for (KeyValue<int, Subscription> &entry : p_client->subscriptions) {
		const String key = entry.value.binding_key;
		SignalBinding *binding = bindings.getptr(key);
		if (binding == nullptr) {
			continue;
		}
		for (int index = binding->subscribers.size() - 1; index >= 0; index--) {
			const EventSubscriber &subscriber = binding->subscribers[index];
			if (subscriber.client_id == p_client->id && subscriber.subscription_id == entry.key) {
				binding->subscribers.remove_at(index);
			}
		}
		if (binding->subscribers.is_empty()) {
			Object *object = ObjectDB::get_instance(binding->object_id);
			if (object != nullptr && binding->callable.is_valid() && object->is_connected(binding->signal, binding->callable)) {
				object->disconnect(binding->signal, binding->callable);
			}
			bindings.erase(key);
		}
	}
	p_client->subscriptions.clear();
}

void GaiAgentServer::_prune_bindings() {
	Vector<String> keys;
	for (const KeyValue<String, SignalBinding> &entry : bindings) {
		keys.push_back(entry.key);
	}
	for (const String &key : keys) {
		SignalBinding *binding = bindings.getptr(key);
		if (binding == nullptr) {
			continue;
		}
		if (ObjectDB::get_instance(binding->object_id) != nullptr) {
			continue;
		}
		const ObjectID object_id = binding->object_id;
		const StringName signal = binding->signal;
		const String path = binding->path;
		const Vector<EventSubscriber> subscribers = binding->subscribers;
		bindings.erase(key);
		for (const EventSubscriber &subscriber : subscribers) {
			Client **found = clients.getptr(subscriber.client_id);
			if (found == nullptr) {
				continue;
			}
			Client *client = *found;
			Subscription *subscription = client->subscriptions.getptr(subscriber.subscription_id);
			if (subscription == nullptr) {
				continue;
			}
			Dictionary params;
			params["subscription"] = subscriber.subscription_id;
			params["signal"] = String(signal);
			params["handle"] = String::num_uint64((uint64_t)object_id);
			params["path"] = path;
			params["closed"] = true;
			client->subscriptions.erase(subscriber.subscription_id);
			Dictionary notification;
			notification["jsonrpc"] = "2.0";
			notification["method"] = "event";
			notification["params"] = params;
			_send_to(subscriber.client_id, JSON::stringify(notification) + "\n");
			if (!clients.has(subscriber.client_id)) {
				continue;
			}
		}
	}
}

void GaiAgentServer::_accept_client(uint64_t p_now) {
	while (server.is_valid() && server->is_connection_available()) {
		Ref<StreamPeerTCP> incoming = server->take_connection();
		if (incoming.is_null()) {
			break;
		}
		if (clients.size() >= GAI_MAX_CLIENTS) {
			incoming->disconnect_from_host();
			continue;
		}
		Client *client = memnew(Client);
		client->id = next_client_id++;
		client->peer = incoming;
		client->last_activity = p_now;
		clients[client->id] = client;
	}
}

void GaiAgentServer::_poll_client(Client *p_client, uint64_t p_now) {
	if (p_client == nullptr || p_client->peer.is_null()) {
		_drop_client(p_client);
		return;
	}
	const int client_id = p_client->id;
	p_client->peer->poll();
	if (p_client->peer->get_status() != StreamPeerTCP::STATUS_CONNECTED) {
		_drop_client(p_client);
		return;
	}
	if (p_client->subscriptions.is_empty() && p_now - p_client->last_activity > GAI_IDLE_TIMEOUT_MS) {
		_drop_client(p_client);
		return;
	}
	_flush_client(p_client);
	if (!clients.has(client_id)) {
		return;
	}
	_read_client(p_client);
	if (!clients.has(client_id)) {
		return;
	}
	_flush_client(p_client);
}

void GaiAgentServer::poll() {
	if (!server.is_valid() || !server->is_listening()) {
		return;
	}
	if (step_frames > 0) {
		step_frames--;
		if (step_frames == 0 && step_restore_pause && tree != nullptr) {
			tree->set_pause(true);
			step_restore_pause = false;
		}
	}
	const uint64_t now = OS::get_singleton()->get_ticks_msec();
	_accept_client(now);
	_prune_bindings();
	Vector<int> ids;
	for (const KeyValue<int, Client *> &entry : clients) {
		ids.push_back(entry.key);
	}
	for (int id : ids) {
		Client **found = clients.getptr(id);
		if (found != nullptr) {
			_poll_client(*found, now);
		}
	}
}

void GaiAgentServer::_read_client(Client *p_client) {
	const int client_id = p_client->id;
	int handled = 0;
	while (p_client->peer.is_valid() && p_client->peer->get_available_bytes() > 0 && handled < 32) {
		uint8_t byte = 0;
		int read = 0;
		if (p_client->peer->get_partial_data(&byte, 1, read) != OK || read != 1) {
			break;
		}
		if (byte == '\r') {
			continue;
		}
		if (byte == '\n') {
			if (!p_client->line_buffer.is_empty()) {
				const String line = String::utf8((const char *)p_client->line_buffer.ptr(), p_client->line_buffer.size()).strip_edges();
				p_client->line_buffer.clear();
				if (!line.is_empty()) {
					handled++;
					p_client->last_activity = OS::get_singleton()->get_ticks_msec();
					_handle(p_client, line);
					if (!clients.has(client_id)) {
						return;
					}
				}
			}
			continue;
		}
		p_client->line_buffer.push_back(byte);
		if (p_client->line_buffer.size() > 65536) {
			p_client->line_buffer.clear();
			_send_to(p_client->id, JSON::stringify(rpc.make_response_error(JSONRPC::INVALID_REQUEST, "Request too large")) + "\n");
			return;
		}
	}
}

void GaiAgentServer::_flush_client(Client *p_client) {
	if (p_client == nullptr || p_client->peer.is_null()) {
		return;
	}
	while (p_client->output_offset < p_client->output.size()) {
		int sent = 0;
		const Error err = p_client->peer->put_partial_data(
				p_client->output.ptr() + p_client->output_offset,
				p_client->output.size() - p_client->output_offset,
				sent);
		if (err == ERR_BUSY) {
			return;
		}
		if (err != OK) {
			_drop_client(p_client);
			return;
		}
		if (sent <= 0) {
			return;
		}
		p_client->output_offset += sent;
	}
	if (p_client->output_offset > 0) {
		p_client->output.clear();
		p_client->output_offset = 0;
	}
}

void GaiAgentServer::_handle(Client *p_client, const String &p_line) {
	if (p_client == nullptr) {
		return;
	}
	Client *previous = current_client;
	current_client = p_client;
	_handle_line(p_line);
	current_client = previous;
}

void GaiAgentServer::_handle_line(const String &p_line) {
	JSON json;
	if (json.parse(p_line) != OK) {
		_send(JSON::stringify(rpc.make_response_error(JSONRPC::PARSE_ERROR, "Parse error")) + "\n");
		return;
	}
	const Variant data = json.get_data();
	if (data.get_type() == Variant::DICTIONARY) {
		const Dictionary request = data;
		const Variant id = request.get("id", Variant());
		if (String(request.get("token", "")) != token) {
			_send(JSON::stringify(rpc.make_response_error(-32001, "Unauthorized", id)) + "\n");
			return;
		}
		const Variant response = _process_request(request, id);
		if (response.get_type() == Variant::NIL) {
			return;
		}
		_send(JSON::stringify(response) + "\n");
		return;
	}

	if (data.get_type() == Variant::ARRAY) {
		const Array batch = data;
		if (batch.is_empty()) {
			_send(JSON::stringify(rpc.make_response_error(JSONRPC::INVALID_REQUEST, "Invalid Request")) + "\n");
			return;
		}
		if (batch.size() > GAI_MAX_BATCH) {
			_send(JSON::stringify(rpc.make_response_error(JSONRPC::INVALID_REQUEST, "Batch too large")) + "\n");
			return;
		}
		const uint64_t started = OS::get_singleton()->get_ticks_msec();
		Array responses;
		for (int index = 0; index < batch.size(); index++) {
			if (OS::get_singleton()->get_ticks_msec() - started > GAI_BATCH_DEADLINE_MS) {
				for (int remaining = index; remaining < batch.size(); remaining++) {
					const Variant item = batch[remaining];
					if (item.get_type() != Variant::DICTIONARY) {
						continue;
					}
					const Dictionary request = item;
					if (!request.has("id")) {
						continue;
					}
					responses.push_back(rpc.make_response_error(-32000, "Batch deadline exceeded", request["id"]));
				}
				break;
			}
			const Variant item = batch[index];
			if (item.get_type() != Variant::DICTIONARY) {
				responses.push_back(rpc.make_response_error(JSONRPC::INVALID_REQUEST, "Invalid Request"));
				continue;
			}
			const Dictionary request = item;
			const Variant id = request.get("id", Variant());
			if (String(request.get("token", "")) != token) {
				responses.push_back(rpc.make_response_error(-32001, "Unauthorized", id));
				continue;
			}
			const Variant response = _process_request(request, id);
			if (response.get_type() != Variant::NIL) {
				responses.push_back(response);
			}
		}
		if (!responses.is_empty()) {
			_send(JSON::stringify(responses) + "\n");
		}
		return;
	}

	_send(JSON::stringify(rpc.make_response_error(JSONRPC::INVALID_REQUEST, "Invalid request")) + "\n");
}

GaiAccess GaiAgentServer::_required_access(const String &p_method) const {
	// One table decides what a role may call. An unlisted method needs an admin,
	// so a new method is closed until someone classifies it.
	for (const GaiAccessRule &rule : GAI_ACCESS_RULES) {
		if (p_method == rule.method) {
			return rule.access;
		}
	}
	return GaiAccess::ADMIN;
}

bool GaiAgentServer::_role_allows(GaiAccess p_required) const {
	switch (role_access) {
		case GaiAccess::READ:
			return p_required == GaiAccess::READ;
		case GaiAccess::WRITE:
			return p_required != GaiAccess::ADMIN;
		default:
			return true;
	}
}

Dictionary GaiAgentServer::_forbidden(const String &p_method, GaiAccess p_required) {
	Dictionary error;
	error["$gai_forbidden"] = vformat("%s needs the %s role; this bridge runs as %s", p_method, gai_access_name(p_required), role);
	return error;
}

void GaiAgentServer::_audit(const Dictionary &p_request, const String &p_target, GaiAccess p_access, bool p_allowed) {
	if (audit.is_null() || p_access == GaiAccess::READ) {
		return;
	}
	// One line per mutating request, written as it happens: the log answers
	// "who changed what" after the fact, so it must not wait for a shutdown.
	Dictionary line;
	line["ts"] = Time::get_singleton()->get_datetime_string_from_system(true);
	line["pid"] = OS::get_singleton()->get_process_id();
	line["client"] = current_client != nullptr ? current_client->id : 0;
	line["role"] = role;
	line["access"] = gai_access_name(p_access);
	line["method"] = String(p_request.get("method", ""));
	line["target"] = p_target;
	line["allowed"] = p_allowed;
	audit->seek_end();
	audit->store_line(JSON::stringify(line));
	audit->flush();
}

void GaiAgentServer::_install_crash_record() {
#ifdef GAI_CRASH_RECORD_ENABLED
	if (gai_crash.installed) {
		return;
	}
	String path = OS::get_singleton()->get_environment("GAI_CRASH_RECORD");
	if (path.is_empty()) {
		path = OS::get_singleton()->get_data_path().path_join("gai").path_join("bridge-crash.json");
	}
	DirAccess::make_dir_recursive_absolute(path.get_base_dir());
	const CharString utf8 = path.utf8();
	if (utf8.length() == 0 || utf8.length() >= (int)sizeof(gai_crash.path)) {
		return;
	}
	memcpy(gai_crash.path, utf8.get_data(), utf8.length());
	gai_crash.path[utf8.length()] = '\0';

	struct sigaction action = {};
	action.sa_handler = gai_crash_handler;
	action.sa_flags = SA_RESETHAND;
	sigemptyset(&action.sa_mask);
	const int signals[] = { SIGSEGV, SIGFPE, SIGILL, SIGABRT };
	for (int index = 0; index < 4; index++) {
		sigaction(signals[index], &action, nullptr);
	}
	gai_crash.installed = true;
#endif
}

void GaiAgentServer::_remove_crash_record() {
#ifdef GAI_CRASH_RECORD_ENABLED
	if (!gai_crash.installed || gai_crash.path[0] == '\0') {
		return;
	}
	// A clean shutdown must not leave a record that frames a later crash.
	DirAccess::remove_absolute(String::utf8(gai_crash.path));
#endif
}

void GaiAgentServer::_arm_crash_record(const String &p_method, const String &p_target) {
#ifdef GAI_CRASH_RECORD_ENABLED
	if (!gai_crash.installed) {
		return;
	}
	int length = 0;
	const int capacity = (int)sizeof(gai_crash.prefix);
	gai_crash_text(gai_crash.prefix, length, capacity, "{\"schema\":1,\"pid\":");
	gai_crash_number(gai_crash.prefix, length, capacity, (uint64_t)OS::get_singleton()->get_process_id());
	gai_crash_text(gai_crash.prefix, length, capacity, ",\"method\":");
	gai_crash_json_string(gai_crash.prefix, length, capacity, p_method);
	gai_crash_text(gai_crash.prefix, length, capacity, ",\"target\":");
	gai_crash_json_string(gai_crash.prefix, length, capacity, p_target);
	gai_crash_text(gai_crash.prefix, length, capacity, ",\"started_ms\":");
	gai_crash_number(gai_crash.prefix, length, capacity, (uint64_t)OS::get_singleton()->get_ticks_msec());
	gai_crash.prefix_length = length;
	gai_crash.armed = 1;
#endif
}

void GaiAgentServer::_disarm_crash_record() {
#ifdef GAI_CRASH_RECORD_ENABLED
	gai_crash.armed = 0;
#endif
}

Variant GaiAgentServer::_process_request(const Dictionary &p_request, const Variant &p_id) {
	const String method = p_request.get("method", String());
	String target;
	const Variant params = p_request.get("params", Variant());
	if (params.get_type() == Variant::DICTIONARY) {
		const Dictionary dict = params;
		if (dict.has("handle")) {
			target = "handle=" + dict["handle"].stringify();
		}
		if (dict.has("path")) {
			target = "path=" + String(dict["path"]);
		}
		if (dict.has("method")) {
			target += " call=" + String(dict["method"]);
		}
	}
	const GaiAccess required = _required_access(method);
	const bool allowed = _role_allows(required);
	_audit(p_request, target, required, allowed);
	if (!allowed) {
		return rpc.make_response_error(-32003, String(Dictionary(_forbidden(method, required))["$gai_forbidden"]), p_id);
	}
	_arm_crash_record(method, target);
	const Variant response = rpc.process_action(p_request);
	_disarm_crash_record();
	if (response.get_type() == Variant::DICTIONARY) {
		const Dictionary response_dict = response;
		if (response_dict.has("result") && response_dict["result"].get_type() == Variant::DICTIONARY) {
			const Dictionary result = response_dict["result"];
			if (result.has("$gai_error")) {
				return rpc.make_response_error(JSONRPC::INVALID_PARAMS, String(result["$gai_error"]), p_id);
			}
		}
	}
	return response;
}

void GaiAgentServer::_send(const String &p_payload) {
	if (current_client == nullptr) {
		return;
	}
	_send_to(current_client->id, p_payload);
}

void GaiAgentServer::_send_to(int p_client_id, const String &p_payload) {
	Client **found = clients.getptr(p_client_id);
	if (found == nullptr) {
		return;
	}
	Client *client = *found;
	const CharString utf8 = p_payload.utf8();
	const int old_size = client->output.size();
	client->output.resize(old_size + utf8.length());
	if (utf8.length() > 0) {
		memcpy(client->output.ptrw() + old_size, utf8.get_data(), utf8.length());
	}
	if (client->output.size() > GAI_MAX_OUTPUT_BYTES) {
		print_error("gai_agent: client output limit reached; dropping client " + itos(client->id));
		_drop_client(client);
	}
}

void GaiAgentServer::_queue_event(const String &p_binding_key, const Array &p_args) {
	SignalBinding *binding = bindings.getptr(p_binding_key);
	if (binding == nullptr) {
		return;
	}
	Object *object = ObjectDB::get_instance(binding->object_id);
	if (object == nullptr) {
		_prune_bindings();
		return;
	}
	EventRecord record;
	record.seq = next_event_seq++;
	record.object_id = binding->object_id;
	record.signal = binding->signal;
	if (Node *node = Object::cast_to<Node>(object)) {
		record.path = String(node->get_path());
	}
	for (int index = 0; index < p_args.size(); index++) {
		record.args.push_back(_json_value(p_args[index]));
	}
	event_history.push_back(record);
	if (event_history.size() > GAI_MAX_EVENT_HISTORY) {
		event_history.remove_at(0);
	}

	const Vector<EventSubscriber> subscribers = binding->subscribers;
	for (const EventSubscriber &subscriber : subscribers) {
		Client **found = clients.getptr(subscriber.client_id);
		if (found == nullptr) {
			continue;
		}
		Client *client = *found;
		if (!client->subscriptions.has(subscriber.subscription_id)) {
			continue;
		}
		Dictionary params;
		params["subscription"] = subscriber.subscription_id;
		params["seq"] = (int64_t)record.seq;
		params["signal"] = String(record.signal);
		params["handle"] = String::num_uint64((uint64_t)record.object_id);
		params["path"] = record.path;
		params["args"] = record.args;
		Dictionary notification;
		notification["jsonrpc"] = "2.0";
		notification["method"] = "event";
		notification["params"] = params;
		_send_to(subscriber.client_id, JSON::stringify(notification) + "\n");
		if (!clients.has(subscriber.client_id)) {
			continue;
		}
	}
}

Node *GaiAgentServer::_node_for(const String &p_path) {
	if (tree == nullptr) {
		return nullptr;
	}
	if (p_path.is_empty()) {
		Node *edited = _editor_scene_root();
		return edited != nullptr ? edited : tree->get_current_scene();
	}
	Node *root = tree->get_root();
	if (root == nullptr) {
		return nullptr;
	}
	return root->get_node_or_null(NodePath(p_path));
}

Variant GaiAgentServer::_json_value(const Variant &p_value, int p_depth) {
	if (p_depth > 64) {
		return String("<max depth>");
	}
	if (p_value.get_type() == Variant::OBJECT) {
		Object *object = p_value;
		if (object != nullptr) {
			return _object_info(object);
		}
		return Variant();
	}
	switch (p_value.get_type()) {
		case Variant::NIL:
		case Variant::BOOL:
		case Variant::INT:
		case Variant::FLOAT:
		case Variant::STRING:
			return p_value;
		case Variant::ARRAY: {
			const Array array = p_value;
			Array out;
			for (const Variant &value : array) {
				out.push_back(_json_value(value, p_depth + 1));
			}
			return out;
		}
		case Variant::DICTIONARY: {
			const Dictionary dictionary = p_value;
			Dictionary out;
			for (const KeyValue<Variant, Variant> &entry : dictionary) {
				out[entry.key] = _json_value(entry.value, p_depth + 1);
			}
			return out;
		}
		default:
			return VariantUtilityFunctions::var_to_str(p_value);
	}
}

Dictionary GaiAgentServer::_node_info(Node *p_node, const Array &p_properties) {
	Dictionary info;
	info["name"] = String(p_node->get_name());
	info["type"] = p_node->get_class();
	info["path"] = String(p_node->get_path());
	info["handle"] = _handle(p_node);

	const Variant script_variant = p_node->get_script();
	if (script_variant.get_type() == Variant::OBJECT) {
		Script *script = Object::cast_to<Script>(script_variant);
		if (script != nullptr) {
			info["script"] = script->get_path();
		}
	}

	Array children;
	for (int i = 0; i < p_node->get_child_count(); i++) {
		children.push_back(_node_info(p_node->get_child(i), p_properties));
	}
	info["children"] = children;

	if (!p_properties.is_empty()) {
		Dictionary properties;
		for (int i = 0; i < p_properties.size(); i++) {
			const String property = p_properties[i];
			properties[property] = _json_value(p_node->get(property));
		}
		info["properties"] = properties;
	}
	return info;
}

Variant GaiAgentServer::_rpc_ping(const Variant &p_params) {
	(void)p_params;
	Dictionary result;
	result["pong"] = true;
	result["engine"] = String(VERSION_FULL_NAME);
	result["role"] = role;
	result["pid"] = OS::get_singleton()->get_process_id();
	result["clients"] = clients.size();
	if (current_client != nullptr) {
		result["client"] = current_client->id;
	}
	return result;
}

Variant GaiAgentServer::_rpc_event_subscribe(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	if (current_client == nullptr) {
		return _error("no client");
	}
	const Dictionary params = p_params;
	const String signal_name = params.get("signal", "");
	if (signal_name.is_empty()) {
		return _error("signal is required");
	}
	Object *object = nullptr;
	if (params.has("handle")) {
		object = _resolve_handle(params["handle"]);
	} else if (params.has("path")) {
		object = _node_for(String(params["path"]));
	} else {
		return _error("handle or path is required");
	}
	if (object == nullptr) {
		return _error("object not found");
	}
	const StringName signal = StringName(signal_name);
	if (!object->has_signal(signal)) {
		return _error("signal not found: " + signal_name);
	}
	if (current_client->subscriptions.size() >= GAI_MAX_SUBSCRIPTIONS) {
		return _error("too many subscriptions");
	}
	const ObjectID object_id = object->get_instance_id();
	const String binding_key = String::num_uint64((uint64_t)object_id) + ":" + String(signal);
	SignalBinding *binding = bindings.getptr(binding_key);
	if (binding == nullptr) {
		SignalBinding binding_value;
		binding_value.key = binding_key;
		binding_value.object_id = object_id;
		binding_value.signal = signal;
		if (Node *node = Object::cast_to<Node>(object)) {
			binding_value.path = String(node->get_path());
		}
		binding_value.callable = Callable(memnew(GaiAgentEventCallable(this, binding_key)));
		const Error error = object->connect(signal, binding_value.callable);
		if (error != OK) {
			return _error("cannot connect signal: " + itos(error));
		}
		bindings[binding_key] = binding_value;
		binding = bindings.getptr(binding_key);
	}
	const int subscription_id = next_subscription_id++;
	EventSubscriber subscriber;
	subscriber.client_id = current_client->id;
	subscriber.subscription_id = subscription_id;
	binding->subscribers.push_back(subscriber);
	Subscription subscription;
	subscription.id = subscription_id;
	subscription.binding_key = binding_key;
	current_client->subscriptions[subscription_id] = subscription;

	Dictionary result;
	result["subscription"] = subscription_id;
	result["signal"] = String(signal);
	result["handle"] = _handle(object);
	result["path"] = binding->path;
	result["last_seq"] = (int64_t)(next_event_seq - 1);
	if (params.has("since")) {
		int64_t since = params.get("since", 0);
		if (since < 0) {
			since = 0;
		}
		bool lost = false;
		if (!event_history.is_empty() && (uint64_t)since < event_history[0].seq - 1) {
			lost = true;
		}
		Array replay;
		for (const EventRecord &record : event_history) {
			if (record.object_id != object_id || record.signal != signal) {
				continue;
			}
			if (record.seq <= (uint64_t)since) {
				continue;
			}
			Dictionary event;
			event["subscription"] = subscription_id;
			event["seq"] = (int64_t)record.seq;
			event["signal"] = String(record.signal);
			event["handle"] = String::num_uint64((uint64_t)record.object_id);
			event["path"] = record.path;
			event["args"] = record.args;
			replay.push_back(event);
		}
		if (replay.size() > GAI_MAX_REPLAY) {
			while (replay.size() > GAI_MAX_REPLAY) {
				replay.remove_at(0);
			}
			lost = true;
		}
		result["replay"] = replay;
		result["lost"] = lost;
	}
	return result;
}

Variant GaiAgentServer::_rpc_event_unsubscribe(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	if (current_client == nullptr) {
		return _error("no client");
	}
	const Dictionary params = p_params;
	const int subscription_id = params.get("subscription", -1);
	Subscription *found = current_client->subscriptions.getptr(subscription_id);
	if (found == nullptr) {
		return _error("subscription not found");
	}
	const String binding_key = found->binding_key;
	SignalBinding *binding = bindings.getptr(binding_key);
	if (binding != nullptr) {
		for (int index = binding->subscribers.size() - 1; index >= 0; index--) {
			const EventSubscriber &subscriber = binding->subscribers[index];
			if (subscriber.client_id == current_client->id && subscriber.subscription_id == subscription_id) {
				binding->subscribers.remove_at(index);
			}
		}
		if (binding->subscribers.is_empty()) {
			Object *object = ObjectDB::get_instance(binding->object_id);
			if (object != nullptr && binding->callable.is_valid() && object->is_connected(binding->signal, binding->callable)) {
				object->disconnect(binding->signal, binding->callable);
			}
			bindings.erase(binding_key);
		}
	}
	current_client->subscriptions.erase(subscription_id);
	Dictionary result;
	result["subscription"] = subscription_id;
	result["removed"] = true;
	return result;
}

Variant GaiAgentServer::_rpc_event_list(const Variant &p_params) {
	(void)p_params;
	Array result;
	if (current_client == nullptr) {
		return result;
	}
	for (const KeyValue<int, Subscription> &entry : current_client->subscriptions) {
		Dictionary info;
		info["subscription"] = entry.key;
		SignalBinding *binding = bindings.getptr(entry.value.binding_key);
		if (binding == nullptr) {
			info["closed"] = true;
			result.push_back(info);
			continue;
		}
		info["signal"] = String(binding->signal);
		info["handle"] = String::num_uint64((uint64_t)binding->object_id);
		info["path"] = binding->path;
		Object *object = ObjectDB::get_instance(binding->object_id);
		info["closed"] = object == nullptr;
		if (object != nullptr) {
			info["handle"] = _handle(object);
		}
		result.push_back(info);
	}
	return result;
}

Variant GaiAgentServer::_rpc_client_list(const Variant &p_params) {
	(void)p_params;
	Array result;
	const uint64_t now = OS::get_singleton()->get_ticks_msec();
	for (const KeyValue<int, Client *> &entry : clients) {
		const Client *client = entry.value;
		Dictionary info;
		info["id"] = client->id;
		info["subscriptions"] = client->subscriptions.size();
		info["output_bytes"] = client->output.size() - client->output_offset;
		info["idle_ms"] = now > client->last_activity ? now - client->last_activity : 0;
		info["current"] = client == current_client;
		result.push_back(info);
	}
	return result;
}

Variant GaiAgentServer::_rpc_scene_tree(const Variant &p_params) {
	(void)p_params;
	if (tree == nullptr) {
		return Dictionary();
	}
	Node *root = _editor_scene_root();
	if (root == nullptr) {
		root = tree->get_current_scene();
	}
	if (root == nullptr) {
		root = tree->get_root();
	}
	if (root == nullptr) {
		return Dictionary();
	}
	Dictionary result;
	result["root"] = _node_info(root, Array());
	return result;
}

Variant GaiAgentServer::_rpc_node_get(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String path = params.get("path", "");
	Node *node = _node_for(path);
	if (node == nullptr) {
		return _error("node not found: " + path);
	}
	Array properties;
	if (params.has("properties") && params["properties"].get_type() == Variant::ARRAY) {
		properties = params["properties"];
	}
	return _node_info(node, properties);
}

Variant GaiAgentServer::_rpc_node_set(const Variant &p_params) {
	if (p_params.get_type() != Variant::DICTIONARY) {
		return _error("params must be an object");
	}
	const Dictionary params = p_params;
	const String path = params.get("path", "");
	const String property = params.get("property", "");
	if (property.is_empty() || !params.has("value")) {
		return _error("property and value are required");
	}
	Node *node = _node_for(path);
	if (node == nullptr) {
		return _error("node not found: " + path);
	}
	const Variant result = _set_property(node, property, params["value"]);
	if (result.get_type() == Variant::DICTIONARY) {
		const Dictionary dictionary = result;
		if (dictionary.has("$gai_error")) {
			return result;
		}
	}
	Dictionary out;
	out["path"] = String(node->get_path());
	out["property"] = property;
	out["value"] = result;
	return out;
}
