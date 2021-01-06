# Threadweaver
A Discord Redbot Cog that allows users to react to messages with the `:thread:` (🧵) emoji to create temporary channels based around that comment.

![Threadweaver Demo](Threadweaver.gif)

# Installation
Once you have a [Red Discord Bot V3](https://github.com/Cog-Creators/Red-DiscordBot) set up, execute these commands in Discord (where `[p]` is your bot's command character):
```
[p]repo add Threadweaver https://github.com/zalo/Threadweaver
[p]cog install Threadweaver threadweaver
```

Make sure your bot has permissions to manage channels and roles/permissions.

# Usage

By default, you and your users should be able to use the 🧵 emoji on any message to create threads.

The list of internal settings can be viewed via `/threadweaver_settings`.
Settings can be changed via `/threadweaver_update_setting [name] [value]`.

Thread Comment Originators can `/rename-thread [NAME]` and `/archive-thread` in their own threads.
