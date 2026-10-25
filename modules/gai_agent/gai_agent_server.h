#pragma once

#include "core/io/stream_peer_tcp.h"
#include "core/io/tcp_server.h"
#include "core/object/object.h"
#include "core/object/ref_counted.h"
#include "core/templates/hash_map.h"
#include "core/templates/hash_set.h"
#include "core/variant/variant.h"
#include "modules/jsonrpc/jsonrpc.h"

class SceneTree;
class Node;
struct MethodInfo;
struct PropertyInfo;

class GaiAgentServer : public Object {
	Ref<TCPServer> server;
	Ref<StreamPeerTCP> client;
	JSONRPC rpc;
	Vector<uint8_t> line_buffer;
	Vector<uint8_t> output_buffer;
	int output_offset = 0;
	String token;
	int port = 0;
	uint64_t client_deadline = 0;
	SceneTree *tree = nullptr;
	HashMap<ObjectID, Ref<RefCounted>> refs;
	HashSet<ObjectID> created;
	int step_frames = 0;
	bool step_restore_pause = false;

	Variant _rpc_ping(const Variant &p_params);
	Variant _rpc_api_methods(const Variant &p_params);
	Variant _rpc_api_singletons(const Variant &p_params);
	Variant _rpc_classdb_classes(const Variant &p_params);
	Variant _rpc_classdb_class(const Variant &p_params);
	Variant _rpc_classdb_instantiate(const Variant &p_params);
	Variant _rpc_object_get(const Variant &p_params);
	Variant _rpc_object_set(const Variant &p_params);
	Variant _rpc_object_call(const Variant &p_params);
	Variant _rpc_object_properties(const Variant &p_params);
	Variant _rpc_object_methods(const Variant &p_params);
	Variant _rpc_object_signals(const Variant &p_params);
	Variant _rpc_object_singleton(const Variant &p_params);
	Variant _rpc_object_free(const Variant &p_params);
	Variant _rpc_scene_tree(const Variant &p_params);
	Variant _rpc_scene_current(const Variant &p_params);
	Variant _rpc_scene_change(const Variant &p_params);
	Variant _rpc_node_get(const Variant &p_params);
	Variant _rpc_node_set(const Variant &p_params);
	Variant _rpc_node_create(const Variant &p_params);
	Variant _rpc_node_delete(const Variant &p_params);
	Variant _rpc_node_reparent(const Variant &p_params);
	Variant _rpc_node_add_child(const Variant &p_params);
	Variant _rpc_resource_load(const Variant &p_params);
	Variant _rpc_resource_save(const Variant &p_params);
	Variant _rpc_project_get(const Variant &p_params);
	Variant _rpc_project_set(const Variant &p_params);
	Variant _rpc_project_save(const Variant &p_params);
	Variant _rpc_run_status(const Variant &p_params);
	Variant _rpc_run_pause(const Variant &p_params);
	Variant _rpc_run_resume(const Variant &p_params);
	Variant _rpc_run_step(const Variant &p_params);
	Variant _rpc_run_time_scale(const Variant &p_params);
	Variant _rpc_run_quit(const Variant &p_params);
	Variant _rpc_input_action(const Variant &p_params);
	Variant _rpc_input_key(const Variant &p_params);
	Variant _rpc_input_mouse(const Variant &p_params);
	Variant _rpc_render_screenshot(const Variant &p_params);

	Object *_resolve_handle(const Variant &p_value);
	String _handle(Object *p_object);
	Variant _to_variant(const Variant &p_value, Variant::Type p_type, String &r_error);
	Dictionary _object_info(Object *p_object);
	Dictionary _error(const String &p_message);
	Dictionary _property_dict(const PropertyInfo &p_info);
	Dictionary _method_dict(const MethodInfo &p_info);
	bool _property_for(Object *p_object, const String &p_name, PropertyInfo &r_info);
	Variant _set_property(Object *p_object, const String &p_name, const Variant &p_value);

	bool _editor_mode() const;
	Node *_editor_scene_root();
	String _editor_refusal(const Dictionary &p_params, const String &p_what);

	Dictionary _node_info(Node *p_node, const Array &p_properties);
	Variant _json_value(const Variant &p_value, int p_depth = 0);
	Node *_node_for(const String &p_path);
	void _handle(const String &p_line);
	void _send(const String &p_payload);
	void _drop_client();

public:
	GaiAgentServer();
	~GaiAgentServer();

	void start();
	void stop();
	void poll();
};
