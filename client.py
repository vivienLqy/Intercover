import discord
from discord.ext import commands
import os
from dotenv import load_dotenv
import random
import asyncio

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Initialisation des intents et du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Dictionnaires pour gérer les lobbies et les votes
lobbies = {}
int_designated = {}
votes = {}

MAX_PARTICIPANTS = 2  # Nombre minimum de participants pour lancer la partie

def generate_lobby_name():
    """Génère un nom de lobby aléatoire."""
    return ''.join(random.choices("ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789", k=6))

@bot.tree.command(name="newlobby")
async def newlobby(interaction: discord.Interaction):
    lobby_name = generate_lobby_name()
    while lobby_name in lobbies:
        lobby_name = generate_lobby_name()

    lobbies[lobby_name] = []
    await interaction.response.send_message(f"Lobby '{lobby_name}' créé ! Réagissez avec ✅ pour rejoindre. Décompte en cours...")

    message = await interaction.followup.send(
        content=f"**Lobby '{lobby_name}'**\nParticipants : Aucun\nDécompte : 20 secondes restantes.",
    )

    # Ajout de la réaction pour participer
    await message.add_reaction("✅")

    # Collecte des réactions pour ajouter des participants
    def check_reaction(reaction, user):
        return str(reaction.emoji) == "✅" and reaction.message.id == message.id and user != bot.user

    try:
        for _ in range(20):
            reaction, user = await bot.wait_for("reaction_add", timeout=1, check=check_reaction)
            if user not in lobbies[lobby_name]:
                lobbies[lobby_name].append(user)
            participants = "\n".join([p.mention for p in lobbies[lobby_name]])
            await message.edit(content=f"**Lobby '{lobby_name}'**\nParticipants :\n{participants}\nDécompte : {20 - len(lobbies[lobby_name])} secondes restantes.")
    except asyncio.TimeoutError:
        pass

    participants = lobbies[lobby_name]
    if len(participants) < MAX_PARTICIPANTS:
        await message.edit(content=f"Lobby '{lobby_name}' annulé : pas assez de participants.")
        del lobbies[lobby_name]
        return

    int_player = random.choice(participants)
    int_designated[lobby_name] = int_player

    for player in participants:
        try:
            if player == int_player:
                await player.send(f"Tu as été désigné comme 'inter' pour le lobby '{lobby_name}'. Bonne chance !")
            else:
                await player.send(f"Le lobby '{lobby_name}' est prêt. Essayez de deviner qui est l'inter !")
        except discord.Forbidden:
            print(f"Impossible d'envoyer un message à {player.name}.")

    # Démarrage du vote
    embed = discord.Embed(
        title=f"Vote pour l'inter du lobby '{lobby_name}'",
        description="Réagissez avec les emojis correspondants au joueur que vous pensez être l'inter.",
        color=discord.Color.blue()
    )
    for i, participant in enumerate(participants):
        embed.add_field(name=f"Joueur {i+1}", value=participant.mention, inline=False)

    vote_message = await interaction.followup.send(embed=embed)
    votes[lobby_name] = {participant: 0 for participant in participants}

    # Ajout des réactions pour voter
    emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣", "5️⃣"][:len(participants)]
    for emoji in emojis:
        await vote_message.add_reaction(emoji)

    # Collecte des votes
    def check_vote(reaction, user):
        return reaction.message.id == vote_message.id and user in participants and str(reaction.emoji) in emojis

    for _ in range(len(participants)):
        try:
            reaction, user = await bot.wait_for("reaction_add", timeout=20, check=check_vote)
            voted_index = emojis.index(str(reaction.emoji))
            votes[lobby_name][participants[voted_index]] += 1
        except asyncio.TimeoutError:
            break

    # Annonce des résultats
    max_votes = max(votes[lobby_name].values())
    impostors = [p for p, v in votes[lobby_name].items() if v == max_votes]
    impostor_voted = random.choice(impostors)
    int_actual = int_designated[lobby_name]

    if impostor_voted == int_actual:
        conclusion = f"**Bravo ! Vous avez trouvé l'inter : {int_actual.mention}.**"
    else:
        conclusion = f"**Raté ! L'inter était {int_actual.mention}, mais vous avez voté pour {impostor_voted.mention}.**"

    results = "\n".join([f"{p.name}: {v} vote(s)" for p, v in votes[lobby_name].items()])
    await interaction.followup.send(
        content=f"**Résultats du vote :**\n{results}\n\n{conclusion}"
    )
    del lobbies[lobby_name]
    del int_designated[lobby_name]

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{bot.user} est prêt.')

bot.run(token)
