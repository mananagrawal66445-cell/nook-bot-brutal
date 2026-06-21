import io
import textwrap
import traceback
from contextlib import redirect_stdout
import discord
from discord.ext import commands

class OwnerCog(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self._last_result = None

    def cleanup_code(self, content: str) -> str:
        """Automatically removes code blocks from the input code."""
        # Remove triple backticks at the beginning and end
        if content.startswith('```') and content.endswith('```'):
            return '\n'.join(content.split('\n')[1:-1])

        # Remove single backticks
        return content.strip('` \n')

    @commands.command(name=".eval")
    @commands.is_owner()  # Restricts the command strictly to the bot creator/owner
    async def eval_command(self, ctx, *, body: str):
        """Evaluates arbitrary Python code. Restricted to the bot owner."""
        env = {
            'bot': self.bot,
            'ctx': ctx,
            'channel': ctx.channel,
            'author': ctx.author,
            'guild': ctx.guild,
            'message': ctx.message,
            '_': self._last_result
        }

        # Include all globals in the execution environment
        env.update(globals())

        body = self.cleanup_code(body)
        stdout = io.StringIO()

        # Wrap the code inside an async function definition
        to_compile = f'async def func():\n{textwrap.indent(body, "  ")}'

        try:
            # Compile and execute function definition
            exec(to_compile, env)
        except Exception as e:
            return await ctx.send(f'```py\n{e.__class__.__name__}: {e}\n```')

        func = env['func']
        try:
            # Run the function and capture stdout
            with redirect_stdout(stdout):
                ret = await func()
        except Exception:
            value = stdout.getvalue()
            await ctx.send(f'```py\n{value}{traceback.format_exc()}\n```')
        else:
            value = stdout.getvalue()
            try:
                # Add checkmark reaction to command message on success
                await ctx.message.add_reaction('✅')
            except discord.HTTPException:
                pass

            # Respond with stdout and the return value if any
            if ret is None:
                if value:
                    # If output exceeds Discord's 2000 character limit, send as file
                    if len(value) > 1900:
                        fp = io.BytesIO(value.encode('utf-8'))
                        await ctx.send("Output too long, sending as file:", file=discord.File(fp, 'output.txt'))
                    else:
                        await ctx.send(f'```py\n{value}\n```')
            else:
                self._last_result = ret
                out_content = f'{value}{ret}'
                if len(out_content) > 1900:
                    fp = io.BytesIO(out_content.encode('utf-8'))
                    await ctx.send("Output too long, sending as file:", file=discord.File(fp, 'output.txt'))
                else:
                    await ctx.send(f'```py\n{out_content}\n```')

    @commands.command(name=".sync")
    @commands.is_owner()
    async def sync_commands(self, ctx):
        """Syncs all slash commands globally. Restricted to the bot owner."""
        try:
            synced = await self.bot.tree.sync()
            await ctx.send(f"✅ Successfully synced {len(synced)} application commands globally.")
        except Exception as e:
            await ctx.send(f"❌ Failed to sync application commands: {e}")

async def setup(bot):
    await bot.add_cog(OwnerCog(bot))
