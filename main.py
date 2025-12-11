
import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import pandas as pd

load_dotenv()
token = str(os.getenv('DISCORD_TOKEN'))
handler = logging.FileHandler(filename='discord.log',encoding='utf-8',mode='w')
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
log_channels = {}

badwords = "bdwrds.csv"
warnings = "warning.csv"

if os.path.exists(badwords):
    df = pd.read_csv(badwords)
else:
    df = pd.DataFrame(columns=["server_id", "input"])
if os.path.exists(warnings):
    warnings_df = pd.read_csv(warnings)
else:
    warnings_df = pd.DataFrame(columns=["server_id", "user_id", "username", "warnings"])


bot = commands.Bot(command_prefix='#',intents=intents)


@bot.event
async def on_ready():
    print(f'{bot.user} is ready')


@bot.command()
async def savebdwrds(ctx, *, user_input: str):
    global df
    new_entry = {
        "server_id": ctx.guild.id,
        "input": user_input
    }
    df = pd.concat([df, pd.DataFrame([new_entry])], ignore_index=True)
    df.to_csv(badwords, index=False)
    await ctx.send(f"✅ Input saved for server **`{ctx.guild.name}`**!")


@bot.command()
async def showbdwrds(ctx):
    """Show all inputs for this server."""
    global df
    server_data = df[df["server_id"] == ctx.guild.id]
    if server_data.empty:
        await ctx.send("No inputs saved yet for this server.")
    else:
        # Build a readable string
        response = "\n".join(
            f"{row['input']}" for _, row in server_data.iterrows()
        )
        await ctx.send(f"📂 Saved inputs for ***{ctx.guild.name}***:\n**```{response}```**")



@bot.event
async def on_message(message):
    global df, warnings_df


    if message.author.bot:
        return
    if message.author.guild_permissions.administrator:
        await bot.process_commands(message)
        return

    server_inputs = df[df["server_id"] == message.guild.id]["input"].tolist()


    for word in server_inputs:
        if word.lower() in message.content.lower():
            await message.delete()  


            user_row = warnings_df[
                (warnings_df["server_id"] == message.guild.id) &
                (warnings_df["user_id"] == message.author.id)
            ]

            if user_row.empty:

                new_entry = {
                    "server_id": message.guild.id,
                    "user_id": message.author.id,
                    "username": str(message.author),
                    "warnings": 1
                }
                warnings_df = pd.concat([warnings_df, pd.DataFrame([new_entry])], ignore_index=True)
                await message.channel.send(f"⚠️ {message.author.mention}, this is your **first warning**!")
            else:

                warnings_df.loc[user_row.index, "warnings"] += 1
                count = int(warnings_df.loc[user_row.index, "warnings"].values[0])

                if count < 3:
                    await message.channel.send(f"⚠️ {message.author.mention}, warning {count}/3!")
                else:
                    await message.channel.send(f"⛔ {message.author.mention} has reached 3 warnings and will be banned.")
                    await message.guild.ban(message.author, reason="Reached 3 warnings")

            warnings_df.to_csv("warnings.csv", index=False)
            break  


    await bot.process_commands(message)


@bot.command()
async def showwarnings(ctx, member: discord.Member = None):
    global warnings_df
    if member is None:
        member = ctx.author

    user_row = warnings_df[
        (warnings_df["server_id"] == ctx.guild.id) &
        (warnings_df["user_id"] == member.id)
    ]

    if user_row.empty:
        await ctx.send(f"{member.mention} has no warnings.")
    else:
        count = int(user_row["warnings"].values[0])
        await ctx.send(f"{member.mention} has {count} warning(s).")


@bot.command()
@commands.has_permissions(manage_messages=True)
async def removewarning(ctx, member: discord.Member):
    """Remove one warning from a user in this server."""
    global warnings_df
    user_row = warnings_df[
        (warnings_df["server_id"] == ctx.guild.id) &
        (warnings_df["user_id"] == member.id)
    ]

    if user_row.empty:
        await ctx.send(f"{member.mention} has no warnings.")
    else:
        current = int(user_row["warnings"].values[0])
        new_count = max(0, current - 1)
        warnings_df.loc[user_row.index, "warnings"] = new_count
        warnings_df.to_csv("warnings.csv", index=False)
        await ctx.send(f"✅ Removed one warning from {member.mention}. Now at {new_count} warning(s).")


@bot.command()
@commands.has_permissions(manage_guild=True)
async def setlogch(ctx, channel: discord.TextChannel):
    log_channels[ctx.guild.id] = channel.id
    await ctx.send(f"✅ Log channel set to {channel.mention}")


@bot.command()
@commands.has_permissions(manage_messages=True)
async def removeword(ctx, *, word: str):
    """Remove a forbidden word from this server's list."""
    global df
    before_count = len(df)
    df = df[
        ~((df["server_id"] == ctx.guild.id) & (df["input"].str.lower() == word.lower()))
    ]
    after_count = len(df)

    if before_count == after_count:
        await ctx.send(f"⚠️ Word `{word}` was not found in this server's forbidden list.")
    else:
        df.to_csv(badwords, index=False)
        await ctx.send(f"✅ Word `{word}` removed from this server's forbidden list.")


@bot.event
async def on_message_delete(message):
    if message.author.bot:
        return

    channel_id = log_channels.get(message.guild.id)
    if channel_id:
        log_channel = message.guild.get_channel(channel_id)
        if log_channel:
            embed = discord.Embed(
                title="Message Deleted",
                description=f"**Author:** {message.author}\n**Channel:** {message.channel.mention}",
                color=discord.Color.red()
            )
            embed.add_field(name="Content", value=message.content or "No text content", inline=False)
            embed.set_footer(text=f"Message ID: {message.id}")

            await log_channel.send(embed=embed)

@bot.event
async def on_message_edit(before, after):
    
    if before.author.bot or before.content == after.content:
        return

    channel_id = log_channels.get(before.guild.id)
    if channel_id:
        log_channel = before.guild.get_channel(channel_id)
        if log_channel:
            embed = discord.Embed(
                title="Message Edited",
                description=f"**Author:** {before.author}\n**Channel:** {before.channel.mention}",
                color=discord.Color.orange()
            )
            embed.add_field(name="Before", value=before.content or "No text content", inline=False)
            embed.add_field(name="After", value=after.content or "No text content", inline=False)
            embed.set_footer(text=f"Message ID: {before.id}")

            await log_channel.send(embed=embed)


bot.run(token)