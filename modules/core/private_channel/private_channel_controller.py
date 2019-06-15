from core.ban_service import BanService
from core.command_param_types import Character
from core.decorators import instance, command, event
from core.dict_object import DictObject
from core.private_channel_service import PrivateChannelService


@instance()
class PrivateChannelController:
    RELAY_CHANNEL_PREFIX = "[Private]"
    RELAY_HUB_SOURCE = "private_channel"

    def inject(self, registry):
        self.bot = registry.get_instance("bot")
        self.private_channel_service = registry.get_instance("private_channel_service")
        self.character_service = registry.get_instance("character_service")
        self.job_scheduler = registry.get_instance("job_scheduler")
        self.access_service = registry.get_instance("access_service")
        self.relay_hub_service = registry.get_instance("relay_hub_service")
        self.ban_service = registry.get_instance("ban_service")
        self.log_controller = registry.get_instance("log_controller")
        self.online_controller = registry.get_instance("online_controller")

    def start(self):
        self.relay_hub_service.register_relay(self.RELAY_HUB_SOURCE, self.handle_incoming_relay_message)

    @command(command="join", params=[], access_level="all",
             description="Join the private channel")
    def join_cmd(self, request):
        self.private_channel_service.invite(request.sender.char_id)

    @command(command="leave", params=[], access_level="all",
             description="Leave the private channel")
    def leave_cmd(self, request):
        self.private_channel_service.kick(request.sender.char_id)

    @command(command="invite", params=[Character("character")], access_level="all",
             description="Invite a character to the private channel")
    def invite_cmd(self, request, char):
        if char.char_id:
            if self.private_channel_service.in_private_channel(char.char_id):
                return "<highlight>%s<end> is already in the private channel." % char.name
            else:
                self.bot.send_private_message(char.char_id, "You have been invited to the private channel by <highlight>%s<end>." % request.sender.name)
                self.private_channel_service.invite(char.char_id)
                return "You have invited <highlight>%s<end> to the private channel." % char.name
        else:
            return "Could not find character <highlight>%s<end>." % char.name

    @command(command="kick", params=[Character("character")], access_level="admin",
             description="Kick a character from the private channel")
    def kick_cmd(self, request, char):
        if char.char_id:
            if not self.private_channel_service.in_private_channel(char.char_id):
                return "<highlight>%s<end> is not in the private channel." % char.name
            else:
                # TODO use request.sender.access_level and char.access_level
                if self.access_service.has_sufficient_access_level(request.sender.char_id, char.char_id):
                    self.bot.send_private_message(char.char_id, "You have been kicked from the private channel by <highlight>%s<end>." % request.sender.name)
                    self.private_channel_service.kick(char.char_id)
                    return "You have kicked <highlight>%s<end> from the private channel." % char.name
                else:
                    return "You do not have the required access level to kick <highlight>%s<end>." % char.name
        else:
            return "Could not find character <highlight>%s<end>." % char.name

    @command(command="kickall", params=[], access_level="admin",
             description="Kick all characters from the private channel")
    def kickall_cmd(self, request):
        self.bot.send_private_channel_message("Everyone will be kicked from this channel in 10 seconds. [by <highlight>%s<end>]" % request.sender.name)
        self.job_scheduler.delayed_job(lambda t: self.private_channel_service.kickall(), 10)

    @event(event_type=BanService.BAN_ADDED_EVENT, description="Kick characters from the private channel who are banned", is_hidden=True)
    def ban_added_event(self, event_type, event_data):
        self.private_channel_service.kick(event_data.char_id)

    @event(event_type=PrivateChannelService.PRIVATE_CHANNEL_MESSAGE_EVENT, description="Relay messages from the private channel to the relay hub", is_hidden=True)
    def handle_private_channel_message_event(self, event_type, event_data):
        if event_data.char_id == self.bot.char_id or self.ban_service.get_ban(event_data.char_id):
            return

        char_name = self.character_service.resolve_char_to_name(event_data.char_id)
        sender = DictObject({"char_id": event_data.char_id, "name": char_name})
        message = "%s %s: %s" % (self.RELAY_CHANNEL_PREFIX, char_name, event_data.message)

        self.relay_hub_service.send_message(self.RELAY_HUB_SOURCE, sender, message)

    @event(event_type=PrivateChannelService.JOINED_PRIVATE_CHANNEL_EVENT, description="Notify when a character joins the private channel")
    def handle_private_channel_joined_event(self, event_type, event_data):
        char_name = self.character_service.resolve_char_to_name(event_data.char_id)
        sender = DictObject({"char_id": event_data.char_id, "name": char_name})
        message = "%s has joined the private channel. %s" % (self.online_controller.get_char_info_display(event_data.char_id),
                                                             self.log_controller.get_logon(event_data.char_id))

        self.relay_hub_service.send_message(self.RELAY_HUB_SOURCE, sender, message)

    @event(event_type=PrivateChannelService.LEFT_PRIVATE_CHANNEL_EVENT, description="Notify when a character leaves the private channel")
    def handle_private_channel_left_event(self, event_type, event_data):
        char_name = self.character_service.resolve_char_to_name(event_data.char_id)
        sender = DictObject({"char_id": event_data.char_id, "name": char_name})
        message = "<highlight>%s<end> has left the private channel. %s" % (char_name, self.log_controller.get_logoff(event_data.char_id))

        self.relay_hub_service.send_message(self.RELAY_HUB_SOURCE, sender, message)

    def handle_incoming_relay_message(self, ctx):
        message = ctx.message

        self.bot.send_private_channel_message(message, fire_outgoing_event=False)
