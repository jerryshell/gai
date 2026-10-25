#include "register_types.h"

#include "gai_agent_server.h"

#include "core/object/callable_mp.h"
#include "core/object/message_queue.h"
#include "core/os/os.h"

static GaiAgentServer *gai_agent_server = nullptr;

void initialize_gai_agent_module(ModuleInitializationLevel p_level) {
	if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
		return;
	}
	if (OS::get_singleton()->get_environment("GAI_AGENT_PORT").is_empty()) {
		return;
	}
	gai_agent_server = memnew(GaiAgentServer);
	MessageQueue::get_main_singleton()->push_callable(callable_mp(gai_agent_server, &GaiAgentServer::start));
}

void uninitialize_gai_agent_module(ModuleInitializationLevel p_level) {
	if (p_level != MODULE_INITIALIZATION_LEVEL_SCENE) {
		return;
	}
	if (gai_agent_server != nullptr) {
		memdelete(gai_agent_server);
		gai_agent_server = nullptr;
	}
}
