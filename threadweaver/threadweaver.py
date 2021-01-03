from redbot.core import commands
import discord
from   discord import Embed, Member, Message, RawReactionActionEvent, Client, Guild, TextChannel, CategoryChannel
from   discord.ext.commands import Cog

class Threadweaver(commands.Cog):
    """Threadweaver creates temporary channels based on emoji reactions."""

    def __init__(self, bot):
        self.bot                    : Client          = bot
        self.thread_category        : CategoryChannel = None
        self.thread_archive_channel : TextChannel     = None

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
        for categoryChannel in guild.categories:
            if(str(categoryChannel) == "Threads"):
                self.thread_category = categoryChannel

        # Create the "Threads" Category if it doesn't exist
        if(self.thread_category is None):
            print("Attempting to create the Thread Category...")
            self.thread_category = await guild.create_category("Threads", reason="Setting up Threading for this Server/'Guild'")
            if self.thread_category is None:
                print("ERROR: Insufficient permissions to create Categories!  Please give me more permissions!")

        # Create the "Thread Archive" Channel if it doesn't exist
        for channel in self.bot.get_all_channels():
            if str(channel) == "thread-archive":
                self.thread_archive_channel : TextChannel = channel
        if(self.thread_archive_channel is None):
            print("Attempting to create the Thread-Archive Channel...")
            self.thread_archive_channel : TextChannel = await guild.create_text_channel("Thread Archive", 
                        topic="This channel records conversations from old threads.", category=self.thread_category,
                        reason = "Setting up the server for Threadweaver.")
            if self.thread_archive_channel is None:
                print("ERROR: Insufficient permissions to create Channels!  Please give me more permissions!")

        # Iterate through all the existing threads, checking for the age of the latest message
        for channel in self.bot.get_all_channels():
            if str(channel) != "thread-archive" and str(channel).startswith("thread-"):
                pass
                # TODO: Implement Thread Deletion - Consolidate messages to thread-archive

    @Cog.listener()
    async def on_raw_reaction_add(self, payload: RawReactionActionEvent) -> None:
            """
            Manage thread creation and user permissions.
            """
            # Is the emoji in the reaction a :thread:?
            if payload.emoji.name == "🧵":
                # If so, get the metadata about the message's channel, message itself, and member
                channel : TextChannel = discord.utils.get(self.bot.get_all_channels(), id=payload.channel_id)
                message : Message     = await channel.fetch_message(payload.message_id)
                guild   : Guild       = message.guild
                member  : Member      = discord.utils.get(guild.members, id=payload.user_id)

                # Ensure that the server structure contains the necessary categories
                await self.verify_server_structure(guild)

                thread_channel = None
                thread_name    = ("thread-" + str(message.author.name) + "-" + str(message.id)[-4:]).lower()

                # Add the user to the thread if it already exists
                for channel in self.bot.get_all_channels():
                    if str(channel) == thread_name:
                        thread_channel : TextChannel = channel
                        await thread_channel.set_permissions(member, read_messages=True)
                        await thread_channel.send('Welcome <@' + str(member.id) +"> to the thread!")
                
                # Otherwise, create the Thread Channel if it doesn't exist
                if(thread_channel is None):
                    # Set the permissions that let specific users see into this channel
                    overwrites = {
                        guild.default_role : discord.PermissionOverwrite(read_messages=False),
                        guild.me           : discord.PermissionOverwrite(read_messages=True, manage_permissions=True),
                        member             : discord.PermissionOverwrite(read_messages=True),
                        message.author     : discord.PermissionOverwrite(read_messages=True)
                    }
                    thread_channel : TextChannel = await guild.create_text_channel(
                        thread_name, overwrites=overwrites, topic="\n\nDiscussion Thread: \n"+message.content, category=self.thread_category,
                        reason = member.display_name + " added a :thread: emoji to " + message.author.display_name + "'s message.")
                    print(member.display_name + " created a new thread: #" + thread_name + " from this message: \n"+message.jump_url)

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
            # Is the emoji in the reaction a :thread:?
            if payload.emoji.name == "🧵":
                # If so, get the metadata about the message's channel, message itself, and member
                channel : TextChannel  = discord.utils.get(self.bot.get_all_channels(), id=payload.channel_id)
                message : Message      = await channel.fetch_message(payload.message_id)
                guild   : Guild        = message.guild
                member  : Member       = discord.utils.get(guild.members, id=payload.user_id)

                thread_channel = None
                thread_name    = ("thread-" + str(message.author.name) + "-" + str(message.id)[-4:]).lower()

                # Remove the user from the thread
                for channel in self.bot.get_all_channels():
                    if str(channel) == thread_name:
                        thread_channel = channel
                        await thread_channel.send("<@" + str(member.id) +"> has left the thread!")
                        await thread_channel.set_permissions(member, overwrite=None,
                            reason = member.display_name + " removed their :thread: emoji from " + message.author.display_name + "'s message.")
