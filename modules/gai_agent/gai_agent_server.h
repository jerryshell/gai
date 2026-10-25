#pragma once

#include "core/io/stream_peer_tcp.h"
#include "core/io/tcp_server.h"
#include "core/object/object.h"
#include "core/variant/variant.h"
#include "modules/jsonrpc/jsonrpc.h"

class SceneTree;
class Node;

class GaiAgentServer : public Object {
	Ref<TCPServer> server;
	Ref<StreamPeerTCP> client;
	JSONRPC rpc;
	Vector<uint8_t> line_buffer;
	String token;
	uint64_t client_since = 0;
	int port = 0;
	SceneTree *tree = nullptr;

	Variant _rpc_ping(const Variant &p_params);
	Variant _rpc_scene_tree(const Variant &p_params);
	Variant _rpc_node_get(const Variant &p_params);
	Variant _rpc_node_set(const Variant &p_params);

	Dictionary _node_info(Node *p_node, const Array &p_properties);
	Variant _json_value(const Variant &p_value);
	Node *_node_for(const String &p_path);
	void _handle(const String &p_line);
	void _send(const String &p_payload);

public:
	GaiAgentServer();
	~GaiAgentServer();

	void start();
	void stop();
	void poll();
};
