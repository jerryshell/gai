#include "gai_agent_server.h"

#include "core/io/ip_address.h"
#include "core/io/json.h"
#include "core/object/callable_mp.h"
#include "core/object/message_queue.h"
#include "core/os/os.h"
#include "core/string/print_string.h"
#include "core/version.h"
#include "scene/main/node.h"
#include "scene/main/scene_tree.h"
#include "scene/main/window.h"
#include "core/object/script_language.h"
#include "core/variant/variant_utility.h"

GaiAgentServer::GaiAgentServer() {
	rpc.set_method("ping", callable_mp(this, &GaiAgentServer::_rpc_ping));
	rpc.set_method("scene.tree", callable_mp(this, &GaiAgentServer::_rpc_scene_tree));
	rpc.set_method("node.get", callable_mp(this, &GaiAgentServer::_rpc_node_get));
	rpc.set_method("node.set", callable_mp(this, &GaiAgentServer::_rpc_node_set));
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
	tree->connect("process_frame", callable_mp(this, &GaiAgentServer::poll));
	print_line("GAI_AGENT_LISTENING " + itos(port));
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
	client = Ref<StreamPeerTCP>();
	line_buffer.clear();
}

void GaiAgentServer::poll() {
	if (!server.is_valid() || !server->is_listening()) {
		return;
	}
	if (client.is_null()) {
		if (!server->is_connection_available()) {
			return;
		}
		client = server->take_connection();
		line_buffer.clear();
		client_since = OS::get_singleton()->get_ticks_msec();
	}
	if (client.is_null()) {
		return;
	}
	if (client->get_status() != StreamPeerTCP::STATUS_CONNECTED) {
		client = Ref<StreamPeerTCP>();
		line_buffer.clear();
		return;
	}
	if (OS::get_singleton()->get_ticks_msec() - client_since > 10000) {
		client = Ref<StreamPeerTCP>();
		line_buffer.clear();
		return;
	}

	while (client.is_valid() && client->get_available_bytes() > 0) {
		uint8_t byte = 0;
		int read = 0;
		if (client->get_partial_data(&byte, 1, read) != OK || read != 1) {
			break;
		}
		client_since = OS::get_singleton()->get_ticks_msec();
		if (byte == '\n') {
			if (!line_buffer.is_empty()) {
				const String line = String::utf8((const char *)line_buffer.ptr(), line_buffer.size()).strip_edges();
				line_buffer.clear();
				if (!line.is_empty()) {
					_handle(line);
					if (client.is_null()) {
						line_buffer.clear();
						return;
					}
				}
			}
			continue;
		}
		if (byte == '\r') {
			continue;
		}
		line_buffer.push_back(byte);
		if (line_buffer.size() > 65536) {
			line_buffer.clear();
			_send(JSON::stringify(rpc.make_response_error(JSONRPC::INVALID_REQUEST, "Request too large")) + "\n");
			client = Ref<StreamPeerTCP>();
			return;
		}
	}
}

void GaiAgentServer::_handle(const String &p_line) {
	JSON json;
	if (json.parse(p_line) != OK) {
		_send(JSON::stringify(rpc.make_response_error(JSONRPC::PARSE_ERROR, "Parse error")) + "\n");
		return;
	}
	const Variant data = json.get_data();
	if (data.get_type() != Variant::DICTIONARY) {
		_send(JSON::stringify(rpc.make_response_error(JSONRPC::INVALID_REQUEST, "Invalid request")) + "\n");
		return;
	}

	const Dictionary request = data;
	const Variant id = request.get("id", Variant());
	if (String(request.get("token", "")) != token) {
		_send(JSON::stringify(rpc.make_response_error(-32001, "Unauthorized", id)) + "\n");
		return;
	}

	const String response = rpc.process_string(p_line);
	if (!response.is_empty()) {
		_send(response + "\n");
	}
}

void GaiAgentServer::_send(const String &p_payload) {
	if (client.is_null()) {
		return;
	}
	if (client->get_status() != StreamPeerTCP::STATUS_CONNECTED) {
		client = Ref<StreamPeerTCP>();
		return;
	}
	const CharString utf8 = p_payload.utf8();
	if (client->put_data((const uint8_t *)utf8.get_data(), utf8.length()) != OK) {
		client = Ref<StreamPeerTCP>();
		return;
	}
	client = Ref<StreamPeerTCP>();
}

Node *GaiAgentServer::_node_for(const String &p_path) {
	if (tree == nullptr) {
		return nullptr;
	}
	if (p_path.is_empty()) {
		return tree->get_current_scene();
	}
	Node *root = tree->get_root();
	if (root == nullptr) {
		return nullptr;
	}
	return root->get_node_or_null(NodePath(p_path));
}

Variant GaiAgentServer::_json_value(const Variant &p_value) {
	switch (p_value.get_type()) {
		case Variant::NIL:
		case Variant::BOOL:
		case Variant::INT:
		case Variant::FLOAT:
		case Variant::STRING:
		case Variant::ARRAY:
		case Variant::DICTIONARY:
			return p_value;
		default:
			return p_value.stringify();
	}
}

Dictionary GaiAgentServer::_node_info(Node *p_node, const Array &p_properties) {
	Dictionary info;
	info["name"] = String(p_node->get_name());
	info["type"] = p_node->get_class();
	info["path"] = String(p_node->get_path());

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
	result["pid"] = OS::get_singleton()->get_process_id();
	return result;
}

Variant GaiAgentServer::_rpc_scene_tree(const Variant &p_params) {
	(void)p_params;
	if (tree == nullptr) {
		return Dictionary();
	}
	Node *root = tree->get_current_scene();
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
	Dictionary error;
	if (p_params.get_type() != Variant::DICTIONARY) {
		error["error"] = "params must be an object";
		return error;
	}
	const Dictionary params = p_params;
	const String path = params.get("path", "");
	Node *node = _node_for(path);
	if (node == nullptr) {
		error["error"] = "node not found: " + path;
		return error;
	}
	Array properties;
	if (params.has("properties") && params["properties"].get_type() == Variant::ARRAY) {
		properties = params["properties"];
	}
	return _node_info(node, properties);
}

Variant GaiAgentServer::_rpc_node_set(const Variant &p_params) {
	Dictionary error;
	if (p_params.get_type() != Variant::DICTIONARY) {
		error["error"] = "params must be an object";
		return error;
	}
	const Dictionary params = p_params;
	const String path = params.get("path", "");
	const String property = params.get("property", "");
	if (property.is_empty() || !params.has("value")) {
		error["error"] = "property and value are required";
		return error;
	}
	Node *node = _node_for(path);
	if (node == nullptr) {
		error["error"] = "node not found: " + path;
		return error;
	}

	Variant value = params["value"];
	if (value.get_type() == Variant::STRING) {
		const Variant parsed = VariantUtilityFunctions::str_to_var(value);
		if (parsed.get_type() != Variant::NIL) {
			value = parsed;
		}
	}
	node->set(property, value);

	Dictionary result;
	result["path"] = String(node->get_path());
	result["property"] = property;
	result["value"] = _json_value(node->get(property));
	return result;
}
