/***************************************************************************/
/*  steam_packet_peer.h                                                    */
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

// Include Godot headers
#ifdef GDEXTENSION
#include <godot_cpp/classes/packet_peer_extension.hpp>
#include <godot_cpp/templates/list.hpp>

#include <godot_cpp/core/ext_wrappers.gen.inc>
using namespace godot;
#else
#include "core/version.h"
#if VERSION_MAJOR == 4 && VERSION_MINOR > 6
#include "core/extension/ext_wrappers.gen.h"
#endif
#include "core/io/packet_peer.h"
#include "core/object/class_db.h"
#include "core/templates/list.h"
#endif

// Include Steamworks API headers
#include "steam/steam_api_flat.h"

// Include GodotSteam headers
#include "godotsteam_project_settings.h"


#ifdef GDEXTENSION
class SteamPacketPeer : public PacketPeerExtension {
	GDCLASS(SteamPacketPeer, PacketPeerExtension);
#else
class SteamPacketPeer : public PacketPeer {
	GDCLASS(SteamPacketPeer, PacketPeer);
#endif


public:
	enum PeerState {
		STATE_NONE = k_ESteamNetworkingConnectionState_None,
		STATE_CONNECTING = k_ESteamNetworkingConnectionState_Connecting,
		STATE_FINDING_ROUTE = k_ESteamNetworkingConnectionState_FindingRoute,
		STATE_CONNECTED = k_ESteamNetworkingConnectionState_Connected,
		STATE_CLOSED_BY_PEER = k_ESteamNetworkingConnectionState_ClosedByPeer,
		STATE_PROBLEM_DETECTED_LOCALLY = k_ESteamNetworkingConnectionState_ProblemDetectedLocally,
		STATE_FIN_WAIT = k_ESteamNetworkingConnectionState_FinWait,
		STATE_LINGER = k_ESteamNetworkingConnectionState_Linger,
		STATE_DEAD = k_ESteamNetworkingConnectionState_Dead,
	};

	struct PeerIDPacket {
		uint32_t peer_id = 0;
	};


private:
	PeerState state = STATE_NONE;
	uint64_t steam_id = 0;
	HSteamNetConnection connection_handle = k_HSteamNetConnection_Invalid;
	uint32_t peer_id = 0;
	int configured_lanes = 1;

	List<SteamNetworkingMessage_t *> packet_queue;
	SteamNetworkingMessage_t *last_packet = nullptr;


public:
	SteamPacketPeer();
	~SteamPacketPeer();

	void set_steam_id(uint64_t p_steam_id);
	uint64_t get_steam_id() const;

	void set_connection_handle(HSteamNetConnection p_handle);
	HSteamNetConnection get_connection_handle() const;

	void set_peer_id(uint32_t p_peer_id);
	uint32_t get_peer_id() const;

	void set_state(PeerState p_state);
	PeerState get_state() const;

	MODBIND0RC(int, get_available_packet_count);
	MODBIND0RC(int, get_max_packet_size);

#ifdef GDEXTENSION
	Error get_packet(const uint8_t **r_buffer, int &r_buffer_size);
	Error put_packet(const uint8_t *p_buffer, int p_buffer_size);
	virtual Error _get_packet(const uint8_t **r_buffer, int *r_buffer_size) override {
		int ret_size = 0;
		Error err = get_packet(r_buffer, ret_size);
		*r_buffer_size = ret_size;
		return err;
	}
	virtual Error _put_packet(const uint8_t *p_buffer, int p_buffer_size) override {
		return put_packet(p_buffer, p_buffer_size);
	}
#else
	virtual Error get_packet(const uint8_t **r_buffer, int &r_buffer_size) override;
	virtual Error put_packet(const uint8_t *p_buffer, int p_buffer_size) override;
#endif

	Error send(int p_channel, const uint8_t *p_data, int p_size, int p_flags);
	Error ping(uint32_t p_peer_id);
	Error process_ping(SteamNetworkingMessage_t *p_packet);

	void queue_packet(SteamNetworkingMessage_t *p_packet);

	void disconnect_peer(bool p_force = false);


protected:
	static void _bind_methods();
};


VARIANT_ENUM_CAST(SteamPacketPeer::PeerState);
