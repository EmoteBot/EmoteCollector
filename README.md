# Emoji Connoisseur

Emoji Connoisseur lets you use emotes you don't have, even without Nitro.

Once you've found an emoji you'd like to use, just send it as if you were sending a regular Discord emoji (e.g. :speedtest:).
It will be detected and sent by the bot. Using semicolons (;thonkang;) is also supported.

Note that this bot is still in <em>beta</em> status, and is subject to change at any time until it becomes stable.

- To add the bot to your server, visit https://discordapp.com/oauth2/authorize?client_id=405953712113057794&scope=bot&permissions=355392.
- To run your own instance of the bot, read [the installation guide](INSTALLATION.md).
- If you'd like to help out with the code, read [CONTRIBUTING.md](CONTRIBUTING.md).

## Commands

<p>
To add an emote:
<ul>
<li><code>ec/add <img class="emote" src="https://cdn.discordapp.com/emojis/407347328606011413.png?v=1&size=32" alt=":thonkang:" title=":thonkang:"></code> (if you already have that emote)</li>
<li><code>ec/add rollsafe https://image.noelshack.com/fichiers/2017/06/1486495269-rollsafe.png</code></li>
<li><code>ec/add speedtest https://cdn.discordapp.com/emojis/379127000398430219.png</code></li>
</ul>
If you invoke <code>ec/add</code> with an image upload, the image will be used as the emote image, and the filename will be used as the emote name. To choose a different name, simply run it like<br>
<code>ec/add :some_emote:</code> instead.</p>

<p>
Running <code>ec/info :some_emote:</code> will show you some information about the emote, including when it was created and how many times it's been used.
</p>

<p>
Running <code>ec/big :some_emote:</code> will enlarge the emote.
</p>

<p>
There's a few ways to react to a message with an emote you don't have:
<ul>
	<li><code>ec/react speedtest</code> will react with <img src="https://cdn.discordapp.com/emojis/410183865701892106.png?v=1&size=32" class="emote" alt=":speedtest:" title=":speedtest:"> to the last message.
	<li><code>ec/react :speedtest: hello there</code> will react with <img src="https://cdn.discordapp.com/emojis/410183865701892106.png?v=1&size=32" class="emote" alt=":speedtest:" title=":speedtest:"> to the most recent message containing "hello there".
	<li><code>ec/react speedtest @Someone</code> will react with <img src="https://cdn.discordapp.com/emojis/410183865701892106.png?v=1&size=32" class="emote" alt=":speedtest:" title=":speedtest:"> to the last message by Someone.
	<li><code>ec/react ;speedtest; -2</code> will react with <img src="https://cdn.discordapp.com/emojis/410183865701892106.png?v=1&size=32" class="emote" alt=":speedtest:" title=":speedtest:"> to the second-to-last message.
	<li><code>ec/react speedtest 462092903540457473</code> will react with <img src="https://cdn.discordapp.com/emojis/410183865701892106.png?v=1&size=32" class="emote" alt=":speedtest:" title=":speedtest:"> to message ID 462092903540457473.
</ul>
After running this command, the bot will wait for you to also react. Once you react, or after 30s, the bot will remove its reaction. Confused? It works like this:<br>
<img src="https://discord.coffee/829b79.gif" alt="demonstration of how the ec/react command works">
</p>

<p>
	<code>ec/list [user]</code> gives you a list of all emotes. If you provide a user (IDs, names, and @mentions all work),
	then the bot will limit the list to only emotes created by that user.
</p>

<p>
  <code>ec/popular</code> will list all emotes, sorted by how often they've been used within the last 4 weeks.
</p>
