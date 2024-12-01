import discord
from discord.ext import commands
from discord.ui import Button, View
import os
from dotenv import load_dotenv
from keep_alive import keep_alive
import asyncio
import random
import string

load_dotenv()
token = os.getenv('DISCORD_TOKEN')

# Initialisation des intents et du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Dictionnaires pour gérer les lobbies, les messages et les joueurs
lobbies = {}
lobby_messages = {}
MAX_PARTICIPANTS = 2  # Nombre minimum de participants pour lancer la partie
int_designated = {}

def generate_lobby_name():
    """Génère un nom de lobby aléatoire."""
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))

@bot.tree.command(name="newlobby")
async def newlobby(interaction: discord.Interaction):
    # Générer un nom de lobby unique
    lobby_name = generate_lobby_name()

    # Vérification si le lobby existe déjà
    while lobby_name in lobbies:
        lobby_name = generate_lobby_name()  # Regénérer le nom si déjà pris

    # Création d'un nouveau lobby
    lobbies[lobby_name] = []

    button = Button(label="Participer", style=discord.ButtonStyle.primary)

    async def button_callback(interaction: discord.Interaction):
        # Ajout de l'utilisateur au lobby
        if interaction.user not in lobbies[lobby_name]:
            lobbies[lobby_name].append(interaction.user)
            participants_list = "\n".join([p.mention for p in lobbies[lobby_name]])

            # Mise à jour du message de lobby avec la liste des participants
            await lobby_messages[lobby_name].edit(content=f"Lobby '{lobby_name}' en cours de création.\nDécompte : 10 secondes restantes.\nParticipants :\n{participants_list}")

    button.callback = button_callback

    # Vue avec le bouton pour rejoindre le lobby
    view = View()
    view.add_item(button)

    # Envoi d'un message initial pour la création du lobby
    await interaction.response.send_message("Création du lobby...")
    embed = discord.Embed(
        title=f"Lobby '{lobby_name}' en cours de création",
        description="Décompte : 10 secondes restantes.\nParticipants : Aucun",
        color=discord.Color.yellow()
    )

    # Ajout du bouton pour lancer la partie (désactivé au départ)
    start_button = Button(label="Lancer la partie", style=discord.ButtonStyle.green, disabled=True)

    async def start_game_callback(interaction: discord.Interaction):
        if len(lobbies[lobby_name]) < MAX_PARTICIPANTS:
            await interaction.response.send_message(
                f"Impossible de lancer la partie : le lobby '{lobby_name}' doit avoir au moins {MAX_PARTICIPANTS} participants.",
                ephemeral=True
            )
        else:
            await launch_game(interaction, lobby_name, lobby_messages[lobby_name])

    start_button.callback = start_game_callback
    start_view = View()
    start_view.add_item(start_button)

    # Envoi du message de lobby avec le bouton désactivé
    lobby_message = await interaction.followup.send(embed=embed, view=view)

    # Stockage du message pour mise à jour ultérieure
    lobby_messages[lobby_name] = lobby_message

    # Décompte de 10 secondes
    for seconds_left in range(20, 0, -1):
        await asyncio.sleep(1)
        participants_list = "\n".join([p.mention for p in lobbies[lobby_name]])
        
        # Création de la jauge de progression
        progress = "█" * (20 - seconds_left) + "░" * seconds_left
        embed.description = f"Décompte : {seconds_left} secondes restantes\n{progress}\nParticipants :\n{participants_list}"

        await lobby_messages[lobby_name].edit(embed=embed)

    # Activation du bouton de démarrage de la partie
    embed.description = f"Le décompte est terminé. Vous pouvez lancer la partie si le lobby contient au moins {MAX_PARTICIPANTS} joueurs.\nParticipants :\n" + "\n".join([p.mention for p in lobbies[lobby_name]])
    start_button.disabled = False
    await lobby_messages[lobby_name].edit(embed=embed, view=start_view)

async def launch_game(interaction, lobby_name, message):
    participants = lobbies[lobby_name]
    int_player = random.choice(participants)
    int_designated[lobby_name] = int_player

    # Envoi des messages privés aux participants
    for player in participants:
        try:
            if player == int_player:
                await player.send(f"Tu as été choisi pour 'int' la partie du lobby '{lobby_name}' ! Bonne chance !")
            else:
                await player.send(f"Tu dois tryhard la partie du lobby '{lobby_name}'. À toi de jouer !")
        except discord.Forbidden:
            print(f"Impossible d'envoyer un message à {player.name}, messages privés désactivés.")

    # Initialisation des votes
    votes = {participant: 0 for participant in participants}
    voted_users = set()

    # Création du sondage avec les options
    options = [discord.SelectOption(label=p.name, value=str(i)) for i, p in enumerate(participants)]
    select = discord.ui.Select(placeholder="Choisissez l'inter", options=options)

    async def select_callback(interaction: discord.Interaction):
        if interaction.user in voted_users:
            await interaction.response.send_message(f"Tu as déjà voté, {interaction.user.mention} !", ephemeral=True)
            return

        voted_index = int(select.values[0])
        voted_player = participants[voted_index]
        votes[voted_player] += 1
        voted_users.add(interaction.user)

        # Mise à jour des résultats des votes
        results_message = "Résultats des votes :\n" + "\n".join([f"{p.name}: {votes[p]} vote(s)" for p in participants])
        embed = message.embeds[0]
        embed.description = f"{embed.description}\n\n{results_message}"

        await message.edit(embed=embed)

    select.callback = select_callback

    # Bouton pour révéler les imposteurs
    reveal_impostors_button = Button(label="Révéler les imposteurs", style=discord.ButtonStyle.red)

    async def reveal_impostors_callback(interaction: discord.Interaction):
        max_votes = max(votes.values())
        impostors = [p for p, v in votes.items() if v == max_votes]
        impostor_voted = random.choice(impostors)
        int_actual = int_designated[lobby_name]

        if impostor_voted == int_actual:
            conclusion = f"**Bravo ! Vous avez trouvé l'inter : {int_actual.mention}.**"
        else:
            conclusion = f"**Raté ! L'inter était {int_actual.mention}, mais vous avez voté pour {impostor_voted.mention}.**"

        results_message = (
            f"Résultats des votes :\n"
            + "\n".join([f"{p.name}: {votes[p]} vote(s)" for p in participants])
            + f"\n\n{conclusion}"
        )
        embed = message.embeds[0]
        embed.description = f"{embed.description}\n\n{results_message}"

        # Modification du message pour révéler les imposteurs et ajouter le bouton "Fin de partie"
        await message.edit(embed=embed)

        # Ajouter un seul message de résultats des imposteurs
        await interaction.channel.send(f"Les imposteurs ont été révélés ! Voici les résultats :")
        await interaction.channel.send(results_message)

        # Ajout du bouton "Fin de partie"
        end_game_button = Button(label="Fin de partie", style=discord.ButtonStyle.danger)

        async def end_game_callback(interaction: discord.Interaction):
            # Supprimer les participants et le lobby
            lobbies[lobby_name].clear()
            int_designated.pop(lobby_name, None)
            await interaction.response.send_message(f"Le lobby '{lobby_name}' a été supprimé et la partie est terminée.", ephemeral=True)
            await message.delete()  # Supprimer le message de lancement de la partie

        end_game_button.callback = end_game_callback

        end_game_view = View()
        end_game_view.add_item(end_game_button)

        # Modifier le message pour ajouter le bouton "Fin de partie"
        await message.edit(embed=embed, view=end_game_view)

    reveal_impostors_button.callback = reveal_impostors_callback

    # Création de la vue pour la fin de la partie
    end_game_view = View()
    end_game_view.add_item(select)
    end_game_view.add_item(reveal_impostors_button)

    # Création du message de lancement de la partie
    embed = discord.Embed(
        title=f"Partie lancée dans le lobby '{lobby_name}'",
        description=f"Les messages privés ont été envoyés aux participants.\n\nParticipants :\n" + "\n".join([p.mention for p in participants]),
        color=discord.Color.green()
    )

    await message.edit(embed=embed, view=end_game_view)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f'{bot.user} est prêt.')

keep_alive()
bot.run(token)
