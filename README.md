# Emoji Connoisseur

[![Discord Bots](https://discordbots.org/api/widget/status/405953712113057794.svg)](https://discordbots.org/bot/405953712113057794)

Emoji Connoisseur lets you use emotes you don't have, even without Nitro.

Once you've found an emoji you'd like to use, just send it as if you were sending a regular Discord emoji (e.g. :speedtest:).
It will be detected and sent by the bot. Using semicolons (;thonkang;) is also supported.

If you don't want the bot to respond to you, you can run `ec/toggle`. If the server is opt-in, this will enable the bot response instead.
If you have permissions to manage emojis on a server, you can run `ec/toggleserver` to make the auto response opt-in.

Note that this bot is still in <em>beta</em> status, and is subject to change at any time until it becomes stable.

- To add the bot to your server, visit https://discordapp.com/oauth2/authorize?client_id=405953712113057794&scope=bot&permissions=355392.
- To run your own instance of the bot, read [the installation guide](INSTALLATION.md).
- If you'd like to help out with the code, read [CONTRIBUTING.md](CONTRIBUTING.md).

### Commands

<ul>
	<li><ul>
		<li><code>ec/add :thonkang:</code> (if you already have that emote)</li>
		<li><code>ec/add rollsafe https://image.noelshack.com/fichiers/2017/06/1486495269-rollsafe.png</code></li>
		<li><code>ec/add speedtest https://cdn.discordapp.com/emojis/379127000398430219.png</code></li>
		<li>If you invoke <code>ec/add</code> with an image upload, the image will be used as the emote image,
		and the filename will be used as the emote name. To choose a different name, simply run it like
		<code>ec/add name</code> instead.</li>
	</ul></li>
	<li><code>ec/remove &lt;name&gt;</code> removes an emote from the bot. You have to own it though.</li>
	<li><code>ec/rename &lt;old name&gt; &lt;new name&gt;</code> renames an emote. You have to own it.</li>
	<li>
		<p><code>ec/react &lt;name&gt; [message ID] [#channel]</code> adds a reaction to the message.
		This one's pretty cool since the reaction appears to come from you, rather than the bot.<br>
		If you leave off the message ID, the bot will react to the last sent message.</p>
		<p>Otherwise, you can get the message ID by enabling developer mode (in Settings→Appearance),
		then right clicking on the message you want and clicking "Copy ID".</p>
		<p>After running this command, the bot will add the reaction to the message, and wait for you to also react.
        Once you react, or after 30s, the bot will remove its reaction.
		Confused? It works like this:<br>
		<img src="https://ping-b1nzy.today/829b79.gif" alt="demonstration of how the ec/react command works"></p>
	</li>
	<li>
		<code>ec/list [user]</code> gives you a list of all emotes. If you provide a user (IDs, names, and @mentions all work),
		then the bot will limit the list to only emotes created by that user. Here's
		<a href="https://gist.github.com/anonymous/99199402d5cd5c111aa9896a49e3cf49">an example list</a>.
	</li>
</ul>
