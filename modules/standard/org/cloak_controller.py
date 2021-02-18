import time

from core.aochat.server_packets import PublicChannelMessage
from core.chat_blob import ChatBlob
from core.command_param_types import Const, Int
from core.conn import Conn
from core.decorators import instance, command, event, timerevent
from core.dict_object import DictObject
from core.public_channel_service import PublicChannelService


@instance()
class CloakController:
    MESSAGE_SOURCE = "cloak_reminder"
    CLOAK_EVENT = "cloak"

    def inject(self, registry):
        self.bot = registry.get_instance("bot")
        self.db = registry.get_instance("db")
        self.util = registry.get_instance("util")
        self.text = registry.get_instance("text")
        self.character_service = registry.get_instance("character_service")
        self.command_alias_service = registry.get_instance("command_alias_service")
        self.timer_controller = registry.get_instance("timer_controller", is_optional=True)
        self.event_service = registry.get_instance("event_service")
        self.access_service = registry.get_instance("access_service")
        self.message_hub_service = registry.get_instance("message_hub_service")

    def pre_start(self):
        self.bot.register_packet_handler(PublicChannelMessage.id, self.handle_public_message)
        self.event_service.register_event_type(self.CLOAK_EVENT)
        self.message_hub_service.register_message_source(self.MESSAGE_SOURCE)

    def start(self):
        self.db.exec("CREATE TABLE IF NOT EXISTS cloak_status (char_id INT NOT NULL, action VARCHAR(10) NOT NULL, created_at INT NOT NULL, org_id INT NOT NULL)")
        self.command_alias_service.add_alias("city", "cloak")

    @command(command="cloak", params=[Const("history"), Int("org_id")], access_level="org_member",
             description="Shows the cloak history")
    def cloak_history_command(self, request, _, org_id):
        data = self.db.query("SELECT c.*, p.name FROM cloak_status c LEFT JOIN player p ON c.char_id = p.char_id "
                             "WHERE c.org_id = ? ORDER BY created_at DESC LIMIT 20", [org_id])

        blob = ""
        for row in data:
            action = "<green>on</green>" if row.action == "on" else "<orange>off</orange>"
            blob += "%s turned the device %s at %s.\n" % (row.name, action, self.util.format_datetime(row.created_at))

        conn = self.bot.get_conn_by_org_id(org_id)
        org_name = conn.get_org_name()
        return ChatBlob(f"Cloak History for {org_name}", blob)

    @command(command="cloak", params=[], access_level="org_member",
             description="Shows the cloak status")
    def cloak_command(self, request):
        t = int(time.time())

        blob = ""
        for _id, conn in self.bot.get_conns(lambda x: x.is_main and x.org_id):
            row = self.db.query_single("SELECT c.char_id, c.action, c.created_at, p.name FROM cloak_status c LEFT JOIN player p ON c.char_id = p.char_id "
                                       "WHERE c.org_id = ? ORDER BY created_at DESC LIMIT 1", [conn.org_id])

            org_name = conn.get_org_name()
            if row:
                action = "<green>on</green>" if row.action == "on" else "<orange>off</orange>"
                time_str = self.util.time_to_readable(t - row.created_at)
                history_link = self.text.make_tellcmd("History", f"cloak history {conn.org_id}")
                blob += f"{org_name} - {action} [{time_str} ago] {history_link}\n"
            else:
                blob += f"{org_name} - Unknown status\n"

        return ChatBlob(f"Cloak Status", blob)

    @event(event_type=CLOAK_EVENT, description="Record when the city cloak is turned off and on", is_hidden=True)
    def city_cloak_event(self, event_type, event_data):
        self.db.exec("INSERT INTO cloak_status (char_id, action, created_at, org_id) VALUES (?, ?, ?, ?)",
                     [event_data.char_id, event_data.action, int(time.time()), event_data.conn.org_id])

    @timerevent(budatime="15m", description="Reminds the players when cloak can be raised")
    def cloak_reminder_event(self, event_type, event_data):
        messages = []
        for _id, conn in self.bot.get_conns(lambda x: x.is_main and x.org_id):
            row = self.db.query_single("SELECT c.*, p.name FROM cloak_status c LEFT JOIN player p ON c.char_id = p.char_id "
                                       "WHERE c.org_id = ? ORDER BY created_at DESC LIMIT 1", [conn.org_id])
            if row:
                one_hour = 3600
                t = int(time.time())
                time_until_change = row.created_at + one_hour - t
                if row.action == "off" and 0 >= time_until_change > (one_hour * 6 * -1):
                    time_str = self.util.time_to_readable(t - row.created_at)
                    org_name = conn.get_org_name()
                    messages.append(f"The cloaking device for org <highlight>{org_name}</highlight> is <orange>disabled</orange> but can be enabled. "
                                    f"<highlight>{row.name}</highlight> disabled it {time_str} ago.")

        if messages:
            self.message_hub_service.send_message(self.MESSAGE_SOURCE, None, None, "\n".join(messages))

    @event(event_type=CLOAK_EVENT, description="Set a timer for when cloak can be raised and lowered")
    def city_cloak_timer_event(self, event_type, event_data):
        if event_data.action == "off":
            timer_name = f"Raise City Cloak ({event_data.conn.get_org_name()})"
        elif event_data.action == "on":
            timer_name = f"Lower City Cloak ({event_data.conn.get_org_name()})"
        else:
            raise Exception(f"Unknown cloak action '{event_data.action}'")

        self.timer_controller.add_timer(timer_name, event_data.char_id, PublicChannelService.ORG_CHANNEL_COMMAND, int(time.time()), 3600)

    def get_cloak_status(self, row):
        one_hour = 3600
        time_until_change = row.created_at + one_hour - int(time.time())
        time_string = self.util.time_to_readable(time_until_change)
        conn = self.bot.get_conn_by_org_id(row.org_id)
        org_name = "Unknown"
        if conn:
            org_name = conn.get_org_name()

        if row.action == "off":
            if time_until_change <= 0:
                msg = f"The cloaking device for org <highlight>{org_name}</highlight> is <orange>disabled</orange>. It is possible to enable it."
            else:
                msg = f"The cloaking device for org <highlight>{org_name}</highlight>  is <orange>disabled</orange>. It is possible to enable it in {time_string}."
        else:
            if time_until_change <= 0:
                msg = f"The cloaking device for org <highlight>{org_name}</highlight> is <green>enabled</green>. It is possible to disable it."
            else:
                msg = f"The cloaking device for org <highlight>{org_name}</highlight> is <green>enabled</green>. It is possible to disable it in {time_string}."

        return msg

    def handle_public_message(self, conn: Conn, packet: PublicChannelMessage):
        if not conn.is_main:
            return

        extended_message = packet.extended_message
        if extended_message and extended_message.category_id == 1001 and extended_message.instance_id == 1:
            char_name = extended_message.params[0]
            char_id = self.character_service.resolve_char_to_id(char_name)
            action = extended_message.params[1]
            self.event_service.fire_event(self.CLOAK_EVENT, DictObject({"char_id": char_id, "name": char_name, "action": action, "conn": conn}))
