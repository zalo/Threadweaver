from asyncio.tasks import sleep
from redbot.core import commands, Config
import discord
from   discord import Embed, Member, Message, RawReactionActionEvent, Client, Guild, TextChannel, CategoryChannel, Role, AllowedMentions
from   discord.ext.commands import Cog
from datetime import datetime, timedelta
import re
import logging
logger = logging.getLogger("red.Threadweaver.threadweaver")

class Threadweaver(commands.Cog):
    """Threadweaver creates temporary channels based on emoji :thread: reactions."""

    def __init__(self, bot):
        self.bot                    : Client              = bot
        self.thread_category        : CategoryChannel     = None
        self.thread_archive_channel : TextChannel         = None
        self.thread_priority        : int                 = 2147483646
        #self.user_rate_limit        : dict[int, datetime] = []

        self.config = Config.get_conf(self, identifier=786340) # THREAD in 1337
        guild_defaults = {
            "thread_category_name" : "══════ ❖ THREADS ❖ ══════",
            "thread_archive_name"  : "📓｜thread_archive",
            "thread_prefix"        : "🧵｜thread",
            "name_separator"       : "_",
            "welcome_message"      : "Welcome <@USER> to the thread!",
            "farewell_message"     : "<@USER> has left the thread!",
            "hide_threads"         : True,
            "trigger_emoji"        : "🧵",
            "prune_interval_days"  : 1,
            "min_role_to_create"   : "IMPERATOR⚔️" # This is inactive if the role doesn't exist
            #"user_threads_per_hour": 3
        }
        self.config.register_guild(**guild_defaults)

    @commands.command(name="threadweaver-settings",
                      description='Threadweaver Configuration; update them with [p]threadweaver_update_setting')
    @commands.guild_only()
    async def threadweaver_settings(self, ctx):
        """Print Threadweaver's Current Config Settings to Discord."""
        # Set up an embed-message template
        prefixes : list[str] = await self.bot.get_valid_prefixes(ctx.guild)
        embed=discord.Embed(title="Guild-level Threadweaver Settings", color=0xff4500)
        embed.set_author(name=ctx.bot.user.name, icon_url=ctx.bot.user.avatar_url)
        embed.set_thumbnail(url=ctx.guild.icon_url)
        embed.set_footer(text=f'Change a setting with "'+str(prefixes[0])+'threadweaver_update_setting [name] [value]"')

        # Iterate through the settings and add them as fields to the embed
        current_settings = await self.config.guild(ctx.guild).get_raw()
        for setting in current_settings:
            embed.add_field(name=setting, value="`"+str(current_settings[setting])+"`", inline=False)

        await ctx.send(embed=embed)

    def parse_str(self, s):
        '''Trivial helper function for parsing a string into an int or float or string'''
        try:
            return int(s)
        except ValueError:
            try:
                return float(s)
            except ValueError:
                return s

    @commands.command(name="threadweaver_update_setting",
                      description="[MOD] Update one of Threadweaver's Config Settings; see [p]threadweaver-settings")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def threadweaver_update_setting(self, ctx, settingName: str, value: str):
        """Update one of Threadweaver's Config Settings."""

        # Begin writing a message confirming the changed settings to the user
        embed=discord.Embed(title="Guild-level Threadweaver Setting Updated!", description=f"Changed Setting: ", color=0x00ff00)

        # Try Acquiring the setting, changing it, and adding it to the embed
        try:
            oldValue = await self.config.guild(ctx.guild).get_raw(settingName)
            newValue = self.parse_str(value)
            await self.config.guild(ctx.guild).set_raw(settingName, value=newValue)
            embed.add_field(name=settingName, value=str(oldValue) + " --> " + str(newValue))
        except KeyError:
            # KeyError is thrown on bad keys
            embed.add_field(name=settingName, value="This setting doesn't exist in Threadweaver!")
            return

        prefixes : list[str] = await self.bot.get_valid_prefixes(ctx.guild)
        embed.set_author(name=ctx.bot.user.name, icon_url=ctx.bot.user.avatar_url)
        embed.set_thumbnail(url=ctx.guild.icon_url)
        embed.set_footer(text=f'View all settings with "'+str(prefixes[0])+'threadweaver-settings"')
        await ctx.send(embed=embed) 

    async def make_channel_friendly(self, name : str, guild : Guild):
        '''Removes the spaces and upper-case characters from a name; not exhaustive or robust'''
        sep = await self.config.guild(guild).name_separator()
        return name.replace(" ", sep).lower()
        
    def get_thread_owner(self, guild : Guild, thread : TextChannel) -> Member :
        '''Parses thread topics to get the owning member of a thread; None if not a thread'''
        thread_topic : str = thread.topic
        if(thread_topic.startswith("[THREAD]")):
            match  : re.Match = re.search(r"<@[0-9]*?>", thread_topic)
            owner_id = int(match.group()[2:-1])
            member : Member   = discord.utils.get(guild.members, id=owner_id)
            return member
        else:
            return None

    async def archive_thread(self, channel : TextChannel):
        '''Read the first 5000 messages of the thread, mirror them to the thread archive, and delete the channel'''
        full_history : list[Message] = await channel.history(limit=5000, oldest_first=True).flatten()
        text_buffer  : str           = ""
        for thread_message in full_history:
            next_message = "<@"+str(thread_message.author.id)+">: "+thread_message.content + "\n"

            # If the text buffer is above the field limit, cut off a new message
            if(len(text_buffer) + len(next_message) > 1999):
                # Post embed
                embed=discord.Embed(description=text_buffer, color=0xff4500)
                #embed.set_author(name=thread_message.author.display_name, icon_url=thread_message.author.avatar_url)
                await self.thread_archive_channel.send(title=channel.name, embed=embed, 
                    allowed_mentions=AllowedMentions(everyone=False, users=False, roles=False))
                text_buffer = ""
                await sleep(1.01)

            text_buffer += next_message

        # Clean up the remains
        if(len(text_buffer) > 0):
            embed=discord.Embed(title=channel.name, description=text_buffer, color=0xff4500)
            await self.thread_archive_channel.send(embed=embed, 
                allowed_mentions=AllowedMentions(everyone=False, users=False, roles=False))

        # Delete the thread when we're done
        await channel.delete(reason="Archived Old Thread; Deleting Thread")

    @commands.command(name="archive-thread",
                      description="[OP] This command archives all the thread's messages to thread-archive and deletes the thread.")
    @commands.guild_only()
    async def archive_thread_command(self, ctx : Message):
        await self.verify_server_structure(ctx.guild)
        thread_owner : Member = self.get_thread_owner(ctx.guild, ctx.channel)
        if thread_owner is not None:
            if(ctx.author.id == thread_owner.id):
                await self.archive_thread(ctx.channel)
            else:
                await ctx.send("Only the thread owner <@"+str(thread_owner.id)+"> may archive this thread.")

    @commands.command(name="threadweaver-delete-all-threads",
                      description="[MOD] Deletes all of the threadweaver threads without backing them up")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def delete_all_threads_command(self, ctx : Message):
        logger.info(msg="[THREADWEAVER] Running command: Delete Threads")
        for channel in self.bot.get_all_channels():
            channel : TextChannel = channel
            if hasattr(channel, 'topic') and channel.topic is not None and channel.topic.startswith("[THREAD]"):
                logger.info(msg="[THREADWEAVER] Deleting "+str(channel)+"...")
                await channel.delete(reason="Deleting all threads via the 'threadweaver_delete_all_threads' command")
                return

    @commands.command(name="rename-thread",
                      description="[OP] This command renames the thread; no spaces!")
    @commands.guild_only()
    async def rename_thread_command(self, ctx : Message, new_name : str):
        await self.verify_server_structure(ctx.guild)
        thread_owner : Member = self.get_thread_owner(ctx.guild, ctx.channel)
        if thread_owner is not None:
            if(ctx.author.id == thread_owner.id):
                thread : TextChannel = ctx.channel
                emoji : str = await self.config.guild(ctx.guild).trigger_emoji()
                await thread.edit(name=emoji + "｜" + await self.make_channel_friendly(new_name, ctx.guild))
            else:
                await ctx.send("Only the thread owner <@"+str(thread_owner.id)+"> may rename this thread.")

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
        thread_category_name = await self.config.guild(guild).thread_category_name()
        for categoryChannel in guild.categories:
            if(str(categoryChannel) == thread_category_name):
                self.thread_category = categoryChannel

        # Create the "Threads" Category if it doesn't exist
        if(self.thread_category is None):
            logger.info(msg="[THREADWEAVER] Attempting to create the Thread Category...")
            self.thread_category = await guild.create_category(thread_category_name, reason="Setting up Threading for this Server/'Guild'")
            if self.thread_category is None:
                logger.error(msg="[THREADWEAVER] ERROR: Insufficient permissions to create Categories!  Please give me more permissions!")

        # Create the "Thread Archive" Channel if it doesn't exist
        thread_archive_name = await self.make_channel_friendly(await self.config.guild(guild).thread_archive_name(), guild)
        for channel in self.bot.get_all_channels():
            if str(channel) == thread_archive_name:
                self.thread_archive_channel : TextChannel = channel
        if(self.thread_archive_channel is None):
            logger.info(msg="[THREADWEAVER] Attempting to create the thread_archive Channel...")
            overwrites = { 
                guild.default_role : discord.PermissionOverwrite(send_messages=False),
                guild.me           : discord.PermissionOverwrite(send_messages=True, manage_permissions=True) 
            }
            self.thread_archive_channel : TextChannel = await guild.create_text_channel(thread_archive_name, 
                        topic="This channel records conversations from old threads.", category=self.thread_category,
                        overwrites = overwrites, position=2147483647, reason = "Setting up the server for Threadweaver.")
            if self.thread_archive_channel is None:
                logger.error(msg="[THREADWEAVER] ERROR: Insufficient permissions to create Channels!  Please give me more permissions!")

        # Iterate through all the existing threads, checking for the age of the latest message
        interval_days = await self.config.guild(guild).prune_interval_days()
        for channel in self.bot.get_all_channels():
            channel : TextChannel = channel
            if str(channel) != thread_archive_name and hasattr(channel, 'topic') and channel.topic is not None and channel.topic.startswith("[THREAD]"):
                latest_message : list[Message] = await channel.history(limit=1).flatten()
                # If the latest message is older than the time interval, archive the thread
                if len(latest_message) > 0 and latest_message[0].created_at < datetime.now() - timedelta(days=interval_days):
                    self.archive_thread(channel)

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
            trigger_emoji = await self.config.guild(guild).trigger_emoji()
            if payload.emoji.name == trigger_emoji:
                # If so, get the metadata about the message's member
                member  : Member      = discord.utils.get(guild.members, id=payload.user_id)

                # Ensure that the server structure contains the necessary categories
                await self.verify_server_structure(guild)

                thread_channel = None
                thread_name    = await self.make_channel_friendly(await self.config.guild(guild).thread_prefix() + " " + 
                                        str(message.author.name), guild)

                # Add the user to the thread if it already exists
                for channel in self.bot.get_all_channels():
                    if hasattr(channel, 'topic') and channel.topic is not None and channel.topic[9:13] == str(message.id)[-4:]:
                        thread_channel : TextChannel = channel

                        # Add the user to the thread if threads are hidden
                        hide_threads = await self.config.guild(guild).hide_threads()
                        if hide_threads:
                            await thread_channel.set_permissions(member, read_messages=True)

                        # Send the Welcome Message if it exists
                        welcome_message = await self.config.guild(guild).welcome_message()
                        if welcome_message and len(welcome_message) > 0:
                            await thread_channel.send(welcome_message.replace("<@USER>", "<@" + str(member.id) +">"))

                        return # End execution here
                
                # Otherwise, create the Thread Channel if it doesn't exist
                if(thread_channel is None):
                    # First, check if we should be limiting this member
                    min_role_name = await self.config.guild(guild).min_role_to_create()
                    guild_roles  : list[Role] = guild .roles
                    member_roles : list[Role] = member.roles
                    for role in guild_roles:
                        if(str(min_role_name) == str(role)):
                            if member_roles[-1].position < role.position:
                                await message.remove_reaction(trigger_emoji, member)
                                return # This user's role is too low to create a thread

                    #if member.id in self.user_rate_limit:
                    #    threads_per_hour = await self.config.guild(guild).user_threads_per_hour()
                    #    if self.user_rate_limit[member.id] > datetime.now() - timedelta(days=threads_per_hour):
                    #        await member.send(content="You can't create another thread yet; only "+str(threads_per_hour)+" per hour.")
                    #        return

                    # Set the permissions that let specific users see into this channel
                    overwrites = {
                        guild.default_role : discord.PermissionOverwrite(read_messages=(not await self.config.guild(guild).hide_threads())),
                        guild.me           : discord.PermissionOverwrite(read_messages=True, manage_permissions=True),
                        member             : discord.PermissionOverwrite(read_messages=True),
                        message.author     : discord.PermissionOverwrite(read_messages=True)
                    }
                    thread_channel : TextChannel = await guild.create_text_channel(
                        thread_name, overwrites=overwrites, topic="[THREAD] "+ str(message.id)[-4:] + " By <@" + str(message.author.id) +">: \n"+message.content, category=self.thread_category,
                        position=self.thread_priority, reason = member.display_name + " added a :thread: emoji to " + message.author.display_name + "'s message.")
                    logger.info(msg="[THREADWEAVER] "+member.display_name + " created a new thread: #" + thread_name + " from this message: \n"+message.jump_url)
                    self.thread_priority = self.thread_priority - 1 # Decrement the thread priority so new threads are on top 

                    # Create the Original Post in the Thread
                    prefixes : list[str] = await self.bot.get_valid_prefixes(guild)
                    embed = Embed(title="Discussion Thread", description=message.content, color=0x00ace6)
                    embed.set_author(name=message.author.display_name, icon_url=message.author.avatar_url)
                    embed.add_field (name="Commands", value=message.author.display_name+" may use `"+prefixes[0]+"rename-thread [NAME]` and `"+prefixes[0]+"archive-thread`\n[Jump to Original Message]("+message.jump_url+")")
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
            if payload.emoji.name == await self.config.guild(guild).trigger_emoji():
                # If so, get the metadata about the message's member
                member  : Member  = discord.utils.get(guild.members, id=payload.user_id)

                thread_channel = None
                thread_name    = await self.make_channel_friendly(await self.config.guild(guild).thread_prefix() + " " + 
                                        str(message.author.name), guild)

                # Remove the user from the thread
                for channel in self.bot.get_all_channels():
                    if hasattr(channel, 'topic') and channel.topic is not None and channel.topic[9:13] == str(message.id)[-4:]:
                        thread_channel = channel

                        # Send the Farewell Message if it exists
                        farewell_message = await self.config.guild(guild).farewell_message()
                        if farewell_message and len(farewell_message) > 0:
                            await thread_channel.send(farewell_message.replace("<@USER>", "<@" + str(member.id) +">"))
                        
                        # Reset the users' Thread-Specific Permissions to Default
                        await thread_channel.set_permissions(member, overwrite=None,
                            reason = member.display_name + " removed their :thread: emoji from " + message.author.display_name + "'s message.")
