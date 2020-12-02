from chaionline.play import GameClient, PlayAgainstAI
from chaionline.agent import RandomAgent

client = GameClient()
player = RandomAgent()

environment = PlayAgainstAI(client, player, ai_level=8, show_ascii_board=True)
environment._loop()
