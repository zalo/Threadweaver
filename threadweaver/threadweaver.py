from redbot.core import commands, Config
import discord
from   discord import Embed, Member, Message, RawReactionActionEvent, Client, Guild, TextChannel, CategoryChannel
from   discord.ext.commands import Cog
from datetime import datetime, timedelta

class Threadweaver(commands.Cog):
    """Threadweaver creates temporary channels based on emoji :thread: reactions."""

    def __init__(self, bot):
        self.bot                    : Client          = bot
        self.thread_category        : CategoryChannel = None
        self.thread_archive_channel : TextChannel     = None

        self.config = Config.get_conf(self, identifier=786340) # THREAD in 1337
        guild_defaults = {
            "thread_category_name": "Threads",
            "thread_archive_name" : "thread_archive",
            "thread_prefix"       : "thread ",
            "name_separator"      : "_",
            "welcome_message"     : "Welcome <@USER> to the thread!",
            "farewell_message"    : "<@USER> has left the thread!",
            "hide_threads"        : True,
            "trigger_emoji"       : "🧵",
            "prune_interval_days" : 1
        }
        self.config.register_guild(**guild_defaults)

        # TODO: Add Configuration properties to name Channels/Categories, and pruning time

    def make_channel(self, name, guild):
        return name.replace(" ", self.config.guild(guild).name_separator()).lower()

    async def verify_server_structure(self, guild: Guild):
        """
        This function (run periodically) ensures that the server/guild is set up to use threads.
        It essentially just makes sure the Threads Category and Thread-Archive channel exists.
        It also backs up old threads into thread-archive.
        """
        # Clear these in-case the mods have deleted necessary channels
        self.thread_category        : CategoryChannel = None
        self.thread_archive_channel : TextChannel     = None

        # Verify the server is set up with a "Threads" category channel, and a "Thread Archive" Text Channel
        thread_category_name = self.config.guild(guild).thread_category_name()
        for categoryChannel in guild.categories:
            if(str(categoryChannel) == thread_category_name):
                self.thread_category = categoryChannel

        # Create the "Threads" Category if it doesn't exist
        if(self.thread_category is None):
            print("[THREADWEAVER] Attempting to create the Thread Category...")
            self.thread_category = await guild.create_category(thread_category_name, reason="Setting up Threading for this Server/'Guild'")
            if self.thread_category is None:
                print("[THREADWEAVER] ERROR: Insufficient permissions to create Categories!  Please give me more permissions!")

        # Create the "Thread Archive" Channel if it doesn't exist
        thread_archive_name = self.make_channel(self.config.guild(guild).thread_archive_name(), guild)
        for channel in self.bot.get_all_channels():
            if str(channel) == thread_archive_name:
                self.thread_archive_channel : TextChannel = channel
        if(self.thread_archive_channel is None):
            print("[THREADWEAVER] Attempting to create the thread_archive Channel...")
            self.thread_archive_channel : TextChannel = await guild.create_text_channel("Thread Archive", 
                        topic="This channel records conversations from old threads.", category=self.thread_category,
                        reason = "Setting up the server for Threadweaver.")
            if self.thread_archive_channel is None:
                print("[THREADWEAVER] ERROR: Insufficient permissions to create Channels!  Please give me more permissions!")

        # Iterate through all the existing threads, checking for the age of the latest message
        for channel in self.bot.get_all_channels():
            channel : TextChannel = channel
            if str(channel) != thread_archive_name and str(channel).startswith("thread-"):
                latest_message : Message = await channel.history(limit=1).flatten()[0]
                if latest_message.created_at < datetime.now() - timedelta(days=self.config.guild(guild).prune_interval_days()):
                    full_history : list[Message] = await channel.history(limit=1000, oldest_first=True).flatten()
                    #pass
                    # TODO: Implement old Thread Deletion
                    #           - Copy all the messages from the thread to the thread-archive
                    #           - Delete the thread?

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
            """
            Manage thread creation and user permissions.
            """
            # Get the metadata about the message's channel, and message itself
            channel : TextChannel = discord.utils.get(self.bot.get_all_channels(), id=payload.channel_id)
            message : Message     = await channel.fetch_message(payload.message_id)
            guild   : Guild       = message.guild

            # Is the emoji in the reaction a :thread:?
            if payload.emoji.name == self.config.guild(guild).trigger_emoji():
                # If so, get the metadata about the message's member
                member  : Member      = discord.utils.get(guild.members, id=payload.user_id)

                # Ensure that the server structure contains the necessary categories
                await self.verify_server_structure(guild)

                thread_channel = None
                thread_name    = self.make_channel(self.config.guild(guild).thread_prefix() + 
                                    str(message.author.name) + " " + str(message.id)[-4:], guild)

                # Add the user to the thread if it already exists
                for channel in self.bot.get_all_channels():
                    if str(channel) == thread_name:
                        thread_channel : TextChannel = channel

                        # Add the user to the thread if threads are hidden
                        if self.config.guild(guild).hide_threads():
                            await thread_channel.set_permissions(member, read_messages=True)

                        # Send the Welcome Message if it exists
                        welcome_message = self.config.guild(guild).welcome_message()
                        if welcome_message and len(welcome_message) > 0:
                            await thread_channel.send(welcome_message.replace("<@USER>", "<@" + str(member.id) +">"))
                
                # Otherwise, create the Thread Channel if it doesn't exist
                if(thread_channel is None):
                    # Set the permissions that let specific users see into this channel
                    overwrites = {
                        guild.default_role : discord.PermissionOverwrite(read_messages=(not self.config.guild(guild).hide_threads())),
                        guild.me           : discord.PermissionOverwrite(read_messages=True, manage_permissions=True),
                        member             : discord.PermissionOverwrite(read_messages=True),
                        message.author     : discord.PermissionOverwrite(read_messages=True)
                    }
                    thread_channel : TextChannel = await guild.create_text_channel(
                        thread_name, overwrites=overwrites, topic="\n\nDiscussion Thread: \n"+message.content, category=self.thread_category,
                        reason = member.display_name + " added a :thread: emoji to " + message.author.display_name + "'s message.")
                    print("[THREADWEAVER] "+member.display_name + " created a new thread: #" + thread_name + " from this message: \n"+message.jump_url)

                    # Create the Original Post in the Thread
                    embed = Embed(title="Discussion Thread", description=message.content, color=0x00ace6)
                    embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
                    embed.add_field (name="Navigation: ", value="[Jump to Original Message]("+message.jump_url+")")
                    await thread_channel.send(content="<@" + str(message.author.id) +">'s thread opened by <@" + str(member.id) +">", embed = embed)

    @Cog.listener()
    async def on_raw_reaction_remove(self, payload: RawReactionActionEvent) -> None:
            """
            Manage thread destruction and user permissions.
            """
            # Get the metadata about the message's channel, and message itself
            channel : TextChannel = discord.utils.get(self.bot.get_all_channels(), id=payload.channel_id)
            message : Message     = await channel.fetch_message(payload.message_id)
            guild   : Guild       = message.guild

            # Is the emoji in the reaction a :thread:?
            if payload.emoji.name == self.config.guild(guild).trigger_emoji():
                # If so, get the metadata about the message's member
                member  : Member       = discord.utils.get(guild.members, id=payload.user_id)

                thread_channel = None
                thread_name    = self.make_channel(self.config.guild(guild).thread_prefix() + 
                                    str(message.author.name) + " " + str(message.id)[-4:], guild)

                # Remove the user from the thread
                for channel in self.bot.get_all_channels():
                    if str(channel) == thread_name:
                        thread_channel = channel

                        # Send the Farewell Message if it exists
                        farewell_message = self.config.guild(guild).farewell_message()
                        if farewell_message and len(farewell_message) > 0:
                            await thread_channel.send(farewell_message.replace("<@USER>", "<@" + str(member.id) +">"))
                        
                        # Reset the users' Thread-Specific Permissions to Default
                        await thread_channel.set_permissions(member, overwrite=None,
                            reason = member.display_name + " removed their :thread: emoji from " + message.author.display_name + "'s message.")
